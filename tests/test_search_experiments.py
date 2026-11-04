"""Search experiment diagnostics on independent, hand-counted tiny corpora."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tests.fake.search_engine.data_corpus_analysis import (
    create_review_reader, create_tokenizer_pipeline,
)
from tests.test_search_engine import MemoryReader, review
from yelptext.implementation.search_engine.experiments import run_experiment
from yelptext.interface.search_engine import build_index, load_index


REVIEWS = Path(__file__).parent / "fixtures" / "search_engine" / "reviews.jsonl"


@pytest.fixture
def index(tmp_path):
    pipeline = create_tokenizer_pipeline(skip_types={"punctuation"})
    directory = tmp_path / "index"
    build_index(create_review_reader(REVIEWS), pipeline, directory)
    with load_index(directory, pipeline) as opened:
        yield opened


def test_experiment_reports_counts_coverage_overlap_and_exports(index, tmp_path):
    output = tmp_path / "experiment"
    report = run_experiment(index, ["apple banana", "unknown", "apple unknown", "!!!"], output, repeats=2)
    assert report["corpus"]["document_count"] == 4
    assert report["corpus"]["total_terms"] == 9
    assert json.loads((output / "report.json").read_text(encoding="utf-8")) == report
    assert {path.name for path in output.iterdir()} == {
        "report.json", "rankings.csv", "comparison.csv", "bm25_parameters.csv",
    }

    first = report["queries"][0]
    assert first["known_terms"] == ["apple", "banana"]
    assert first["oov_terms"] == []
    assert first["term_document_frequencies"] == {"apple": 2, "banana": 2}
    assert first["comparison"]["overlap_count"] == 3
    assert first["comparison"]["jaccard"] == 1
    assert first["comparison"]["top1_match"] is True
    assert first["comparison"]["common_rank_shifts"] == [
        {"doc_id": doc_id, "tfidf_rank": rank, "bm25_rank": rank, "shift_to_bm25": 0}
        for rank, doc_id in enumerate(["d1", "d2", "d3"], 1)
    ]
    for ranker in ("tfidf", "bm25"):
        run = first["rankers"][ranker]
        assert [hit["document_length"] for hit in run["results"]] == [3, 2, 4]
        assert run["mean_document_length"] == 3
        assert run["all_query_terms_coverage"] == pytest.approx(1 / 3)
        assert run["results"][0]["all_query_terms_matched"] is True
        assert run["results"][1]["matched_query_terms"] == ["banana"]
        assert run["results"][2]["matched_query_terms"] == ["apple"]
        assert run["results"][0]["text"] == "apple apple banana"
        assert run["results"][0]["business_name"] == "Café 苹果"
        assert len(run["timing"]["runs_ms"]) == 2
        assert 0 <= run["timing"]["min_ms"] <= run["timing"]["median_ms"]

    for position in (1, 3):
        empty = report["queries"][position]
        assert empty["comparison"]["overlap_count"] == 0
        assert empty["comparison"]["jaccard"] is None
        assert empty["comparison"]["top1_match"] is None
        for ranker in ("tfidf", "bm25"):
            assert empty["rankers"][ranker]["results"] == []
            assert empty["rankers"][ranker]["mean_document_length"] is None
            assert empty["rankers"][ranker]["all_query_terms_coverage"] is None
    mixed = report["queries"][2]
    assert mixed["known_terms"] == ["apple"]
    assert mixed["oov_terms"] == ["unknown"]
    for ranker in ("tfidf", "bm25"):
        assert mixed["rankers"][ranker]["mean_document_length"] == 3.5
        assert mixed["rankers"][ranker]["all_query_terms_coverage"] == 0

    with (output / "rankings.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 10  # Three and two matches, each for both rankers.
    assert rows[0]["business_name"] == "Café 苹果"
    assert json.loads(rows[0]["matched_query_terms"]) == ["apple", "banana"]
    with (output / "comparison.csv").open(encoding="utf-8", newline="") as stream:
        comparison_rows = list(csv.DictReader(stream))
    assert len(comparison_rows) == 4
    assert comparison_rows[1]["jaccard"] == ""  # Undefined, not a perfect match.
    with (output / "bm25_parameters.csv").open(encoding="utf-8", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 20


def test_parameter_sensitivity_can_change_the_top_document(tmp_path):
    pipeline = create_tokenizer_pipeline(skip_types={"punctuation"})
    # Long repeated-term review wins with b=0; the short focused review wins
    # under the default length normalization. These are observed rank changes,
    # without pretending one is a human-relevance improvement.
    records = [review("long", "apple apple apple " + "banana " * 17), review("short", "apple")]
    directory = tmp_path / "index"
    build_index(MemoryReader(records), pipeline, directory)
    with load_index(directory, pipeline) as index:
        report = run_experiment(index, ["apple"], tmp_path / "report", top_k=1, repeats=1)
    query = report["queries"][0]
    assert query["rankers"]["bm25"]["results"][0]["doc_id"] == "short"
    no_length_normalization = next(variant for variant in query["bm25_parameters"] if variant["b"] == 0)
    assert no_length_normalization["results"][0]["doc_id"] == "long"
    assert no_length_normalization["overlap_with_default"] == 0
    assert no_length_normalization["default_jaccard"] == 0
    assert no_length_normalization["top1_matches_default"] is False
    baseline = query["bm25_parameters"][0]
    assert baseline["overlap_with_default"] == 1
    assert baseline["default_jaccard"] == 1


@pytest.mark.parametrize("queries", [[], "apple", [""], ["   "], [1], ["apple", "apple"]])
def test_invalid_experiment_queries_do_not_create_output(index, tmp_path, queries):
    output = tmp_path / "invalid"
    with pytest.raises(ValueError):
        run_experiment(index, queries, output)
    assert not output.exists()


@pytest.mark.parametrize("repeats", [0, -1, True, 1.5])
def test_invalid_timing_repeats(index, tmp_path, repeats):
    with pytest.raises(ValueError, match="repeats"):
        run_experiment(index, ["apple"], tmp_path / "invalid", repeats=repeats)


def test_unknown_only_experiment_keeps_csv_headers(index, tmp_path):
    output = tmp_path / "no-results"
    run_experiment(index, ["unknown"], output, repeats=1)
    with (output / "rankings.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert "doc_id" in reader.fieldnames
        assert list(reader) == []

