"""MapReduce-style construction of the exact SQLite search index."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any, Iterable

from yelptext.implementation.data_corpus_analysis.tokenizer import create_pipeline

from .index import (
    BM25_FORMULA,
    FORMAT_VERSION,
    INDEX_FILENAME,
    TFIDF_FORMULA,
    _create_schema,
    _finish_statistics,
    _fingerprint,
    _review_json,
    _terms,
)


_MAP_BATCH_SIZE = 1_000


def _configure(connection: sqlite3.Connection, cache_kib: int) -> None:
    connection.execute("PRAGMA journal_mode = OFF")
    connection.execute("PRAGMA synchronous = OFF")
    connection.execute("PRAGMA locking_mode = EXCLUSIVE")
    connection.execute(f"PRAGMA cache_size = -{cache_kib}")
    connection.execute("PRAGMA temp_store = MEMORY")


def _iter_byte_range(path: str, start: int, end: int) -> Iterable[dict[str, Any]]:
    """Yield complete UTF-8 JSONL records whose first byte belongs to a range."""
    with Path(path).open("rb") as source:
        if start:
            source.seek(start - 1)
            if source.read(1) != b"\n":
                source.readline()
        else:
            source.seek(0)
        while True:
            position = source.tell()
            if position >= end:
                break
            line = source.readline()
            if not line:
                break
            if not line.strip():
                raise ValueError(f"Blank JSONL line at byte {position}")
            value = json.loads(line.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError(f"JSONL value at byte {position} is not an object")
            yield value


def _map_shard(
    input_path: str,
    shard_path: str,
    worker_id: int,
    start: int,
    end: int,
    skip_types: tuple[str, ...],
    enable_pos: bool,
) -> dict[str, int]:
    """Tokenize one byte range and append raw integer postings to one shard."""
    tokenizer = create_pipeline(skip_types=skip_types, enable_pos=enable_pos)
    connection = sqlite3.connect(shard_path)
    _configure(connection, 65_536)
    connection.executescript(
        """
        CREATE TABLE documents (
            docno INTEGER PRIMARY KEY,
            doc_id TEXT UNIQUE NOT NULL,
            review_json TEXT NOT NULL,
            length INTEGER NOT NULL,
            norm REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE postings (term TEXT NOT NULL, docno INTEGER NOT NULL, tf INTEGER NOT NULL);
        """
    )
    document_rows: list[tuple[int, str, str, int]] = []
    posting_rows: list[tuple[str, int, int]] = []
    documents = total_terms = postings = 0

    def flush() -> None:
        if not document_rows:
            return
        connection.executemany(
            "INSERT INTO documents(docno, doc_id, review_json, length) VALUES (?, ?, ?, ?)",
            document_rows,
        )
        connection.executemany(
            "INSERT INTO postings(term, docno, tf) VALUES (?, ?, ?)", posting_rows
        )
        connection.commit()
        document_rows.clear()
        posting_rows.clear()

    try:
        for review in _iter_byte_range(input_path, start, end):
            serialized = _review_json(review)
            counts = Counter(_terms(tokenizer, review["text"]))
            length = sum(counts.values())
            docno = (worker_id << 32) | documents
            document_rows.append((docno, review["doc_id"], serialized, length))
            posting_rows.extend((term, docno, tf) for term, tf in counts.items())
            documents += 1
            total_terms += length
            postings += len(counts)
            if documents % _MAP_BATCH_SIZE == 0:
                flush()
        flush()
    finally:
        connection.close()
    return {
        "worker": worker_id,
        "documents": documents,
        "total_terms": total_terms,
        "postings": postings,
    }


def build_index_mapreduce(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    workers: int = 4,
    skip_types: Iterable[str] = ("punctuation",),
    enable_pos: bool = False,
    progress: Any = None,
) -> dict[str, Any]:
    """Build one globally scored index from parallel append-only map shards."""
    if type(workers) is not int or not 2 <= workers <= 8:
        raise ValueError("workers must be an integer between 2 and 8")
    input_path = Path(input_path).resolve()
    destination = Path(output_dir).resolve()
    output_path = destination / INDEX_FILENAME
    if output_path.exists():
        raise FileExistsError(f"Index already exists: {output_path}")
    destination.mkdir(parents=True, exist_ok=True)
    skip_types = tuple(sorted(set(skip_types)))
    tokenizer = create_pipeline(skip_types=skip_types, enable_pos=enable_pos)
    fingerprint = _fingerprint(tokenizer)
    size = input_path.stat().st_size
    ranges = [(size * number // workers, size * (number + 1) // workers) for number in range(workers)]
    stage = Path(tempfile.mkdtemp(prefix=".mapreduce-", dir=destination))
    final_path: Path | None = None
    connection: sqlite3.Connection | None = None
    published = False
    try:
        shard_paths = [stage / f"shard-{number}.sqlite3" for number in range(workers)]
        results = []
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(
                    _map_shard,
                    str(input_path),
                    str(shard_paths[number]),
                    number,
                    *ranges[number],
                    skip_types,
                    enable_pos,
                )
                for number in range(workers)
            ]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                if progress is not None:
                    progress({"stage": "map", **result})

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".index-", suffix=".sqlite3", dir=destination
        )
        os.close(descriptor)
        final_path = Path(temporary_name)
        connection = sqlite3.connect(final_path)
        _configure(connection, 262_144)
        connection.execute("PRAGMA foreign_keys = ON")
        _create_schema(connection)
        for number, shard_path in enumerate(shard_paths):
            alias = f"shard{number}"
            connection.execute(f"ATTACH DATABASE ? AS {alias}", (str(shard_path),))
            connection.execute(
                f"INSERT INTO documents(docno, doc_id, review_json, length, norm) "
                f"SELECT docno, doc_id, review_json, length, norm FROM {alias}.documents"
            )
            connection.execute(
                f"INSERT INTO postings(term, docno, tf) "
                f"SELECT term, docno, tf FROM {alias}.postings"
            )
            connection.commit()
            connection.execute(f"DETACH DATABASE {alias}")
            if progress is not None:
                progress({"stage": "reduce_copy", "shard": number, "workers": workers})

        document_count = sum(item["documents"] for item in results)
        total_terms = sum(item["total_terms"] for item in results)
        posting_count = sum(item["postings"] for item in results)
        vocabulary_size = _finish_statistics(connection, document_count)
        metadata = {
            "format_version": FORMAT_VERSION,
            "build_backend": "mapreduce-sqlite-v1",
            "workers": workers,
            "tokenizer_fingerprint": fingerprint,
            "document_count": document_count,
            "vocabulary_size": vocabulary_size,
            "total_terms": total_terms,
            "posting_count": posting_count,
            "avgdl": total_terms / document_count if document_count else 0.0,
            "tfidf_formula": TFIDF_FORMULA,
            "bm25_formula": BM25_FORMULA,
        }
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            ((key, json.dumps(value)) for key, value in metadata.items()),
        )
        connection.commit()
        connection.close()
        connection = None
        os.rename(final_path, output_path)
        published = True
        return metadata
    finally:
        if connection is not None:
            connection.close()
        if final_path is not None and not published:
            final_path.unlink(missing_ok=True)
        if stage.exists():
            shutil.rmtree(stage)


__all__ = ["build_index_mapreduce"]
