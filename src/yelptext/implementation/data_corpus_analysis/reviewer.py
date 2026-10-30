"""Validate and stream the canonical prepared-review JSONL handoff."""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import cast

from yelptext.protocol.reviewer import PreparedReview


PREPARED_REVIEW_FIELDS = tuple(PreparedReview.__annotations__)


class YelpDataError(ValueError):
    """A JSONL record does not satisfy the prepared-review protocol."""


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON numeric constant: {value}")


def _required_text(record: dict[str, object], field: str) -> str:
    value = record[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-blank string")
    return value


def _optional_text(record: dict[str, object], field: str) -> str | None:
    value = record[field]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-blank string or null")
    return value


def _stars(value: object) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float):
        raise ValueError("stars must be a number or null")
    stars = float(value)
    if (
        not math.isfinite(stars)
        or not 1.0 <= stars <= 5.0
        or stars * 2 != int(stars * 2)
    ):
        raise ValueError("stars must be from 1 to 5 in half-star steps")
    return stars


def _review_date(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("review_date must be an ISO date string or null")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("review_date must use YYYY-MM-DD") from exc


def _categories(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("categories must be a list of strings or null")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError("categories must contain only non-blank strings")
    return list(value)


def _prepared_review(record: dict[str, object]) -> PreparedReview:
    if set(record) != set(PREPARED_REVIEW_FIELDS):
        missing = sorted(set(PREPARED_REVIEW_FIELDS) - set(record))
        extra = sorted(set(record) - set(PREPARED_REVIEW_FIELDS))
        raise ValueError(
            "prepared-review fields do not match schema; "
            f"missing={missing}, extra={extra}"
        )
    return cast(
        PreparedReview,
        {
            "doc_id": _required_text(record, "doc_id"),
            "text": _required_text(record, "text"),
            "user_id": _optional_text(record, "user_id"),
            "stars": _stars(record["stars"]),
            "review_date": _review_date(record["review_date"]),
            "business_id": _optional_text(record, "business_id"),
            "business_name": _optional_text(record, "business_name"),
            "categories": _categories(record["categories"]),
            "city": _optional_text(record, "city"),
            "state": _optional_text(record, "state"),
        },
    )


class JsonlPreparedReviewReader:
    """Re-openable streaming reader for the canonical prepared JSONL file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def iter_reviews(self) -> Iterator[PreparedReview]:
        try:
            with self.path.open("r", encoding="utf-8") as source:
                for line_number, line in enumerate(source, 1):
                    try:
                        if not line.strip():
                            raise ValueError("blank JSONL line")
                        value = json.loads(
                            line,
                            object_pairs_hook=_object_without_duplicates,
                            parse_constant=_reject_constant,
                        )
                        if not isinstance(value, dict):
                            raise ValueError("each line must be a JSON object")
                        yield _prepared_review(value)
                    except (ValueError, RecursionError) as exc:
                        raise YelpDataError(
                            f"{self.path}:{line_number}: {exc}"
                        ) from exc
        except UnicodeDecodeError as exc:
            raise YelpDataError(f"{self.path}: invalid UTF-8") from exc
