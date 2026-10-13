"""Provisional shared-tokenizer boundary; not yet an approved API."""

from __future__ import annotations

from typing import Protocol


class Tokenizer(Protocol):
    def tokenize(self, text: str) -> list[str]: ...

    def fingerprint(self) -> str: ...
