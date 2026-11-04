"""Streaming VADER sentiment aggregation by business sector and period."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from math import sqrt
from statistics import NormalDist
from typing import Any, Protocol

from nltk.sentiment import SentimentIntensityAnalyzer


class SentimentAnalyzer(Protocol):
    def polarity_scores(self, text: str) -> Mapping[str, float]: ...


@dataclass(frozen=True, slots=True)
class SectorDefinition:
    """A report label and the Yelp categories that must all be present."""

    name: str
    required_categories: frozenset[str]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("sector name must be non-blank")
        if not self.required_categories or any(
            not category.strip() for category in self.required_categories
        ):
            raise ValueError("a sector requires at least one non-blank category")


@dataclass(slots=True)
class _Bucket:
    count: int = 0
    mean: float = 0.0
    squared_deviation: float = 0.0
    positive: int = 0
    neutral: int = 0
    negative: int = 0
    star_sum: float = 0.0
    star_count: int = 0

    def add(self, compound: float, stars: object) -> None:
        self.count += 1
        delta = compound - self.mean
        self.mean += delta / self.count
        self.squared_deviation += delta * (compound - self.mean)
        if compound >= 0.05:
            self.positive += 1
        elif compound <= -0.05:
            self.negative += 1
        else:
            self.neutral += 1
        if type(stars) in (int, float):
            self.star_sum += float(stars)
            self.star_count += 1

    def row(
        self,
        *,
        sector: str,
        period: str,
        confidence_level: float,
    ) -> dict[str, object]:
        lower: float | None = None
        upper: float | None = None
        if self.count >= 2:
            sample_variance = self.squared_deviation / (self.count - 1)
            z_score = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
            margin = z_score * sqrt(sample_variance / self.count)
            lower = max(-1.0, self.mean - margin)
            upper = min(1.0, self.mean + margin)
        return {
            "sector": sector,
            "period": period,
            "review_count": self.count,
            "mean_compound": self.mean,
            "compound_ci_lower": lower,
            "compound_ci_upper": upper,
            "positive_share": self.positive / self.count,
            "neutral_share": self.neutral / self.count,
            "negative_share": self.negative / self.count,
            "mean_stars": (
                self.star_sum / self.star_count if self.star_count else None
            ),
        }


def analyze_sector_sentiment(
    reviews: Iterable[Mapping[str, Any]],
    sectors: Sequence[SectorDefinition],
    *,
    granularity: str = "year",
    start_date: date | None = None,
    end_date: date | None = None,
    confidence_level: float = 0.95,
    analyzer: SentimentAnalyzer | None = None,
    progress: Callable[[int], None] | None = None,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Score original review text and aggregate it in constant working memory.

    A sector matches when every category in ``required_categories`` is present.
    A review may contribute to multiple sectors, but VADER scores it only once.
    Confidence intervals use an online normal approximation for the mean.
    """
    if granularity not in {"year", "month"}:
        raise ValueError("granularity must be 'year' or 'month'")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0 and 1")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    if not sectors:
        raise ValueError("at least one sector is required")
    names = [sector.name for sector in sectors]
    if len(set(names)) != len(names):
        raise ValueError("sector names must be unique")

    scorer = analyzer or SentimentIntensityAnalyzer()
    buckets: dict[tuple[str, str], _Bucket] = {}
    audit = {
        "reviews_read": 0,
        "reviews_without_date": 0,
        "reviews_outside_date_range": 0,
        "reviews_without_categories": 0,
        "reviews_not_in_selected_sectors": 0,
        "matched_reviews": 0,
        "multi_sector_reviews": 0,
        "sector_review_assignments": 0,
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

        raw_categories = review.get("categories")
        if not isinstance(raw_categories, list) or not raw_categories:
            audit["reviews_without_categories"] += 1
            continue
        categories = frozenset(raw_categories)
        matching = [
            sector
            for sector in sectors
            if sector.required_categories.issubset(categories)
        ]
        if not matching:
            audit["reviews_not_in_selected_sectors"] += 1
            continue

        text = review.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("prepared review text must be a non-blank string")
        compound = float(scorer.polarity_scores(text)["compound"])
        period = parsed_date.strftime("%Y" if granularity == "year" else "%Y-%m")
        audit["matched_reviews"] += 1
        if len(matching) > 1:
            audit["multi_sector_reviews"] += 1
        audit["sector_review_assignments"] += len(matching)
        for sector in matching:
            bucket = buckets.setdefault((sector.name, period), _Bucket())
            bucket.add(compound, review.get("stars"))

    sector_order = {sector.name: index for index, sector in enumerate(sectors)}
    rows = [
        bucket.row(
            sector=sector,
            period=period,
            confidence_level=confidence_level,
        )
        for (sector, period), bucket in sorted(
            buckets.items(), key=lambda item: (sector_order[item[0][0]], item[0][1])
        )
    ]
    return rows, audit


__all__ = ["SectorDefinition", "analyze_sector_sentiment"]
