"""Provisional prepared-review boundary; not yet an approved API.

Raw Yelp record models are intentionally excluded because they are internal to
data preparation. Downstream groups consume only prepared review records.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypedDict


class PreparedReview(TypedDict):
    review_id: str
    business_id: str
    business_name: str
    categories: list[str]
    stars: float
    text: str
    date: str


class PreparedReviewReader(Protocol):
    def iter_reviews(self) -> Iterable[PreparedReview]: ...
