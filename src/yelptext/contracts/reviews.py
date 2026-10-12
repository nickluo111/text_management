"""Proposed review-stream contract; not yet approved by the team."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Protocol


class PreparedReview(Protocol):
    """Suggested fields exposed to downstream groups.

    The team must still confirm field names, serialized date representation,
    category representation, nullability, and orphan-review policy.
    """

    review_id: str
    business_id: str
    business_name: str
    text: str
    stars: float
    date: datetime
    categories: tuple[str, ...]


class ReviewReader(Protocol):
    """Suggested streaming provider shared by fake and real readers."""

    def __iter__(self) -> Iterator[PreparedReview]: ...
