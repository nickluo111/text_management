from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pytest

from yelptext.implementation.trend_application.sentiment import (
    SectorDefinition,
    analyze_sector_sentiment,
)
from yelptext.command.trend_application import _select_pmi_heatmap_terms


class FakeAnalyzer:
    def __init__(self, scores: Mapping[str, float]) -> None:
        self.scores = scores
        self.seen: list[str] = []

    def polarity_scores(self, text: str) -> dict[str, float]:
        self.seen.append(text)
        return {"compound": self.scores[text]}


def review(
    text: str,
    review_date: str | None,
    categories: list[str] | None,
    stars: float | None = 4.0,
) -> dict[str, object]:
    return {
        "text": text,
        "review_date": review_date,
        "categories": categories,
        "stars": stars,
    }


def test_streaming_sentiment_matches_composite_and_single_category_sectors() -> None:
    sectors = [
        SectorDefinition(
            "Italian Restaurants", frozenset({"Italian", "Restaurants"})
        ),
        SectorDefinition("Fast Food", frozenset({"Fast Food"})),
    ]
    analyzer = FakeAnalyzer({"GREAT!!!": 0.8, "not good": -0.4, "ordinary": 0.0})
    rows, audit = analyze_sector_sentiment(
        [
            review("GREAT!!!", "2020-01-02", ["Italian", "Restaurants"]),
            review("not good", "2020-07-02", ["Fast Food"], 2.0),
            review(
                "ordinary",
                "2021-03-04",
                ["Italian", "Restaurants", "Fast Food"],
                None,
            ),
            review("ignored", "2020-01-01", ["Italian"]),
            review("ignored", None, ["Fast Food"]),
        ],
        sectors,
        analyzer=analyzer,
    )

    assert analyzer.seen == ["GREAT!!!", "not good", "ordinary"]
    assert [(row["sector"], row["period"]) for row in rows] == [
        ("Italian Restaurants", "2020"),
        ("Italian Restaurants", "2021"),
        ("Fast Food", "2020"),
        ("Fast Food", "2021"),
    ]
    assert rows[0]["mean_compound"] == pytest.approx(0.8)
    assert rows[0]["positive_share"] == 1.0
    assert rows[1]["neutral_share"] == 1.0
    assert rows[2]["negative_share"] == 1.0
    assert audit == {
        "reviews_read": 5,
        "reviews_without_date": 1,
        "reviews_outside_date_range": 0,
        "reviews_without_categories": 0,
        "reviews_not_in_selected_sectors": 1,
        "matched_reviews": 3,
        "multi_sector_reviews": 1,
        "sector_review_assignments": 4,
    }


def test_online_confidence_interval_and_date_filter() -> None:
    analyzer = FakeAnalyzer({"positive": 1.0, "negative": -1.0})
    rows, audit = analyze_sector_sentiment(
        [
            review("positive", "2019-12-31", ["Fast Food"]),
            review("positive", "2020-01-01", ["Fast Food"]),
            review("negative", "2020-12-31", ["Fast Food"]),
            review("negative", "2021-01-01", ["Fast Food"]),
        ],
        [SectorDefinition("Fast Food", frozenset({"Fast Food"}))],
        start_date=date(2020, 1, 1),
        end_date=date(2020, 12, 31),
        analyzer=analyzer,
    )

    assert len(rows) == 1
    assert rows[0]["review_count"] == 2
    assert rows[0]["mean_compound"] == pytest.approx(0.0)
    assert rows[0]["compound_ci_lower"] == -1.0
    assert rows[0]["compound_ci_upper"] == 1.0
    assert audit["reviews_outside_date_range"] == 2


@pytest.mark.parametrize("granularity", ["week", "quarter"])
def test_rejects_unsupported_granularity(granularity: str) -> None:
    with pytest.raises(ValueError, match="granularity"):
        analyze_sector_sentiment(
            [],
            [SectorDefinition("Fast Food", frozenset({"Fast Food"}))],
            granularity=granularity,
            analyzer=FakeAnalyzer({}),
        )


def test_heatmap_terms_prefer_cross_period_persistence() -> None:
    rows: list[dict[str, object]] = []
    for period in ("2018", "2019", "2020", "2021"):
        rows.append(
            {
                "period": period,
                "associated_term": "stable",
                "rank": 5,
                "pmi": 2.0,
            }
        )
    rows.append(
        {
            "period": "2021",
            "associated_term": "one_year_spike",
            "rank": 1,
            "pmi": 9.0,
        }
    )

    assert _select_pmi_heatmap_terms(rows) == ["stable"]
