"""Provisional search schema; this is a proposal, not an approved API."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol, TypedDict

from yelptext.protocol.data_corpus_analysis import PreparedReview, Tokenizer


class SearchHit(TypedDict):
    review_id: str
    score: float
    rank: int


class IndexBuilder(Protocol):
    def build(
        self, reviews: Iterable[PreparedReview], tokenizer: Tokenizer
    ) -> Mapping[str, object]: ...


class SearchIndex(Protocol):
    def search(
        self, query: str, *, ranker: str, top_k: int
    ) -> list[SearchHit]: ...
