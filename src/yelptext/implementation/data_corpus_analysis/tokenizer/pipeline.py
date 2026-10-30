"""Shared facade composing tokenization, classification, filtering, and lookup."""

from __future__ import annotations

import json
from collections.abc import Iterable

from .classification import TokenClassifier, TokenFilter
from .models import ClassifiedToken, MappedToken
from .pos import PosTagger
from .tokenizer import RegexTokenizer
from .vocabulary import VocabularyLookup


class TokenizerPipeline:
    def __init__(
        self,
        tokenizer: RegexTokenizer | None = None,
        classifier: TokenClassifier | None = None,
        pos_tagger: PosTagger | None = None,
        token_filter: TokenFilter | None = None,
        vocabulary_lookup: VocabularyLookup | None = None,
    ) -> None:
        self.tokenizer = tokenizer or RegexTokenizer()
        self.classifier = classifier or TokenClassifier()
        self.pos_tagger = pos_tagger
        self.token_filter = token_filter or TokenFilter()
        self.vocabulary_lookup = vocabulary_lookup
        if self.token_filter.allow_pos and self.pos_tagger is None:
            raise ValueError("A POS-aware TokenFilter requires an enabled PosTagger")
        if vocabulary_lookup is not None:
            built_with = vocabulary_lookup.vocabulary.metadata.get(
                "tokenizer_fingerprint"
            )
            if built_with and built_with != self.tokenizer.fingerprint():
                raise ValueError(
                    "Vocabulary was built with a different tokenizer fingerprint"
                )
            vocabulary_skips = frozenset(
                vocabulary_lookup.vocabulary.metadata.get("skip_types", ())
            )
            missing_runtime_skips = vocabulary_skips - self.token_filter.skip_types
            if missing_runtime_skips:
                raise ValueError(
                    "Vocabulary omitted token types that this pipeline does not "
                    f"filter: {sorted(missing_runtime_skips)}"
                )

    def tokenize(self, text: str) -> list[str]:
        """Shared-protocol method returning vocabulary-independent terms."""

        return self.tokenizer.tokenize(text)

    def analyze(self, text: str) -> list[ClassifiedToken]:
        classified = self.classifier.classify(self.tokenize(text))
        if self.pos_tagger is not None:
            classified = self.pos_tagger.tag(classified)
        return self.token_filter.filter(classified)

    def terms(self, text: str) -> list[str]:
        """Return term strings after optional POS tagging and filtering."""

        return [token.term for token in self.analyze(text)]

    def process(self, text: str) -> list[ClassifiedToken] | list[MappedToken]:
        analyzed = self.analyze(text)
        if self.vocabulary_lookup is None:
            return analyzed
        return self.vocabulary_lookup.lookup(analyzed)

    def fingerprint(self) -> str:
        payload = {
            "tokenizer": self.tokenizer.fingerprint(),
            "stop_words": sorted(self.classifier.stop_words),
            "pos_tagger": (
                self.pos_tagger.fingerprint() if self.pos_tagger is not None else None
            ),
            "skip_types": sorted(self.token_filter.skip_types),
            "vocabulary_fingerprint": (
                self.vocabulary_lookup.vocabulary.fingerprint()
                if self.vocabulary_lookup
                else None
            ),
            "oov_policy": (
                self.vocabulary_lookup.oov_policy if self.vocabulary_lookup else None
            ),
        }
        return "tokenizer-pipeline|" + json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )


def create_pipeline(
    *,
    skip_types: Iterable[str] = (),
    enable_pos: bool = False,
    vocabulary_lookup: VocabularyLookup | None = None,
) -> TokenizerPipeline:
    pos_tagger = PosTagger() if enable_pos else None
    return TokenizerPipeline(
        classifier=TokenClassifier(),
        pos_tagger=pos_tagger,
        token_filter=TokenFilter(skip_types, allow_pos=enable_pos),
        vocabulary_lookup=vocabulary_lookup,
    )
