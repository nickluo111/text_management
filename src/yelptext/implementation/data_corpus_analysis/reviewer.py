"""Stream raw Yelp reviews and attach the agreed business metadata."""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from yelptext.protocol.reviewer import PreparedReview


OrphanPolicy = Literal["error", "skip"]


class YelpDataError(ValueError):
    """A raw JSONL record cannot satisfy the prepared-review protocol."""


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON numeric constant: {value}")


def _read_object(line: str, *, path: Path, line_number: int) -> dict[str, object]:
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
        return value
    except (ValueError, RecursionError) as exc:
        raise YelpDataError(f"{path}:{line_number}: {exc}") from exc


def _required_text(record: dict[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-blank string")
    return value


def _categories(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, str):
        raise ValueError("categories must be a comma-separated string or null")
    return [category.strip() for category in value.split(",") if category.strip()]


def _review_date(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("date must be an ISO date or datetime string")
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError as exc:
        raise ValueError("date must be a valid ISO date or datetime string") from exc


def _stars(value: object) -> float:
    if type(value) not in (int, float):
        raise ValueError("stars must be a number")
    stars = float(value)
    if not math.isfinite(stars) or not 1.0 <= stars <= 5.0:
        raise ValueError("stars must be a finite number from 1 to 5")
    return stars


class YelpReviewReader:
    """Join streamed raw reviews with an in-memory business lookup.

    Yelp's business file is small enough to retain the fields needed by the
    shared protocol. The much larger review file remains streaming. Repeated
    calls to :meth:`iter_reviews` reuse the business lookup and reopen the
    review file.
    """

    def __init__(
        self,
        review_path: str | Path,
        business_path: str | Path,
        *,
        orphan_policy: OrphanPolicy = "error",
    ) -> None:
        if orphan_policy not in {"error", "skip"}:
            raise ValueError("orphan_policy must be 'error' or 'skip'")
        self.review_path = Path(review_path)
        self.business_path = Path(business_path)
        self.orphan_policy = orphan_policy
        self._businesses: dict[str, tuple[str, list[str]]] | None = None

    def _load_businesses(self) -> dict[str, tuple[str, list[str]]]:
        if self._businesses is not None:
            return self._businesses

        businesses: dict[str, tuple[str, list[str]]] = {}
        try:
            with self.business_path.open("r", encoding="utf-8") as source:
                for line_number, line in enumerate(source, 1):
                    try:
                        record = _read_object(
                            line, path=self.business_path, line_number=line_number
                        )
                        business_id = _required_text(record, "business_id")
                        if business_id in businesses:
                            raise ValueError(f"duplicate business_id: {business_id}")
                        businesses[business_id] = (
                            _required_text(record, "name"),
                            _categories(record.get("categories")),
                        )
                    except ValueError as exc:
                        if isinstance(exc, YelpDataError):
                            raise
                        raise YelpDataError(
                            f"{self.business_path}:{line_number}: {exc}"
                        ) from exc
        except UnicodeDecodeError as exc:
            raise YelpDataError(f"{self.business_path}: invalid UTF-8") from exc

        self._businesses = businesses
        return businesses

    def iter_reviews(self) -> Iterator[PreparedReview]:
        businesses = self._load_businesses()
        try:
            with self.review_path.open("r", encoding="utf-8") as source:
                for line_number, line in enumerate(source, 1):
                    try:
                        record = _read_object(
                            line, path=self.review_path, line_number=line_number
                        )
                        review_id = _required_text(record, "review_id")
                        business_id = _required_text(record, "business_id")
                        business = businesses.get(business_id)
                        if business is None:
                            if self.orphan_policy == "skip":
                                continue
                            raise ValueError(
                                f"business_id {business_id!r} has no business record"
                            )
                        business_name, categories = business
                        yield cast(
                            PreparedReview,
                            {
                                "review_id": review_id,
                                "business_id": business_id,
                                "business_name": business_name,
                                "categories": list(categories),
                                "stars": _stars(record.get("stars")),
                                "text": _required_text(record, "text"),
                                "date": _review_date(record.get("date")),
                            },
                        )
                    except ValueError as exc:
                        if isinstance(exc, YelpDataError):
                            raise
                        raise YelpDataError(
                            f"{self.review_path}:{line_number}: {exc}"
                        ) from exc
        except UnicodeDecodeError as exc:
            raise YelpDataError(f"{self.review_path}: invalid UTF-8") from exc
