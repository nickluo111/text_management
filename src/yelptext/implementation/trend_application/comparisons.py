"""Lightweight detection of cross-business comparison sentences."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from yelptext.protocol.tokenizer import TokenizerPipeline


_BUSINESS_REFERENCES = {
    "restaurant", "restaurants", "place", "places", "business", "businesses",
    "store", "stores", "shop", "shops", "cafe", "cafes", "diner", "diners",
    "chain", "chains", "competitor", "competitors", "spot", "spots",
    "location", "locations", "elsewhere",
}
_COMPARATIVES = {
    "better", "worse", "cheaper", "pricier", "faster", "slower", "cleaner",
    "friendlier", "closer", "larger", "smaller", "higher", "lower", "bigger",
    "nicer", "tastier", "healthier", "quicker",
}


def split_sentences(text: str) -> list[str]:
    """Split review text at ordinary sentence endings and line breaks."""

    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]


def _business_reference(terms: list[str]) -> bool:
    values = set(terms)
    return bool(values & _BUSINESS_REFERENCES) or (
        "anywhere" in values and "else" in values
    )


def comparison_pattern(sentence: str, tokenizer: TokenizerPipeline) -> str | None:
    """Return the matched comparison pattern, or ``None``."""

    terms = tokenizer.terms(sentence)
    if len(terms) < 3:
        return None

    for left, right, label in (
        ("compared", "to", "compared_to"),
        ("compared", "with", "compared_with"),
        ("similar", "to", "similar_to"),
    ):
        for index in range(len(terms) - 1):
            if terms[index : index + 2] == [left, right] and _business_reference(terms[index + 2 : index + 12]):
                return label

    for connector in ("unlike", "versus", "vs"):
        if connector in terms:
            index = terms.index(connector)
            if _business_reference(terms[index + 1 : index + 11]):
                return "explicit_comparison"

    if "than" in terms:
        index = terms.index("than")
        before, after = terms[:index], terms[index + 1 :]
        comparative = any(term in _COMPARATIVES for term in before[-4:]) or any(
            term in {"more", "less"} for term in before[-3:]
        )
        if comparative and _business_reference(after[:6]):
            return "comparative_than"

    if "prefer" in terms and "over" in terms and _business_reference(terms[terms.index("over") + 1 :]):
        return "prefer_over"

    if any(term in terms for term in ("best", "worst")) and any(
        term in terms for term in ("ever", "tried", "visited", "been")
    ):
        return "experience_superlative"
    return None


def scan_comparisons(
    reviews: Iterable[Mapping[str, Any]],
    tokenizer: TokenizerPipeline,
    on_match: Callable[[dict[str, object]], None],
    *,
    limit: int | None = None,
    progress: Callable[[int], None] | None = None,
) -> dict[str, object]:
    """Stream reviews, emit comparison sentences, and return aggregate counts."""

    reviews_scanned = sentences_scanned = matched_reviews = matched_sentences = 0
    patterns: dict[str, int] = {}
    for review in reviews:
        if limit is not None and reviews_scanned >= limit:
            break
        reviews_scanned += 1
        if progress is not None and reviews_scanned % 250_000 == 0:
            progress(reviews_scanned)
        review_matched = False
        for sentence_index, sentence in enumerate(split_sentences(str(review["text"])), 1):
            sentences_scanned += 1
            pattern = comparison_pattern(sentence, tokenizer)
            if pattern is None:
                continue
            review_matched = True
            matched_sentences += 1
            patterns[pattern] = patterns.get(pattern, 0) + 1
            on_match({
                "doc_id": review.get("doc_id", ""),
                "business_id": review.get("business_id", ""),
                "business_name": review.get("business_name", ""),
                "review_date": review.get("review_date", ""),
                "stars": review.get("stars", ""),
                "sentence_index": sentence_index,
                "pattern": pattern,
                "sentence": sentence,
            })
        matched_reviews += int(review_matched)
    return {
        "reviews_scanned": reviews_scanned,
        "sentences_scanned": sentences_scanned,
        "matched_reviews": matched_reviews,
        "matched_sentences": matched_sentences,
        "patterns": dict(sorted(patterns.items())),
    }


__all__ = ["comparison_pattern", "scan_comparisons", "split_sentences"]
