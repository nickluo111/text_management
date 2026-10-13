"""Provisional trend/application outputs; not yet an approved API.

Recommended input split: sentiment receives original review strings, PMI also
receives the shared tokenizer, and comparison detection owns sentence
segmentation locally. These recommendations remain subject to schema approval.
"""

from __future__ import annotations

from typing import TypedDict


class SentimentAggregate(TypedDict):
    period: str
    sector: str
    review_count: int
    mean_compound: float


class TermAssociation(TypedDict):
    period: str
    target: str
    term: str
    cooccurrence: int
    pmi: float
    rank: int


class ComparisonMatch(TypedDict):
    review_id: str
    sentence: str
    cue: str
