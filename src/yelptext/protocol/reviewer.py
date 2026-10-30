"""Shared prepared-review boundary implemented by Group A.

Downstream groups consume normalized review records and do not depend on the
layout of Yelp's raw ``review.json`` and ``business.json`` files.

Every record contains the same ten keys. ``doc_id`` and ``text`` are required
non-blank strings; unavailable optional values are represented by ``None``.
``review_date`` is an ISO ``YYYY-MM-DD`` date. ``categories=None`` means the
business categories are unknown, while ``categories=[]`` means they are known
to be empty.

``user_id`` and ``state`` are deliberately retained as small, useful pieces of
redundancy: the former permits reviewer-level robustness checks and the latter
disambiguates cities. Yelp engagement votes and mutable business snapshots are
not part of the cross-group contract.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypedDict


PREPARED_REVIEW_SCHEMA_VERSION = "2.0"


class PreparedReview(TypedDict):
    doc_id: str
    text: str
    user_id: str | None
    stars: float | None
    review_date: str | None
    business_id: str | None
    business_name: str | None
    categories: list[str] | None
    city: str | None
    state: str | None


class PreparedReviewReader(Protocol):
    def iter_reviews(self) -> Iterable[PreparedReview]: ...
