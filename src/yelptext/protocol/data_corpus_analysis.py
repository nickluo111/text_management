"""Provisional data/corpus schema; this is a proposal, not an approved API."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypedDict


class RawBusiness(TypedDict):
    business_id: str
    name: str
    categories: str | None


class RawReview(TypedDict):
    review_id: str
    user_id: str
    business_id: str
    stars: float
    text: str
    date: str


class PreparedReview(TypedDict):
    review_id: str
    business_id: str
    business_name: str
    categories: list[str]
    stars: float
    text: str
    date: str


class ReviewReader(Protocol):
    def iter_reviews(self) -> Iterable[RawReview]: ...

    def iter_businesses(self) -> Iterable[RawBusiness]: ...


class Tokenizer(Protocol):
    def tokenize(self, text: str) -> list[str]: ...

    def fingerprint(self) -> str: ...
