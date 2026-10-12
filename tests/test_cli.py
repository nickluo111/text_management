"""CLI registration and dispatch tests."""

from __future__ import annotations

import pytest

from yelptext.cli import build_parser, main


@pytest.mark.parametrize(
    ("argv", "expected_path"),
    [
        (["prepare"], ["prepare"]),
        (["analyze", "zipf"], ["analyze", "zipf"]),
        (["analyze", "heaps"], ["analyze", "heaps"]),
        (["analyze", "tokenizers"], ["analyze", "tokenizers"]),
        (["index", "build"], ["index", "build"]),
        (["search", "good service"], ["search"]),
        (["trend", "sentiment"], ["trend", "sentiment"]),
        (["trend", "pmi"], ["trend", "pmi"]),
        (["app", "comparisons"], ["app", "comparisons"]),
        (["run-all"], ["run-all"]),
    ],
)
def test_registered_command_paths(argv: list[str], expected_path: list[str]) -> None:
    args = build_parser().parse_args(argv)
    assert args.command_path == expected_path
    assert callable(args.handler)


def test_search_options_are_preserved() -> None:
    args = build_parser().parse_args(
        ["search", "great noodles", "--ranker", "tfidf", "--queries", "queries.toml"]
    )
    assert args.query == "great noodles"
    assert args.ranker == "tfidf"
    assert args.queries == "queries.toml"
    assert args.config == "configs/default.toml"


def test_placeholder_dispatch(capsys: pytest.CaptureFixture[str]) -> None:
    main(["trend", "pmi", "--term", "service"])
    assert capsys.readouterr().out == (
        "Command 'trend pmi' is scaffolded but not implemented yet.\n"
    )
