"""Approved boundaries for shared tokenization and filtered token analysis."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class AnalyzedToken(Protocol):
    """One occurrence returned by the public analysis pipeline."""

    term: str
    tags: frozenset[str]


class Tokenizer(Protocol):
    """Canonical term segmentation consumed across group boundaries."""

    def tokenize(self, text: str) -> list[str]: ...

    def fingerprint(self) -> str: ...


class TokenizerPipeline(Tokenizer, Protocol):
    """Canonical tokenizer plus optional POS tagging and type filtering."""

    def analyze(self, text: str) -> Sequence[AnalyzedToken]: ...

    def terms(self, text: str) -> list[str]: ...
