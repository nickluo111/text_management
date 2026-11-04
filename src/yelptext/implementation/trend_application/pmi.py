"""Streaming token-window PMI statistics for temporal association drift."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from math import ceil, log2
from typing import Any

from yelptext.protocol.tokenizer import AnalyzedToken, TokenizerPipeline


_EXCLUDED_TAGS = frozenset({"punctuation", "stop_word", "conjunction"})


@dataclass(slots=True)
class _PeriodStats:
    reviews: int = 0
    reviews_with_target: int = 0
    target_occurrences: int = 0
    target_pair_events: int = 0
    total_pair_events: int = 0
    context_counts: Counter[str] = field(default_factory=Counter)
    target_cooccurrences: Counter[str] = field(default_factory=Counter)


def _is_eligible(token: AnalyzedToken) -> bool:
    return "word" in token.tags and token.tags.isdisjoint(_EXCLUDED_TAGS)


def analyze_pmi_drift(
    reviews: Iterable[Mapping[str, Any]],
    pipeline: TokenizerPipeline,
    target_term: str,
    *,
    window_size: int = 5,
    top_n: int = 20,
    min_cooccurrence: int = 10,
    min_cooccurrence_rate: float = 0.001,
    granularity: str = "year",
    start_date: date | None = None,
    end_date: date | None = None,
    progress: Callable[[int], None] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Rank target-context associations independently within each period.

    Every eligible token occurrence is a center in a symmetric positional
    window. PMI marginals and the event total are all measured in directed
    center-to-context pair events. Stop words, conjunctions, and punctuation
    remain in the analyzed sequence for distance but cannot form pair events.
    """
    if granularity not in {"year", "month"}:
        raise ValueError("granularity must be 'year' or 'month'")
    if window_size < 1:
        raise ValueError("window_size must be at least 1")
    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    if min_cooccurrence < 1:
        raise ValueError("min_cooccurrence must be at least 1")
    if not 0.0 <= min_cooccurrence_rate < 1.0:
        raise ValueError("min_cooccurrence_rate must be between 0 and 1")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("start_date must not be after end_date")

    normalized_target = pipeline.tokenize(target_term)
    if len(normalized_target) != 1:
        raise ValueError("target_term must tokenize to exactly one term")
    target = normalized_target[0]
    target_analysis = pipeline.analyze(target_term)
    if len(target_analysis) != 1 or not _is_eligible(target_analysis[0]):
        raise ValueError("target_term must be an eligible non-stop lexical term")

    periods: dict[str, _PeriodStats] = {}
    eligibility_cache: dict[str, bool] = {}
    audit = {
        "reviews_read": 0,
        "reviews_without_date": 0,
        "reviews_outside_date_range": 0,
        "reviews_tokenized": 0,
        "reviews_with_target": 0,
        "target_occurrences": 0,
        "target_pair_events": 0,
        "total_pair_events": 0,
    }

    for review in reviews:
        audit["reviews_read"] += 1
        if progress is not None and audit["reviews_read"] % 250_000 == 0:
            progress(audit["reviews_read"])

        raw_date = review.get("review_date")
        if not isinstance(raw_date, str):
            audit["reviews_without_date"] += 1
            continue
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError:
            audit["reviews_without_date"] += 1
            continue
        if (start_date is not None and parsed_date < start_date) or (
            end_date is not None and parsed_date > end_date
        ):
            audit["reviews_outside_date_range"] += 1
            continue

        text = review.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("prepared review text must be a non-blank string")
        terms = pipeline.tokenize(text)
        audit["reviews_tokenized"] += 1
        period = parsed_date.strftime("%Y" if granularity == "year" else "%Y-%m")
        stats = periods.setdefault(period, _PeriodStats())
        stats.reviews += 1

        eligible: list[bool] = []
        for term in terms:
            allowed = eligibility_cache.get(term)
            if allowed is None:
                term_analysis = pipeline.analyze(term)
                allowed = len(term_analysis) == 1 and _is_eligible(term_analysis[0])
                eligibility_cache[term] = allowed
            eligible.append(allowed)
        prefix = [0]
        for allowed in eligible:
            prefix.append(prefix[-1] + int(allowed))

        review_has_target = False
        for center_index, center_term in enumerate(terms):
            if not eligible[center_index]:
                continue
            start = max(0, center_index - window_size)
            end = min(len(terms), center_index + window_size + 1)
            neighbor_count = prefix[end] - prefix[start] - 1
            stats.total_pair_events += neighbor_count
            stats.context_counts[center_term] += neighbor_count

            if center_term != target:
                continue
            review_has_target = True
            stats.target_occurrences += 1
            stats.target_pair_events += neighbor_count
            for context_index in range(start, end):
                if context_index == center_index or not eligible[context_index]:
                    continue
                context_term = terms[context_index]
                if context_term != target:
                    stats.target_cooccurrences[context_term] += 1

        if review_has_target:
            stats.reviews_with_target += 1

    rows: list[dict[str, object]] = []
    period_summaries: list[dict[str, object]] = []
    for period, stats in sorted(periods.items()):
        effective_min_cooccurrence = max(
            min_cooccurrence,
            ceil(min_cooccurrence_rate * stats.target_pair_events),
        )
        candidates: list[tuple[str, int, float]] = []
        if stats.target_pair_events and stats.total_pair_events:
            for term, pair_count in stats.target_cooccurrences.items():
                if pair_count < effective_min_cooccurrence:
                    continue
                context_count = stats.context_counts[term]
                pmi = log2(
                    pair_count
                    * stats.total_pair_events
                    / (stats.target_pair_events * context_count)
                )
                candidates.append((term, pair_count, pmi))
        candidates.sort(key=lambda item: (-item[2], -item[1], item[0]))
        selected = candidates[:top_n]
        for rank, (term, pair_count, pmi) in enumerate(selected, start=1):
            rows.append(
                {
                    "period": period,
                    "target_term": target,
                    "associated_term": term,
                    "rank": rank,
                    "cooccurrence": pair_count,
                    "target_occurrences": stats.target_occurrences,
                    "target_pair_events": stats.target_pair_events,
                    "context_frequency": stats.context_counts[term],
                    "total_pair_events": stats.total_pair_events,
                    "pmi": pmi,
                }
            )
        period_summaries.append(
            {
                "period": period,
                "reviews": stats.reviews,
                "reviews_with_target": stats.reviews_with_target,
                "target_occurrences": stats.target_occurrences,
                "target_pair_events": stats.target_pair_events,
                "total_pair_events": stats.total_pair_events,
                "effective_min_cooccurrence": effective_min_cooccurrence,
                "candidate_terms": len(candidates),
                "ranked_terms": len(selected),
            }
        )
        audit["reviews_with_target"] += stats.reviews_with_target
        audit["target_occurrences"] += stats.target_occurrences
        audit["target_pair_events"] += stats.target_pair_events
        audit["total_pair_events"] += stats.total_pair_events

    summary: dict[str, object] = {
        "target_term": target,
        "granularity": granularity,
        "window_size": window_size,
        "top_n": top_n,
        "min_cooccurrence": min_cooccurrence,
        "min_cooccurrence_rate": min_cooccurrence_rate,
        "audit": audit,
        "periods": period_summaries,
    }
    return rows, summary


__all__ = ["analyze_pmi_drift"]
