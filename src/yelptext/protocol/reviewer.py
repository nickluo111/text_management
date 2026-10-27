"""Shared prepared-review boundary implemented by Group A.

Raw Yelp record models are intentionally excluded because they are internal to
data preparation. Downstream groups consume only prepared review records.

``date`` is an ISO ``YYYY-MM-DD`` string. ``categories`` is always a list; a
missing Yelp category value becomes an empty list. Business metadata is part
of this boundary because trend analysis needs categories and search results
may need stable business identity/display information.
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
