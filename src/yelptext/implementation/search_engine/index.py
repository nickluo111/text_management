"""SQLite inverted index built from the approved reader and token pipeline.

The index keeps its own collection statistics, including empty-after-filtering
documents. Vocabulary statistics from another corpus are never imported.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any

from yelptext.protocol.reviewer import PreparedReviewReader
from yelptext.protocol.tokenizer import TokenizerPipeline


FORMAT_VERSION = 2
INDEX_FILENAME = "index.sqlite3"
TFIDF_FORMULA = "log-tf-smoothed-idf-cosine-v1"
BM25_FORMULA = "positive-idf-linear-query-tf-v1"
_BATCH_SIZE = 1000


class SearchIndexError(ValueError):
    """An index is incompatible, incomplete, or violates its data contract."""


def _fingerprint(tokenizer: TokenizerPipeline) -> str:
    value = tokenizer.fingerprint()
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Tokenizer fingerprint must be a non-empty string")
    return value


def _terms(tokenizer: TokenizerPipeline, text: str) -> list[str]:
    terms = tokenizer.terms(text)
    if not isinstance(terms, list) or any(
        not isinstance(term, str) or not term.strip() for term in terms
    ):
        raise ValueError("Tokenizer terms() must return a list of non-empty strings")
    return terms


def _review_json(review: Mapping[str, Any]) -> str:
    for key in ("doc_id", "text"):
        if not isinstance(review.get(key), str) or not review[key].strip():
            raise ValueError(f"Review {key} must be a non-empty string")
    for key in ("business_id", "business_name", "city", "state"):
        if review.get(key) is not None and not isinstance(review[key], str):
            raise ValueError(f"Review {key} must be a string or None")
    stars = review.get("stars")
    if stars is not None and (
        isinstance(stars, bool)
        or not isinstance(stars, (int, float))
        or not math.isfinite(stars)
        or not 1 <= stars <= 5
    ):
        raise ValueError("Review stars must be a finite number between 1 and 5 or None")
    return json.dumps(dict(review), ensure_ascii=False, allow_nan=False)


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE documents (
            docno INTEGER PRIMARY KEY,
            doc_id TEXT UNIQUE NOT NULL,
            review_json TEXT NOT NULL,
            length INTEGER NOT NULL CHECK(length >= 0),
            norm REAL NOT NULL DEFAULT 0 CHECK(norm >= 0)
        );
        CREATE TABLE postings (
            term TEXT NOT NULL,
            docno INTEGER NOT NULL REFERENCES documents(docno),
            tf INTEGER NOT NULL CHECK(tf > 0)
        );
        CREATE TABLE terms (
            term TEXT PRIMARY KEY,
            df INTEGER NOT NULL CHECK(df > 0),
            idf REAL NOT NULL DEFAULT 0
        );
        """
    )


def _finish_statistics(connection: sqlite3.Connection, document_count: int) -> int:
    # During scanning postings are an append-only heap. Building the term index
    # once is substantially cheaper than maintaining a text-keyed B-tree for
    # every one of hundreds of millions of incoming rows.
    connection.execute("CREATE INDEX postings_by_term ON postings(term, docno)")
    connection.execute(
        "INSERT INTO terms(term, df) SELECT term, COUNT(*) FROM postings GROUP BY term"
    )
    # Iterate with a separate cursor, batching writes rather than materializing
    # the entire vocabulary or term-document matrix.
    cursor = connection.execute("SELECT term, df FROM terms ORDER BY term")
    vocabulary_size = 0
    while rows := cursor.fetchmany(_BATCH_SIZE):
        connection.executemany(
            "UPDATE terms SET idf = ? WHERE term = ?",
            (
                (math.log((document_count + 1) / (df + 1)) + 1.0, term)
                for term, df in rows
            ),
        )
        vocabulary_size += len(rows)
    cursor.close()

    connection.execute("CREATE INDEX postings_by_document ON postings(docno, term)")
    cursor = connection.execute(
        "SELECT p.docno, p.tf, t.idf FROM postings p "
        "JOIN terms t ON t.term = p.term ORDER BY p.docno, p.term"
    )
    updates: list[tuple[float, int]] = []
    previous_docno: int | None = None
    sum_squares = 0.0
    for docno, tf, idf in cursor:
        if previous_docno is not None and docno != previous_docno:
            updates.append((math.sqrt(sum_squares), previous_docno))
            sum_squares = 0.0
            if len(updates) >= _BATCH_SIZE:
                connection.executemany("UPDATE documents SET norm = ? WHERE docno = ?", updates)
                updates.clear()
        previous_docno = docno
        sum_squares += ((1.0 + math.log(tf)) * idf) ** 2
    cursor.close()
    if previous_docno is not None:
        updates.append((math.sqrt(sum_squares), previous_docno))
    connection.executemany("UPDATE documents SET norm = ? WHERE docno = ?", updates)
    return vocabulary_size


def build_index(
    reader: PreparedReviewReader,
    tokenizer: TokenizerPipeline,
    output_dir: str | Path,
    *,
    progress: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """Stream reviews into a new, atomically published ``index.sqlite3``.

    Existing indexes are never overwritten. A failed build leaves no published
    index; its temporary database is removed. Use a fresh directory to rebuild
    under a new corpus or tokenizer policy.
    """

    fingerprint = _fingerprint(tokenizer)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / INDEX_FILENAME
    if output_path.exists():
        raise FileExistsError(f"Index already exists: {output_path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".index-", suffix=".sqlite3", dir=output_dir
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(temporary_path)
        # The database is an unpublished disposable staging file. Disabling
        # rollback journaling and fsync substantially reduces full-corpus build
        # time without weakening the atomic publication contract: any failure
        # removes the staging file, and only a committed database is renamed.
        connection.execute("PRAGMA journal_mode = OFF")
        connection.execute("PRAGMA synchronous = OFF")
        connection.execute("PRAGMA locking_mode = EXCLUSIVE")
        connection.execute("PRAGMA cache_size = -262144")
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.execute("PRAGMA foreign_keys = ON")
        _create_schema(connection)
        document_count = 0
        total_terms = 0
        document_rows: list[tuple[int, str, str, int]] = []
        posting_rows: list[tuple[str, int, int]] = []

        def flush_batch() -> None:
            if not document_rows:
                return
            try:
                connection.executemany(
                    "INSERT INTO documents(docno, doc_id, review_json, length) VALUES (?, ?, ?, ?)",
                    document_rows,
                )
                connection.executemany(
                    "INSERT INTO postings(term, docno, tf) VALUES (?, ?, ?)",
                    posting_rows,
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("Duplicate doc_id in prepared reviews") from exc
            connection.commit()
            document_rows.clear()
            posting_rows.clear()

        for review in reader.iter_reviews():
            if not isinstance(review, Mapping):
                raise ValueError("Each prepared review must be a mapping")
            serialized = _review_json(review)
            counts = Counter(_terms(tokenizer, review["text"]))
            length = sum(counts.values())
            docno = document_count
            document_rows.append((docno, review["doc_id"], serialized, length))
            posting_rows.extend(
                (term, docno, tf) for term, tf in sorted(counts.items())
            )
            document_count += 1
            total_terms += length
            if progress is not None and document_count % 250_000 == 0:
                progress(document_count)
            if document_count % _BATCH_SIZE == 0:
                flush_batch()

        flush_batch()

        vocabulary_size = _finish_statistics(connection, document_count)
        if _fingerprint(tokenizer) != fingerprint:
            raise SearchIndexError("Tokenizer fingerprint changed during index construction")
        metadata = {
            "format_version": FORMAT_VERSION,
            "tokenizer_fingerprint": fingerprint,
            "document_count": document_count,
            "vocabulary_size": vocabulary_size,
            "total_terms": total_terms,
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
        # Windows rename refuses a racing destination and avoids hard-link
        # permissions in restricted workspaces. POSIX rename would overwrite,
        # so use atomic no-overwrite hard-link publication on that platform.
        if os.name == "nt":
            os.rename(temporary_path, output_path)
        else:
            os.link(temporary_path, output_path)
        return metadata
    finally:
        if connection is not None:
            connection.close()
        temporary_path.unlink(missing_ok=True)
        Path(str(temporary_path) + "-journal").unlink(missing_ok=True)


def _read_metadata(connection: sqlite3.Connection) -> dict[str, Any]:
    try:
        metadata = {
            key: json.loads(value)
            for key, value in connection.execute("SELECT key, value FROM metadata")
        }
        required = {
            "format_version", "tokenizer_fingerprint", "document_count", "vocabulary_size",
            "total_terms", "avgdl", "tfidf_formula", "bm25_formula",
        }
        if not required <= metadata.keys():
            raise SearchIndexError("Index metadata is incomplete; rebuild the index")
        if type(metadata["format_version"]) is not int or metadata["format_version"] != FORMAT_VERSION:
            raise SearchIndexError("Unsupported index format version; rebuild the index")
        if (
            metadata["tfidf_formula"] != TFIDF_FORMULA
            or metadata["bm25_formula"] != BM25_FORMULA
        ):
            raise SearchIndexError("Unsupported index scoring formula; rebuild the index")
        for key in ("document_count", "vocabulary_size", "total_terms"):
            if type(metadata[key]) is not int or metadata[key] < 0:
                raise SearchIndexError(f"Invalid index metadata: {key}")
        fingerprint = metadata["tokenizer_fingerprint"]
        if not isinstance(fingerprint, str) or not fingerprint.strip():
            raise SearchIndexError("Invalid index tokenizer fingerprint")
        average = metadata["avgdl"]
        if (
            isinstance(average, bool)
            or not isinstance(average, (int, float))
            or not math.isfinite(average)
            or average < 0
        ):
            raise SearchIndexError("Invalid index average document length")
        expected_average = (
            metadata["total_terms"] / metadata["document_count"]
            if metadata["document_count"] else 0.0
        )
        if not math.isclose(average, expected_average, rel_tol=1e-12, abs_tol=1e-12):
            raise SearchIndexError("Inconsistent index average document length")
        # Compile queries against all required columns without rescanning a
        # large corpus every time a query process opens an index.
        connection.execute("SELECT docno, doc_id, review_json, length, norm FROM documents LIMIT 0")
        connection.execute("SELECT term, df, idf FROM terms LIMIT 0")
        connection.execute("SELECT term, docno, tf FROM postings LIMIT 0")
    except (sqlite3.DatabaseError, json.JSONDecodeError, TypeError) as exc:
        raise SearchIndexError("Invalid or incomplete search index; rebuild the index") from exc
    return metadata


class SearchIndex:
    """Read-only persisted index with an explicitly managed connection."""

    def __init__(self, output_dir: str | Path, tokenizer: TokenizerPipeline) -> None:
        self.path = Path(output_dir) / INDEX_FILENAME
        if not self.path.is_file():
            raise FileNotFoundError(f"Search index does not exist: {self.path}")
        self._tokenizer = tokenizer
        self._connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        self._closed = False
        try:
            self._metadata = _read_metadata(self._connection)
            self._check_tokenizer()
        except BaseException:
            self.close()
            raise

    def _ensure_open(self) -> None:
        if self._closed:
            raise SearchIndexError("Search index is closed")

    def _check_tokenizer(self) -> None:
        self._ensure_open()
        if _fingerprint(self._tokenizer) != self._metadata["tokenizer_fingerprint"]:
            raise SearchIndexError("Tokenizer fingerprint mismatch; use the index's original policy or rebuild")

    def stats(self) -> dict[str, Any]:
        """Return a copy of persisted collection and compatibility metadata."""
        self._ensure_open()
        return dict(self._metadata)

    def postings(self, term: str) -> list[tuple[str, int]]:
        """Return a term's posting list, ordered by document ID."""
        self._ensure_open()
        return self._connection.execute(
            "SELECT d.doc_id, p.tf FROM postings p "
            "JOIN documents d ON d.docno = p.docno "
            "WHERE p.term = ? ORDER BY d.doc_id",
            (term,),
        ).fetchall()

    def term_df(self, term: str) -> int:
        """Return document frequency without materializing the posting list."""
        self._ensure_open()
        row = self._connection.execute(
            "SELECT df FROM terms WHERE term = ?", (term,)
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def close(self) -> None:
        if not self._closed:
            self._connection.close()
            self._closed = True

    def __enter__(self) -> SearchIndex:
        self._ensure_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def load_index(output_dir: str | Path, tokenizer: TokenizerPipeline) -> SearchIndex:
    """Open a read-only index and verify tokenizer/formula compatibility."""
    return SearchIndex(output_dir, tokenizer)

