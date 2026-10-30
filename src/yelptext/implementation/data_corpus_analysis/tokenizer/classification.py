"""Shared token classification and configurable type filtering."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from .models import ClassifiedToken
from .pos import POS_TAGS
from .stop_words import CONJUNCTIONS, load_nltk_stop_words
from .tokenizer import (
    EMAIL_PATTERN,
    EMOJI_PATTERN,
    EMOTICON_PATTERN,
    HASHTAG_PATTERN,
    MONEY_PATTERN,
    NUMBER_PATTERN,
    PERCENTAGE_PATTERN,
    QUANTITY_PATTERN,
    TEMPERATURE_PATTERN,
    URL_PATTERN,
)


STABLE_TOKEN_TYPES = frozenset(
    {
        "word",
        "stop_word",
        "conjunction",
        "url",
        "email",
        "emoticon",
        "emoji",
        "number",
        "money",
        "percentage",
        "temperature",
        "hashtag",
        "punctuation",
    }
)

_STRUCTURAL_PATTERNS = (
    (frozenset({"url"}), re.compile(rf"^(?:{URL_PATTERN})$", re.IGNORECASE)),
    (frozenset({"email"}), re.compile(rf"^(?:{EMAIL_PATTERN})$", re.IGNORECASE)),
    (frozenset({"emoticon"}), re.compile(rf"^(?:{EMOTICON_PATTERN})$", re.IGNORECASE)),
    (frozenset({"emoji"}), re.compile(rf"^(?:{EMOJI_PATTERN})$")),
    (frozenset({"money", "number"}), re.compile(rf"^(?:{MONEY_PATTERN})$")),
    (
        frozenset({"percentage", "number"}),
        re.compile(rf"^(?:{PERCENTAGE_PATTERN})$"),
    ),
    (
        frozenset({"temperature", "number"}),
        re.compile(rf"^(?:{TEMPERATURE_PATTERN})$", re.IGNORECASE),
    ),
    (frozenset({"number"}), re.compile(rf"^(?:{QUANTITY_PATTERN})$")),
    (frozenset({"number"}), re.compile(rf"^(?:{NUMBER_PATTERN})$")),
    (frozenset({"hashtag"}), re.compile(rf"^(?:{HASHTAG_PATTERN})$", re.UNICODE)),
    (frozenset({"punctuation"}), re.compile(r"^[!?#]$")),
)


class TokenClassifier:
    """Add stable structural and lexical tags; POS is a separate component."""

    def __init__(
        self,
        *,
        stop_words: Iterable[str] | None = None,
    ) -> None:
        self.stop_words = (
            frozenset(stop_words) if stop_words is not None else load_nltk_stop_words()
        )

    def classify(self, terms: Sequence[str]) -> list[ClassifiedToken]:
        return [
            ClassifiedToken(term=term, tags=frozenset(self._static_tags(term)))
            for term in terms
        ]

    def _static_tags(self, term: str) -> set[str]:
        tags: set[str] = set()
        for labels, pattern in _STRUCTURAL_PATTERNS:
            if pattern.fullmatch(term):
                tags.update(labels)
                break
        if not tags:
            tags.add("word")
        if term in self.stop_words:
            tags.add("stop_word")
        if term in CONJUNCTIONS:
            tags.add("conjunction")
        return tags


class TokenFilter:
    """Remove occurrences carrying any configured tag."""

    def __init__(
        self,
        skip_types: Iterable[str] = (),
        *,
        allow_pos: bool = False,
    ) -> None:
        self.skip_types = frozenset(skip_types)
        pos_types = self.skip_types & POS_TAGS
        if pos_types and not allow_pos:
            raise ValueError(
                "POS skip types require an enabled PosTagger: "
                f"{sorted(pos_types)}"
            )
        allowed_types = STABLE_TOKEN_TYPES | (POS_TAGS if allow_pos else frozenset())
        unknown_types = self.skip_types - allowed_types
        if unknown_types:
            raise ValueError(f"Unknown skip types: {sorted(unknown_types)}")
        self.allow_pos = allow_pos

    def filter(self, tokens: Sequence[ClassifiedToken]) -> list[ClassifiedToken]:
        if not self.skip_types:
            return list(tokens)
        return [token for token in tokens if token.tags.isdisjoint(self.skip_types)]
