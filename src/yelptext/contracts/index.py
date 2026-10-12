"""Proposed read-only index contract; not yet approved by the team."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class Posting(Protocol):
    """Suggested posting fields used by rankers."""

    review_id: str
    term_frequency: int
    positions: tuple[int, ...]


class IndexReader(Protocol):
    """Suggested interface implemented by fixture and persisted indexes."""

    document_count: int
    average_document_length: float
    tokenizer_fingerprint: str

    def postings(self, term: str) -> Sequence[Posting]: ...

    def document_length(self, review_id: str) -> int: ...
