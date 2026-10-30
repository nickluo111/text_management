"""Shared vocabulary construction, persistence, and term lookup."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .classification import TokenClassifier, TokenFilter
from .models import ClassifiedToken, MappedToken
from .pos import POS_TAGS, PosTagger
from .tokenizer import RegexTokenizer


UNK_TERM = "<UNK>"
UNK_ID = 0


@dataclass(frozen=True, slots=True)
class VocabularyEntry:
    term: str
    term_id: int
    cf: int
    df: int
    tags: frozenset[str]
    pos_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "term_id": self.term_id,
            "cf": self.cf,
            "df": self.df,
            "tags": sorted(self.tags),
            "pos_counts": dict(sorted(self.pos_counts.items())),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VocabularyEntry":
        return cls(
            term=str(data["term"]),
            term_id=int(data["term_id"]),
            cf=int(data["cf"]),
            df=int(data["df"]),
            tags=frozenset(data.get("tags", ())),
            pos_counts={str(k): int(v) for k, v in data.get("pos_counts", {}).items()},
        )


class Vocabulary:
    SCHEMA_VERSION = "1.0"

    def __init__(self, entries: Sequence[VocabularyEntry], metadata: dict[str, Any]) -> None:
        self.entries = tuple(entries)
        self.metadata = dict(metadata)
        self._by_term = {entry.term: entry for entry in entries}
        self._by_id = {entry.term_id: entry for entry in entries}
        if UNK_TERM not in self._by_term or self._by_term[UNK_TERM].term_id != UNK_ID:
            raise ValueError(f"Vocabulary must reserve {UNK_TERM!r} as term_id {UNK_ID}")
        if len(self._by_term) != len(entries) or len(self._by_id) != len(entries):
            raise ValueError("Vocabulary terms and term IDs must be unique")

    def get(self, term: str) -> VocabularyEntry | None:
        return self._by_term.get(term)

    def get_by_id(self, term_id: int) -> VocabularyEntry | None:
        return self._by_id.get(term_id)

    def fingerprint(self) -> str:
        identifier = self.metadata.get("vocabulary_id")
        if identifier:
            return str(identifier)
        return (
            f"json-vocabulary|schema={self.SCHEMA_VERSION}|"
            f"documents={self.metadata.get('document_count', 0)}|"
            f"entries={len(self.entries)}"
        )

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "metadata": self.metadata,
            "entries": [entry.to_dict() for entry in self.entries],
        }
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: str | Path) -> "Vocabulary":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema_version") != cls.SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported vocabulary schema: {payload.get('schema_version')!r}"
            )
        entries = [VocabularyEntry.from_dict(item) for item in payload["entries"]]
        return cls(entries, payload.get("metadata", {}))


class VocabularyBuilder:
    """Build a deterministic vocabulary from an iterable of document texts."""

    def __init__(
        self,
        tokenizer: RegexTokenizer,
        classifier: TokenClassifier,
        token_filter: TokenFilter | None = None,
        pos_tagger: PosTagger | None = None,
        *,
        min_cf: int = 1,
        min_df: int = 1,
    ) -> None:
        if min_cf < 1 or min_df < 1:
            raise ValueError("min_cf and min_df must be positive")
        self.tokenizer = tokenizer
        self.classifier = classifier
        self.token_filter = token_filter or TokenFilter()
        self.pos_tagger = pos_tagger
        if self.token_filter.allow_pos and self.pos_tagger is None:
            raise ValueError("A POS-aware TokenFilter requires an enabled PosTagger")
        self.min_cf = min_cf
        self.min_df = min_df

    def build(self, documents: Iterable[str]) -> Vocabulary:
        cf: Counter[str] = Counter()
        df: Counter[str] = Counter()
        static_tags: dict[str, set[str]] = defaultdict(set)
        pos_counts: dict[str, Counter[str]] = defaultdict(Counter)
        document_count = 0
        total_tokens = 0

        for text in documents:
            document_count += 1
            terms = self.tokenizer.tokenize(text)
            classified = self.classifier.classify(terms)
            if self.pos_tagger is not None:
                classified = self.pos_tagger.tag(classified)
            classified = self.token_filter.filter(classified)
            cf.update(token.term for token in classified)
            df.update({token.term for token in classified})
            total_tokens += len(classified)
            for token in classified:
                static_tags[token.term].update(token.tags - POS_TAGS)
                pos_counts[token.term].update(token.tags & POS_TAGS)

        kept_terms = sorted(
            term
            for term in cf
            if cf[term] >= self.min_cf and df[term] >= self.min_df
        )
        kept_term_set = set(kept_terms)
        pruned_terms = set(cf) - kept_term_set
        entries = [
            VocabularyEntry(
                UNK_TERM,
                UNK_ID,
                0,
                0,
                frozenset({"special", "unknown"}),
                {},
            )
        ]
        entries.extend(
            VocabularyEntry(
                term=term,
                term_id=term_id,
                cf=cf[term],
                df=df[term],
                tags=frozenset(static_tags[term]),
                pos_counts=dict(pos_counts[term]),
            )
            for term_id, term in enumerate(kept_terms, start=1)
        )
        metadata = {
            "tokenizer_fingerprint": self.tokenizer.fingerprint(),
            "document_count": document_count,
            "total_tokens_after_filtering": total_tokens,
            "vocabulary_size_including_unk": len(entries),
            "min_cf": self.min_cf,
            "min_df": self.min_df,
            "pruned_type_count": len(pruned_terms),
            "pruned_token_count": sum(cf[term] for term in pruned_terms),
            "unk_statistics_semantics": (
                "reserved runtime OOV only; pruned terms are not aggregated"
            ),
            "skip_types": sorted(self.token_filter.skip_types),
            "pos_tagging_enabled": self.pos_tagger is not None,
            "pos_tagger_fingerprint": (
                self.pos_tagger.fingerprint() if self.pos_tagger is not None else None
            ),
        }
        metadata["vocabulary_id"] = (
            f"json-vocabulary-v{Vocabulary.SCHEMA_VERSION}-"
            f"d{document_count}-n{total_tokens}-v{len(entries)}"
        )
        return Vocabulary(entries, metadata)


class VocabularyLookup:
    """Map classified occurrences under an explicit OOV policy."""

    def __init__(
        self,
        vocabulary: Vocabulary,
        *,
        oov_policy: Literal["unk", "drop", "error"] = "unk",
    ) -> None:
        if oov_policy not in {"unk", "drop", "error"}:
            raise ValueError(f"Unsupported OOV policy: {oov_policy!r}")
        self.vocabulary = vocabulary
        self.oov_policy = oov_policy

    def lookup(self, tokens: Sequence[ClassifiedToken]) -> list[MappedToken]:
        mapped: list[MappedToken] = []
        unk = self.vocabulary.get(UNK_TERM)
        assert unk is not None
        for token in tokens:
            entry = self.vocabulary.get(token.term)
            is_oov = entry is None
            if is_oov:
                if self.oov_policy == "drop":
                    continue
                if self.oov_policy == "error":
                    raise KeyError(f"Term is not in vocabulary: {token.term!r}")
                entry = unk
            mapped.append(
                MappedToken(
                    term=token.term,
                    term_id=entry.term_id,
                    vocabulary_term=entry.term,
                    cf=entry.cf,
                    df=entry.df,
                    tags=token.tags | entry.tags,
                    is_oov=is_oov,
                )
            )
        return mapped
