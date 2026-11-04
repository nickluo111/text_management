"""Tiny, deterministic upstream for testing real search algorithms.

This deliberately has its own fingerprint and a small synthetic token policy.
It is not a replacement for testing the real Yelp tokenizer. No NLTK resources
or full Yelp dataset are needed to exercise indexing and ranking.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import cast

from yelptext.protocol.reviewer import PreparedReview


_FIELDS = frozenset(PreparedReview.__annotations__)
_TYPES = frozenset({"word", "punctuation", "stop_word"})
_POS_TYPES = frozenset({"pos:noun", "pos:other"})
_STOP_WORDS = frozenset({"a", "and", "the"})
_PATTERN = re.compile(r"[^\W_]+(?:'[^\W_]+)*|[!?]", re.UNICODE)


@dataclass(frozen=True)
class AnalyzedToken:
    term: str
    tags: frozenset[str]


class FixtureReviewReader:
    def __init__(self, prepared_path: str | Path) -> None:
        self.path = Path(prepared_path)

    def iter_reviews(self) -> Iterator[PreparedReview]:
        with self.path.open(encoding="utf-8") as stream:
            for line in stream:
                review = json.loads(line)
                if not isinstance(review, dict) or set(review) != _FIELDS:
                    raise ValueError("Fixture reviews require the approved ten fields")
                for field in ("doc_id", "text"):
                    if not isinstance(review[field], str) or not review[field].strip():
                        raise ValueError(f"Fixture {field} must be a nonblank string")
                yield cast(PreparedReview, review)


class FixtureTokenizerPipeline:
    def __init__(
        self, *, skip_types: Iterable[str] = (), enable_pos: bool = False
    ) -> None:
        self.skip_types = frozenset(skip_types)
        self.enable_pos = enable_pos
        unknown = self.skip_types - available_token_types(include_pos=enable_pos)
        if unknown:
            raise ValueError(f"Unsupported fixture token types: {sorted(unknown)}")

    def tokenize(self, text: str) -> list[str]:
        # Like the public contract, tokenize() never applies the filters.
        return _PATTERN.findall(text.lower())

    def analyze(self, text: str) -> list[AnalyzedToken]:
        analyzed = []
        for term in self.tokenize(text):
            punctuation = term in {"!", "?"}
            tags = {"punctuation" if punctuation else "word"}
            if term in _STOP_WORDS:
                tags.add("stop_word")
            if self.enable_pos:
                # Synthetic fixture labels, not a linguistic POS model.
                tags.add("pos:other" if punctuation else "pos:noun")
            if not tags.intersection(self.skip_types):
                analyzed.append(AnalyzedToken(term, frozenset(tags)))
        return analyzed

    def terms(self, text: str) -> list[str]:
        return [token.term for token in self.analyze(text)]

    def fingerprint(self) -> str:
        policy = json.dumps(
            {
                "fixture_policy": "search-algebra-v1",
                "skip_types": sorted(self.skip_types),
                "enable_pos": self.enable_pos,
            },
            sort_keys=True,
        )
        return "fixture:" + hashlib.sha256(policy.encode("utf-8")).hexdigest()


def available_token_types(*, include_pos: bool = False) -> frozenset[str]:
    return _TYPES | (_POS_TYPES if include_pos else frozenset())


def create_review_reader(prepared_path: str | Path) -> FixtureReviewReader:
    return FixtureReviewReader(prepared_path)


def create_tokenizer() -> FixtureTokenizerPipeline:
    return FixtureTokenizerPipeline()


def create_tokenizer_pipeline(
    *, skip_types: Iterable[str] = (), enable_pos: bool = False
) -> FixtureTokenizerPipeline:
    return FixtureTokenizerPipeline(skip_types=skip_types, enable_pos=enable_pos)

