"""Proposed tokenizer contract; not yet approved by the team."""

from __future__ import annotations

from typing import Protocol


class Tokenizer(Protocol):
    """Suggested interface implemented by fixture and real tokenizers."""

    def tokenize(self, text: str) -> list[str]: ...

    def fingerprint(self) -> str: ...
