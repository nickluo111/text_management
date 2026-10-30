"""Typed values exchanged by the shared tokenizer pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenSpan:
    """A token and its half-open offsets in normalized text."""

    term: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class ClassifiedToken:
    term: str
    tags: frozenset[str]


@dataclass(frozen=True, slots=True)
class MappedToken:
    """A token occurrence mapped to the fixed vocabulary."""

    term: str
    term_id: int
    vocabulary_term: str
    cf: int
    df: int
    tags: frozenset[str]
    is_oov: bool
