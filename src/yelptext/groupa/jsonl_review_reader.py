"""Streaming reader for prepared Yelp JSONL (Python 3.10+, standard library).

Integration: from groupa.jsonl_review_reader import JsonlReviewReader
Then: for review in JsonlReviewReader(path).iter_reviews(): ...

Only the agreed eight fields are returned, in FIELD_ORDER. Optional missing
fields become None. Text, IDs, array order and null versus [] are preserved.
Unexpected source fields are ignored. Invalid records stop iteration with the
source path and line number; no records are silently skipped.

Memory is proportional to the largest individual line, not the file size.
Global doc_id uniqueness is a prerequisite verified by the separate audit;
this reader deliberately keeps no corpus-sized ID set. Each iteration reopens
the file, so one reader can be used repeatedly. Early-stopping consumers should
close their iterator (e.g. contextlib.closing).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Protocol, TypedDict, cast


class PreparedReview(TypedDict):
    doc_id: str
    text: str
    stars: int | float | None
    review_date: str | None
    business_id: str | None
    business_name: str | None
    categories: list[str] | None
    city: str | None


class PreparedReviewReader(Protocol):
    def iter_reviews(self) -> Iterator[PreparedReview]: ...


FIELD_ORDER = (
    "doc_id", "text", "stars", "review_date", "business_id",
    "business_name", "categories", "city",
)


class ReviewReadError(ValueError):
    """Malformed JSONL or a record violating the agreed field contract."""


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON numeric constant: {value}")


def _prepare(record: object) -> PreparedReview:
    if not isinstance(record, dict):
        raise ValueError("each line must be a JSON object")
    for key in ("doc_id", "text"):
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-blank string")
    for key in ("business_id", "business_name", "city"):
        value = record.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{key} must be a string or null")
    stars = record.get("stars")
    if stars is not None:
        if (type(stars) not in (int, float) or not 1 <= stars <= 5
                or not math.isfinite(stars) or stars * 2 != int(stars * 2)):
            raise ValueError("stars must be null or a number from 1 to 5 in half-star steps")
    review_date = record.get("review_date")
    if review_date is not None:
        if not isinstance(review_date, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", review_date) is None:
            raise ValueError("review_date must be null or YYYY-MM-DD")
        try:
            date.fromisoformat(review_date)
        except ValueError as exc:
            raise ValueError("review_date is not a valid calendar date") from exc
    categories = record.get("categories")
    if categories is not None and (
        not isinstance(categories, list)
        or any(not isinstance(item, str) for item in categories)
    ):
        raise ValueError("categories must be a string array or null")
    return cast(PreparedReview, {key: record.get(key) for key in FIELD_ORDER})


class JsonlReviewReader:
    """Read a previously prepared UTF-8 JSONL file; never load it all at once."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def iter_reviews(self) -> Iterator[PreparedReview]:
        with self.path.open("r", encoding="utf-8") as source:
            line_number = 0
            while True:
                try:
                    line = source.readline()
                except UnicodeDecodeError as exc:
                    raise ReviewReadError(
                        f"{self.path}: invalid UTF-8 near line {line_number + 1} "
                        "(decoder buffering may read ahead)"
                    ) from exc
                if not line:
                    return
                line_number += 1
                try:
                    if not line.strip():
                        raise ValueError("blank JSONL line")
                    record = json.loads(
                        line, object_pairs_hook=_object_without_duplicates,
                        parse_constant=_reject_constant,
                    )
                    review = _prepare(record)
                except (ValueError, RecursionError) as exc:
                    raise ReviewReadError(f"{self.path}:{line_number}: {exc}") from exc
                yield review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=3,
                        help="Records to print; default 3, 0 reads the whole file")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be >= 0")
    iterator = JsonlReviewReader(args.input).iter_reviews()
    count = 0
    try:
        for review in iterator:
            print(json.dumps(review, ensure_ascii=False, allow_nan=False))
            count += 1
            if args.limit and count >= args.limit:
                break
    except (OSError, ReviewReadError) as exc:
        print(f"Reader stopped: {exc}", file=sys.stderr)
        return 1
    finally:
        iterator.close()
    print(f"Records returned: {count}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
