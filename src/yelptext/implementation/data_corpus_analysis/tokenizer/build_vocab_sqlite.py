"""Build the shared full-corpus vocabulary as a disk-backed SQLite file."""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from .sqlite_vocabulary import SqliteVocabularyBuilder


ProgressCallback = Callable[[str, int, int], None]


def build_sqlite_vocabulary(
    input_file: str | Path,
    output_file: str | Path,
    *,
    buffer_unique_terms: int = 100_000,
    progress: ProgressCallback | None = None,
) -> dict[str, object]:
    """Build one full-CF/DF vocabulary without loading the corpus into memory."""

    source_path = Path(input_file)
    target_path = Path(output_file)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    parsing = {"nonempty_lines": 0, "bad_lines": 0}

    def documents() -> Iterator[str]:
        with source_path.open("rb") as source:
            for raw in source:
                if not raw.strip():
                    continue
                parsing["nonempty_lines"] += 1
                try:
                    row = json.loads(raw)
                    text = row["text"]
                    if not isinstance(text, str):
                        raise TypeError("field 'text' must be a string")
                except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError):
                    parsing["bad_lines"] += 1
                    continue
                yield text

    builder = SqliteVocabularyBuilder(buffer_unique_terms=buffer_unique_terms)
    metadata: dict[str, object] = builder.build(
        documents(), target_path, progress=progress
    )
    metadata.update(
        {
            "input_file": str(source_path),
            "input_nonempty_lines": parsing["nonempty_lines"],
            "bad_lines": parsing["bad_lines"],
        }
    )
    with sqlite3.connect(target_path) as connection:
        connection.executemany(
            "INSERT OR REPLACE INTO metadata(key, value_json) VALUES (?, ?)",
            (
                (key, json.dumps(value, ensure_ascii=False))
                for key, value in {
                    "input_file": metadata["input_file"],
                    "input_nonempty_lines": metadata["input_nonempty_lines"],
                    "bad_lines": metadata["bad_lines"],
                }.items()
            ),
        )
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    parser.add_argument("--buffer-unique-terms", type=int, default=100_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.monotonic()

    def progress(phase: str, documents_done: int, tokens_done: int) -> None:
        elapsed = max(time.monotonic() - started, 0.001)
        print(
            f"[{phase}] documents={documents_done:,} tokens={tokens_done:,} "
            f"reviews/s={documents_done / elapsed:,.0f}",
            flush=True,
        )

    metadata = build_sqlite_vocabulary(
        args.input_file,
        args.output_file,
        buffer_unique_terms=args.buffer_unique_terms,
        progress=progress,
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
