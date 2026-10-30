"""Approved boundary for the shared, vocabulary-independent tokenizer."""

from __future__ import annotations

from typing import Protocol


class Tokenizer(Protocol):
    """Canonical term segmentation consumed across group boundaries."""

    def tokenize(self, text: str) -> list[str]: ...

    def fingerprint(self) -> str: ...
