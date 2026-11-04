from __future__ import annotations

from dataclasses import dataclass

import pytest

from yelptext.implementation.trend_application.pmi import analyze_pmi_drift


@dataclass(frozen=True)
class FakeToken:
    term: str
    tags: frozenset[str]


class FakePipeline:
    def __init__(self, documents: dict[str, list[FakeToken]]) -> None:
        self.documents = documents
        self.term_tokens: dict[str, FakeToken] = {}
        for tokens in documents.values():
            for item in tokens:
                self.term_tokens.setdefault(item.term, item)

    def tokenize(self, text: str) -> list[str]:
        return text.lower().split()

    def analyze(self, text: str) -> list[FakeToken]:
        if text in self.documents:
            return self.documents[text]
        if text in self.term_tokens:
            return [self.term_tokens[text]]
        return [word(term) for term in self.tokenize(text)]

    def terms(self, text: str) -> list[str]:
        return [token.term for token in self.analyze(text)]

    def fingerprint(self) -> str:
        return "fake-pipeline"


def word(term: str, *extra_tags: str) -> FakeToken:
    return FakeToken(term, frozenset({"word", *extra_tags}))


def token(term: str, tag: str) -> FakeToken:
    return FakeToken(term, frozenset({tag}))


def review(text: str, year: int) -> dict[str, object]:
    return {"text": text, "review_date": f"{year}-01-01"}


def test_exact_window_marginals_and_pmi() -> None:
    rows, summary = analyze_pmi_drift(
        [review("food service slow", 2020)],
        FakePipeline({}),
        "service",
        window_size=1,
        min_cooccurrence=1,
        top_n=10,
    )

    assert [row["associated_term"] for row in rows] == ["food", "slow"]
    for row in rows:
        assert row["cooccurrence"] == 1
        assert row["target_occurrences"] == 1
        assert row["target_pair_events"] == 2
        assert row["context_frequency"] == 1
        assert row["total_pair_events"] == 4
        assert row["pmi"] == pytest.approx(1.0)
    assert summary["periods"][0]["total_pair_events"] == 4


def test_review_boundaries_and_repeated_targets() -> None:
    rows, summary = analyze_pmi_drift(
        [
            review("service slow", 2020),
            review("friendly service", 2020),
            review("service slow service", 2020),
        ],
        FakePipeline({}),
        "service",
        window_size=1,
        min_cooccurrence=1,
        top_n=10,
    )

    by_term = {row["associated_term"]: row for row in rows}
    assert set(by_term) == {"friendly", "slow"}
    assert by_term["slow"]["cooccurrence"] == 3
    assert by_term["friendly"]["cooccurrence"] == 1
    assert summary["periods"][0]["target_occurrences"] == 4
    assert summary["periods"][0]["target_pair_events"] == 4
    assert summary["periods"][0]["total_pair_events"] == 8


def test_filtering_preserves_original_token_distance() -> None:
    text = "service was ! slow"
    pipeline = FakePipeline(
        {
            text: [
                word("service"),
                word("was", "stop_word"),
                token("!", "punctuation"),
                word("slow"),
            ]
        }
    )
    rows, summary = analyze_pmi_drift(
        [review(text, 2020)],
        pipeline,
        "service",
        window_size=2,
        min_cooccurrence=1,
        top_n=10,
    )

    assert rows == []
    assert summary["periods"][0]["target_occurrences"] == 1
    assert summary["periods"][0]["target_pair_events"] == 0
    assert summary["periods"][0]["total_pair_events"] == 0


def test_period_statistics_are_independent() -> None:
    rows, summary = analyze_pmi_drift(
        [
            review("service friendly", 2020),
            review("service slow", 2021),
        ],
        FakePipeline({}),
        "service",
        window_size=1,
        min_cooccurrence=1,
        top_n=10,
    )

    assert [(row["period"], row["associated_term"]) for row in rows] == [
        ("2020", "friendly"),
        ("2021", "slow"),
    ]
    assert [period["target_occurrences"] for period in summary["periods"]] == [1, 1]
    assert all(row["pmi"] == pytest.approx(1.0) for row in rows)


def test_minimum_count_top_n_and_deterministic_tie_break() -> None:
    reviews = [review("food service slow", 2020)]
    rows, _ = analyze_pmi_drift(
        reviews,
        FakePipeline({}),
        "service",
        window_size=1,
        min_cooccurrence=1,
        top_n=1,
    )
    assert [row["associated_term"] for row in rows] == ["food"]

    filtered_rows, _ = analyze_pmi_drift(
        reviews,
        FakePipeline({}),
        "service",
        window_size=1,
        min_cooccurrence=2,
        top_n=10,
    )
    assert filtered_rows == []


def test_relative_minimum_uses_target_pair_probability() -> None:
    reviews = [review("food service slow", 2020) for _ in range(10)]
    rows, summary = analyze_pmi_drift(
        reviews,
        FakePipeline({}),
        "service",
        window_size=1,
        min_cooccurrence=1,
        min_cooccurrence_rate=0.6,
        top_n=10,
    )

    # The target produces 20 pair events; each candidate occurs 10 times.
    # The relative threshold is ceil(0.6 * 20) = 12, so both are filtered.
    assert rows == []
    assert summary["periods"][0]["effective_min_cooccurrence"] == 12
