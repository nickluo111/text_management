"""Disk-backed full-corpus vocabulary construction and lookup."""

from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .classification import TokenClassifier
from .tokenizer import RegexTokenizer
from .vocabulary import UNK_ID, UNK_TERM, VocabularyEntry


ProgressCallback = Callable[[str, int, int], None]


def _write_metadata(connection: sqlite3.Connection, values: dict[str, Any]) -> None:
    connection.executemany(
        "INSERT OR REPLACE INTO metadata(key, value_json) VALUES (?, ?)",
        ((key, json.dumps(value, ensure_ascii=False)) for key, value in values.items()),
    )


class SqliteVocabularyBuilder:
    """Aggregate CF/DF in bounded memory and persist a typed SQLite vocabulary."""

    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        tokenizer: RegexTokenizer | None = None,
        classifier: TokenClassifier | None = None,
        *,
        buffer_unique_terms: int = 100_000,
    ) -> None:
        if buffer_unique_terms < 1:
            raise ValueError("buffer_unique_terms must be positive")
        self.tokenizer = tokenizer or RegexTokenizer()
        self.classifier = classifier or TokenClassifier()
        self.buffer_unique_terms = buffer_unique_terms

    def build(
        self,
        documents: Iterable[str],
        output_path: str | Path,
        *,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        target = Path(output_path)
        if target.exists():
            raise FileExistsError(f"Output already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(target)
        started = time.monotonic()
        document_count = 0
        total_tokens = 0
        cf_buffer: Counter[str] = Counter()
        df_buffer: Counter[str] = Counter()

        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA temp_store=FILE")
            connection.execute("PRAGMA cache_size=-65536")
            connection.execute(
                "CREATE TABLE metadata (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE stage ("
                "term TEXT PRIMARY KEY, cf INTEGER NOT NULL, df INTEGER NOT NULL"
                ") WITHOUT ROWID"
            )
            _write_metadata(
                connection,
                {
                    "status": "BUILDING",
                    "schema_version": self.SCHEMA_VERSION,
                    "tokenizer_fingerprint": self.tokenizer.fingerprint(),
                },
            )
            connection.commit()

            def flush() -> None:
                if not cf_buffer:
                    return
                connection.executemany(
                    "INSERT INTO stage(term, cf, df) VALUES (?, ?, ?) "
                    "ON CONFLICT(term) DO UPDATE SET "
                    "cf = stage.cf + excluded.cf, "
                    "df = stage.df + excluded.df",
                    (
                        (term, count, df_buffer.get(term, 0))
                        for term, count in cf_buffer.items()
                    ),
                )
                connection.commit()
                cf_buffer.clear()
                df_buffer.clear()

            for text in documents:
                terms = self.tokenizer.tokenize(text)
                document_count += 1
                total_tokens += len(terms)
                cf_buffer.update(terms)
                df_buffer.update(set(terms))
                if len(cf_buffer) >= self.buffer_unique_terms:
                    flush()
                if progress is not None and document_count % 100_000 == 0:
                    progress("tokenize", document_count, total_tokens)
            flush()

            connection.execute(
                "CREATE TABLE terms ("
                "term_id INTEGER PRIMARY KEY, "
                "term TEXT NOT NULL UNIQUE, "
                "cf INTEGER NOT NULL, "
                "df INTEGER NOT NULL, "
                "tags_json TEXT NOT NULL"
                ")"
            )
            connection.execute(
                "INSERT INTO terms(term_id, term, cf, df, tags_json) "
                "VALUES (?, ?, 0, 0, ?)",
                (UNK_ID, UNK_TERM, json.dumps(["special", "unknown"])),
            )

            cursor = connection.execute(
                "SELECT term, cf, df FROM stage ORDER BY term"
            )
            term_id = 1
            while True:
                batch = cursor.fetchmany(10_000)
                if not batch:
                    break
                classified = self.classifier.classify([row[0] for row in batch])
                connection.executemany(
                    "INSERT INTO terms(term_id, term, cf, df, tags_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        (
                            term_id + offset,
                            row[0],
                            row[1],
                            row[2],
                            json.dumps(sorted(token.tags), ensure_ascii=False),
                        )
                        for offset, (row, token) in enumerate(
                            zip(batch, classified, strict=True)
                        )
                    ),
                )
                term_id += len(batch)
                if progress is not None and (term_id - 1) % 100_000 < len(batch):
                    progress("classify", term_id - 1, total_tokens)
            vocabulary_size = term_id
            connection.execute("CREATE INDEX terms_cf_index ON terms(cf DESC)")
            connection.execute("CREATE INDEX terms_df_index ON terms(df DESC)")
            connection.execute("DROP TABLE stage")

            elapsed = time.monotonic() - started
            metadata = {
                "status": "COMPLETED",
                "schema_version": self.SCHEMA_VERSION,
                "tokenizer_fingerprint": self.tokenizer.fingerprint(),
                "document_count": document_count,
                "total_tokens": total_tokens,
                "vocabulary_size_including_unk": vocabulary_size,
                "min_cf": 1,
                "min_df": 1,
                "skip_types": [],
                "pos_tagging_enabled": False,
                "unk_statistics_semantics": (
                    "reserved runtime OOV only; rare terms are not aggregated"
                ),
                "elapsed_seconds": round(elapsed, 3),
            }
            metadata["vocabulary_id"] = (
                f"sqlite-vocabulary-v{self.SCHEMA_VERSION}-"
                f"d{document_count}-n{total_tokens}-v{vocabulary_size}"
            )
            _write_metadata(connection, metadata)
            connection.commit()
            connection.execute("VACUUM")
            if progress is not None:
                progress("complete", document_count, total_tokens)
            return metadata
        finally:
            connection.close()


class SqliteVocabulary:
    """Read-only vocabulary facade compatible with ``VocabularyLookup``."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        uri = self.path.resolve().as_uri() + "?mode=ro"
        self._connection = sqlite3.connect(uri, uri=True)
        self.metadata = {
            key: json.loads(value_json)
            for key, value_json in self._connection.execute(
                "SELECT key, value_json FROM metadata"
            )
        }
        if self.metadata.get("status") != "COMPLETED":
            self.close()
            raise ValueError("SQLite vocabulary is not marked COMPLETED")

    def get(self, term: str) -> VocabularyEntry | None:
        row = self._connection.execute(
            "SELECT term_id, term, cf, df, tags_json FROM terms WHERE term = ?",
            (term,),
        ).fetchone()
        return self._entry(row)

    def get_by_id(self, term_id: int) -> VocabularyEntry | None:
        row = self._connection.execute(
            "SELECT term_id, term, cf, df, tags_json FROM terms WHERE term_id = ?",
            (term_id,),
        ).fetchone()
        return self._entry(row)

    def fingerprint(self) -> str:
        return str(self.metadata["vocabulary_id"])

    @staticmethod
    def _entry(row: tuple[Any, ...] | None) -> VocabularyEntry | None:
        if row is None:
            return None
        return VocabularyEntry(
            term_id=int(row[0]),
            term=str(row[1]),
            cf=int(row[2]),
            df=int(row[3]),
            tags=frozenset(json.loads(row[4])),
            pos_counts={},
        )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SqliteVocabulary":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
