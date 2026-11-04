from __future__ import annotations

import pytest

from yelptext.cli import build_parser
from yelptext.command.data_corpus_analysis import (
    run_heaps_analysis,
    run_tokenizer_comparison,
    run_zipf_analysis,
)
from yelptext.implementation.data_corpus_analysis.heaps import fit_heaps
from yelptext.implementation.data_corpus_analysis.tokenizer import RegexTokenizer
from yelptext.implementation.data_corpus_analysis.tokenizer_comparison import (
    compare_tokenizers,
)


class TinyReader:
    def iter_reviews(self):
        yield {"text": "Great service! Don't wait."}
        yield {"text": "Visit https://example.com 😊"}


def test_fit_heaps_recovers_exact_power_law() -> None:
    expected_k = 7.5
    expected_beta = 0.6
    points = [
        {"N": token_count, "V": expected_k * token_count**expected_beta}
        for token_count in (100, 1_000, 10_000, 100_000)
    ]

    model = fit_heaps(points)

    assert model["k"] == pytest.approx(expected_k)
    assert model["beta"] == pytest.approx(expected_beta)
    assert model["r_squared_log_space"] == pytest.approx(1.0)
    assert model["checkpoints"] == 4


@pytest.mark.parametrize(
    "points",
    [
        [{"N": 100, "V": 20}],
        [{"N": 100, "V": 20}, {"N": 100, "V": 25}],
    ],
)
def test_fit_heaps_rejects_insufficient_distinct_checkpoints(points) -> None:
    with pytest.raises(ValueError, match="distinct positive-token checkpoints"):
        fit_heaps(points)


def test_zipf_and_heaps_are_registered_as_cli_commands() -> None:
    parser = build_parser()

    zipf = parser.parse_args(["analyze", "zipf", "--config", "full.toml"])
    heaps = parser.parse_args(
        [
            "analyze",
            "heaps",
            "--config",
            "full.toml",
            "--seed",
            "17",
            "--keep-random-order",
        ]
    )
    tokenizers = parser.parse_args(
        ["analyze", "tokenizers", "--config", "full.toml"]
    )

    assert zipf.handler is run_zipf_analysis
    assert zipf.command_path == ["analyze", "zipf"]
    assert heaps.handler is run_heaps_analysis
    assert heaps.command_path == ["analyze", "heaps"]
    assert heaps.seed == 17
    assert heaps.keep_random_order is True
    assert tokenizers.handler is run_tokenizer_comparison
    assert tokenizers.command_path == ["analyze", "tokenizers"]


def test_tokenizer_comparison_writes_complete_artifacts_from_tiny_reader(
    tmp_path,
) -> None:
    result = compare_tokenizers(
        TinyReader(),
        RegexTokenizer(),
        tmp_path / "sample.jsonl",
        tmp_path / "output",
        expected_reviews=2,
        benchmark_reviews=2,
        benchmark_repeats=1,
    )

    assert result["status"] == "COMPLETED"
    assert [row["tokenizer"] for row in result["results"]] == [
        "NLTK Whitespace",
        "NLTK WordPunct",
        "Custom Yelp",
    ]
    for name in (
        "summary.json",
        "summary.csv",
        "runtime_benchmark.csv",
        "qualitative_cases.csv",
        "tokenizer_comparison.png",
    ):
        assert (tmp_path / "output" / name).is_file()
