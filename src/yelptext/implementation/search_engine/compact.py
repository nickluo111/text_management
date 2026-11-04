"""Compact integer-posting storage for full-corpus lexical search.

The formulas and token policy are identical to the reference SQLite backend.
Only storage and numeric execution change: one eight-byte (docno, tf) posting,
one blob per term, and memory-mapped length/norm arrays. No term is pruned.
"""

from __future__ import annotations

from array import array
from collections import Counter
from collections.abc import Callable, Mapping
import heapq
import json
import math
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from typing import Any

import numpy as np

from yelptext.protocol.reviewer import PreparedReviewReader
from yelptext.protocol.tokenizer import TokenizerPipeline
from .index import (
    BM25_FORMULA, TFIDF_FORMULA, SearchIndex, SearchIndexError,
    _fingerprint, _review_json, _terms,
)


BACKEND = "compact-v1"
UINT32_MAX = (1 << 32) - 1
Progress = Callable[[dict[str, Any]], None]


def _estimate_bytes(postings: int, vocabulary: int, documents: int) -> int:
    # Arrays overallocate; include per-term Python objects, corpus vectors,
    # SQLite cache, and temporary vectors for a maximal-frequency term.
    return int(postings * 8 * 1.25 + vocabulary * 400 + documents * 64 + 128 * 1024**2)


def _remove_stage(stage: Path, destination: Path) -> None:
    resolved = stage.resolve()
    if resolved.parent != destination.resolve().parent or not resolved.name.startswith(
        f".{destination.name}-building-"
    ):
        raise RuntimeError("Refusing to remove an unexpected index staging directory")
    shutil.rmtree(resolved)


def build_compact_index(
    reader: PreparedReviewReader,
    tokenizer: TokenizerPipeline,
    output_dir: str | Path,
    *,
    progress: Progress | None = None,
    max_memory_bytes: int | None = None,
) -> dict[str, Any]:
    """Build a new compact index, publishing its directory only on success.

    The in-memory posting buffers require approximately eight bytes per unique
    term/document pair plus vocabulary/array overhead. ``max_memory_bytes`` is
    a conservative estimated-working-set limit, checked every 1,000 documents;
    callers should additionally monitor actual RSS and system availability.
    """
    if max_memory_bytes is not None and (
        type(max_memory_bytes) is not int or max_memory_bytes <= 0
    ):
        raise ValueError("max_memory_bytes must be a positive integer")
    fingerprint = _fingerprint(tokenizer)
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError(f"Compact index destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}-building-", dir=destination.parent))
    connection: sqlite3.Connection | None = None
    published = False
    try:
        connection = sqlite3.connect(stage / "compact.sqlite3")
        # This is an unpublished, disposable database. On failure the complete
        # stage is discarded, so per-transaction rollback journals are needless.
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA cache_size=-65536")
        connection.executescript("""
            CREATE TABLE documents (
                docno INTEGER PRIMARY KEY,
                doc_id TEXT UNIQUE NOT NULL,
                review_json TEXT NOT NULL
            );
            CREATE TABLE terms (
                term TEXT PRIMARY KEY,
                df INTEGER NOT NULL,
                idf REAL NOT NULL,
                postings BLOB NOT NULL
            );
        """)
        postings: dict[str, array] = {}
        lengths = array("I")
        document_rows = []
        total_terms = posting_count = max_tf = estimated_peak = 0

        def emit(stage_name: str, **extra: Any) -> None:
            if progress is not None:
                progress({
                    "stage": stage_name, "documents": len(lengths),
                    "postings": posting_count,
                    "estimated_memory_bytes": estimated_peak, **extra,
                })

        def flush_documents() -> None:
            if not document_rows:
                return
            try:
                connection.executemany("INSERT INTO documents VALUES (?, ?, ?)", document_rows)
            except sqlite3.IntegrityError as exc:
                raise ValueError("Duplicate doc_id in prepared reviews") from exc
            document_rows.clear()
            connection.commit()

        for review in reader.iter_reviews():
            if not isinstance(review, Mapping):
                raise ValueError("Each prepared review must be a mapping")
            serialized = _review_json(review)
            docno = len(lengths)
            if docno > UINT32_MAX:
                raise ValueError("Compact index supports at most 2^32 documents")
            counts = Counter(_terms(tokenizer, review["text"]))
            length = sum(counts.values())
            if length > UINT32_MAX:
                raise ValueError("Document length exceeds uint32 storage")
            lengths.append(length)
            document_rows.append((docno, review["doc_id"], serialized))
            total_terms += length
            posting_count += len(counts)
            for term, frequency in counts.items():
                if frequency > max_tf:
                    max_tf = frequency
                bucket = postings.get(term)
                if bucket is None:
                    bucket = postings[term] = array("Q")
                bucket.append((frequency << 32) | docno)
            if len(lengths) % 1000 == 0:
                flush_documents()
                estimate = _estimate_bytes(posting_count, len(postings), len(lengths))
                estimated_peak = max(estimated_peak, estimate)
                if max_memory_bytes is not None and estimate > max_memory_bytes:
                    raise MemoryError(
                        f"Estimated compact build memory {estimate:,} exceeds budget {max_memory_bytes:,}"
                    )
                if len(lengths) % 50000 == 0:
                    emit("documents")
        flush_documents()
        document_count = len(lengths)
        estimated_peak = max(estimated_peak, _estimate_bytes(posting_count, len(postings), document_count))
        if max_memory_bytes is not None and estimated_peak > max_memory_bytes:
            raise MemoryError("Estimated compact build working set exceeds max_memory_bytes")
        emit("document_scan_complete")
        if _fingerprint(tokenizer) != fingerprint:
            raise SearchIndexError("Tokenizer fingerprint changed during index construction")

        # uint32 document lengths and float64 norms have stable on-disk dtypes.
        np.save(stage / "lengths.npy", np.asarray(lengths, dtype="<u4"), allow_pickle=False)
        norms = np.zeros(document_count, dtype="<f8")
        # Use math.log for the same scalar TF weights as the reference ranker.
        weights = np.array([0.0] + [1.0 + math.log(tf) for tf in range(1, max_tf + 1)])
        vocabulary_size = len(postings)
        for number, term in enumerate(sorted(postings), 1):
            bucket = postings.pop(term)
            if sys.byteorder != "little":
                bucket.byteswap()
            pairs = np.frombuffer(bucket, dtype="<u4").reshape(-1, 2)
            docnos, frequencies = pairs[:, 0], pairs[:, 1]
            df = len(bucket)
            idf = math.log((document_count + 1) / (df + 1)) + 1.0
            document_weights = weights[frequencies] * idf
            # Each document appears at most once in a term's posting list.
            norms[docnos] += document_weights * document_weights
            connection.execute(
                "INSERT INTO terms VALUES (?, ?, ?, ?)",
                (term, df, idf, memoryview(bucket)),
            )
            if number % 10000 == 0:
                connection.commit()
                emit("terms", terms_written=number, vocabulary_size=vocabulary_size)
        connection.commit()
        connection.close()
        connection = None
        np.sqrt(norms, out=norms)
        np.save(stage / "norms.npy", norms, allow_pickle=False)
        metadata = {
            "format_version": 1, "backend": BACKEND,
            "tokenizer_fingerprint": fingerprint,
            "document_count": document_count, "vocabulary_size": vocabulary_size,
            "total_terms": total_terms, "avgdl": total_terms / document_count if document_count else 0.0,
            "posting_count": posting_count, "max_tf": max_tf,
            "estimated_peak_build_bytes": estimated_peak,
            "tfidf_formula": TFIDF_FORMULA, "bm25_formula": BM25_FORMULA,
            "posting_encoding": "little-endian uint32 docno, uint32 tf",
        }
        (stage / "manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        # Flush all completed files before publishing a valid directory name.
        import os
        for path in stage.iterdir():
            with path.open("r+b") as stream:
                os.fsync(stream.fileno())
        stage.rename(destination)
        published = True
        emit("complete", vocabulary_size=vocabulary_size)
        return metadata
    finally:
        if connection is not None:
            connection.close()
        if not published and stage.exists():
            _remove_stage(stage, destination)


class CompactSearchIndex(SearchIndex):
    """Read-only term blobs and memory-mapped corpus vectors."""

    def __init__(self, output_dir: str | Path, tokenizer: TokenizerPipeline) -> None:
        self.directory = Path(output_dir)
        self.path = self.directory / "compact.sqlite3"
        self._tokenizer = tokenizer
        self._closed = False
        self._connection = None
        self.lengths = self.norms = None
        try:
            self._metadata = json.loads((self.directory / "manifest.json").read_text(encoding="utf-8"))
            meta = self._metadata
            if meta.get("backend") != BACKEND or meta.get("format_version") != 1:
                raise SearchIndexError("Unsupported compact index format")
            if meta.get("tfidf_formula") != TFIDF_FORMULA or meta.get("bm25_formula") != BM25_FORMULA:
                raise SearchIndexError("Unsupported compact index scoring formulas")
            for key in ("document_count", "vocabulary_size", "total_terms", "posting_count", "max_tf"):
                if type(meta.get(key)) is not int or meta[key] < 0:
                    raise SearchIndexError(f"Invalid compact index metadata: {key}")
            expected_avg = meta["total_terms"] / meta["document_count"] if meta["document_count"] else 0.0
            if not isinstance(meta.get("avgdl"), (float, int)) or not math.isclose(meta["avgdl"], expected_avg):
                raise SearchIndexError("Invalid compact index average document length")
            if not self.path.is_file():
                raise FileNotFoundError(self.path)
            self._connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            self._connection.execute("PRAGMA cache_size=-65536")
            self._connection.execute("SELECT docno, doc_id, review_json FROM documents LIMIT 0")
            self._connection.execute("SELECT term, df, idf, postings FROM terms LIMIT 0")
            mmap_mode = "r" if meta["document_count"] else None
            self.lengths = np.load(self.directory / "lengths.npy", mmap_mode=mmap_mode, allow_pickle=False)
            self.norms = np.load(self.directory / "norms.npy", mmap_mode=mmap_mode, allow_pickle=False)
            if self.lengths.dtype != np.dtype("<u4") or self.norms.dtype != np.dtype("<f8"):
                raise SearchIndexError("Invalid compact index vector dtypes")
            if self.lengths.shape != (meta["document_count"],) or self.norms.shape != self.lengths.shape:
                raise SearchIndexError("Compact index vector sizes do not match metadata")
            self._tf_weights = np.array([0.0] + [1.0 + math.log(tf) for tf in range(1, meta["max_tf"] + 1)])
            self._check_tokenizer()
        except BaseException:
            self.close()
            raise

    def term_df(self, term: str) -> int:
        self._ensure_open()
        row = self._connection.execute("SELECT df FROM terms WHERE term=?", (term,)).fetchone()
        return row[0] if row else 0

    def postings(self, term: str) -> list[tuple[str, int]]:
        """Materialize diagnostic postings; use term_df for cheap term counts."""
        self._ensure_open()
        row = self._connection.execute("SELECT df, postings FROM terms WHERE term=?", (term,)).fetchone()
        if row is None:
            return []
        df, blob = row
        if len(blob) != df * 8:
            raise SearchIndexError("Invalid compact posting length")
        pairs = np.frombuffer(blob, dtype="<u4").reshape(-1, 2)
        rows = []
        for offset in range(0, len(pairs), 900):
            chunk = pairs[offset:offset + 900]
            ids = chunk[:, 0].tolist()
            frequencies = dict(zip(ids, chunk[:, 1].tolist()))
            sql = "SELECT docno,doc_id FROM documents WHERE docno IN (" + ",".join("?" for _ in ids) + ")"
            rows.extend((doc_id, frequencies[docno]) for docno, doc_id in self._connection.execute(sql, ids))
        return sorted(rows)

    def close(self) -> None:
        if not self._closed:
            if self._connection is not None:
                self._connection.close()
            for values in (self.lengths, self.norms):
                if values is not None and getattr(values, "_mmap", None) is not None:
                    values._mmap.close()
            self._closed = True


def load_compact_index(output_dir: str | Path, tokenizer: TokenizerPipeline) -> CompactSearchIndex:
    return CompactSearchIndex(output_dir, tokenizer)


def _choose_docnos(index: CompactSearchIndex, scores: np.ndarray, top_k: int) -> list[int]:
    count = np.count_nonzero(scores > 0)
    if count == 0:
        return []
    if count <= top_k:
        return np.flatnonzero(scores > 0).tolist()
    threshold = float(np.partition(scores, len(scores) - top_k)[len(scores) - top_k])
    selected = np.flatnonzero(scores > threshold).tolist()
    remaining = top_k - len(selected)
    ties = np.flatnonzero(scores == threshold)

    def tie_candidates():
        for start in range(0, len(ties), 900):
            ids = ties[start:start + 900].tolist()
            sql = (
                "SELECT doc_id,docno FROM documents WHERE docno IN ("
                + ",".join("?" for _ in ids) + ") ORDER BY doc_id LIMIT ?"
            )
            yield from index._connection.execute(sql, [*ids, remaining])

    selected.extend(docno for _, docno in heapq.nsmallest(remaining, tie_candidates()))
    return selected


def search_compact(
    index: CompactSearchIndex, query: str, *, ranker: str = "bm25", top_k: int = 10,
    k1: float = 1.5, b: float = 0.75,
):
    """Vectorized execution of the reference TF-IDF/BM25 formulas."""
    from .ranking import SearchResult, _validate_parameters

    _validate_parameters(ranker, top_k, k1, b)
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    index._check_tokenizer()
    query_counts = Counter(_terms(index._tokenizer, query))
    meta = index._metadata
    scores = np.zeros(meta["document_count"], dtype=np.float64)
    query_norm_squared = 0.0
    for term, query_tf in sorted(query_counts.items()):
        row = index._connection.execute("SELECT df,idf,postings FROM terms WHERE term=?", (term,)).fetchone()
        if row is None:
            continue
        df, idf, blob = row
        if len(blob) != df * 8:
            raise SearchIndexError("Invalid compact posting length")
        pairs = np.frombuffer(blob, dtype="<u4").reshape(-1, 2)
        docnos, frequencies = pairs[:, 0], pairs[:, 1]
        if len(docnos) and (docnos.max() >= len(scores) or frequencies.min() < 1 or frequencies.max() > meta["max_tf"]):
            raise SearchIndexError("Invalid compact posting values")
        if ranker == "tfidf":
            query_weight = (1.0 + math.log(query_tf)) * idf
            query_norm_squared += query_weight ** 2
            document_weight = index._tf_weights[frequencies] * idf
            scores[docnos] += document_weight * query_weight / index.norms[docnos]
        else:
            idf = math.log1p((meta["document_count"] - df + 0.5) / (df + 0.5))
            tf = frequencies.astype(np.float64)
            normalization = 1.0 - b + b * index.lengths[docnos] / meta["avgdl"]
            if k1 >= 1:
                tf_weight = tf * (1.0 + 1.0 / k1) / (tf / k1 + normalization)
            else:
                tf_weight = tf * (k1 + 1.0) / (tf + k1 * normalization)
            scores[docnos] += idf * tf_weight * query_tf
    if ranker == "tfidf" and query_norm_squared:
        scores /= math.sqrt(query_norm_squared)
    results = []
    for docno in _choose_docnos(index, scores, top_k):
        doc_id, serialized = index._connection.execute(
            "SELECT doc_id,review_json FROM documents WHERE docno=?", (docno,)
        ).fetchone()
        review = json.loads(serialized)
        results.append(SearchResult(
            doc_id=doc_id, score=float(scores[docno]), text=review["text"],
            business_id=review.get("business_id"), business_name=review.get("business_name"),
            stars=review.get("stars"), city=review.get("city"), state=review.get("state"),
        ))
    return sorted(results, key=lambda result: (-result.score, result.doc_id))

