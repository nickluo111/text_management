"""Unified command-line interface.

The CLI is deliberately thin. Each command will delegate to an importable
domain module once that module is implemented.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def _not_implemented(args: argparse.Namespace) -> None:
    path = " ".join(getattr(args, "command_path", ["unknown"]))
    print(f"Command '{path}' is scaffolded but not implemented yet.")


def _leaf(parent: argparse._SubParsersAction, name: str, help_text: str) -> None:
    parser = parent.add_parser(name, help=help_text)
    parser.set_defaults(handler=_not_implemented)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yelptext",
        description="Yelp review analysis, retrieval, and trend analysis",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="Validate and prepare Yelp JSONL data")
    prepare.add_argument("--config", default="configs/default.toml")
    prepare.set_defaults(handler=_not_implemented, command_path=["prepare"])

    analyze = commands.add_parser("analyze", help="Run dataset-analysis experiments")
    analyze_commands = analyze.add_subparsers(dest="analysis", required=True)
    for name, help_text in (
        ("zipf", "Validate Zipf's law"),
        ("heaps", "Estimate Heaps' law parameters"),
        ("tokenizers", "Compare custom and baseline tokenizers"),
    ):
        child = analyze_commands.add_parser(name, help=help_text)
        child.add_argument("--config", default="configs/default.toml")
        child.set_defaults(handler=_not_implemented, command_path=["analyze", name])

    index = commands.add_parser("index", help="Manage the inverted index")
    index_commands = index.add_subparsers(dest="index_command", required=True)
    build = index_commands.add_parser("build", help="Build and persist an inverted index")
    build.add_argument("--config", default="configs/default.toml")
    build.set_defaults(handler=_not_implemented, command_path=["index", "build"])

    search = commands.add_parser("search", help="Search reviews or evaluate rankers")
    search.add_argument("query", nargs="?", help="Free-text query")
    search.add_argument("--ranker", choices=("tfidf", "bm25"), default="bm25")
    search.add_argument("--config", default="configs/default.toml")
    search.add_argument("--queries", help="TOML file used for batch evaluation")
    search.set_defaults(handler=_not_implemented, command_path=["search"])

    trend = commands.add_parser("trend", help="Run temporal trend analyses")
    trend_commands = trend.add_subparsers(dest="trend_command", required=True)
    sentiment = trend_commands.add_parser("sentiment", help="Analyze sector sentiment")
    sentiment.add_argument("--sector")
    sentiment.add_argument("--config", default="configs/default.toml")
    sentiment.set_defaults(handler=_not_implemented, command_path=["trend", "sentiment"])
    pmi = trend_commands.add_parser("pmi", help="Analyze term co-occurrence drift")
    pmi.add_argument("--term")
    pmi.add_argument("--config", default="configs/default.toml")
    pmi.set_defaults(handler=_not_implemented, command_path=["trend", "pmi"])

    app = commands.add_parser("app", help="Run the small NLP/IR application")
    app_commands = app.add_subparsers(dest="app_command", required=True)
    comparisons = app_commands.add_parser(
        "comparisons", help="Detect comparison sentences in reviews"
    )
    comparisons.add_argument("--limit", type=int, default=20)
    comparisons.add_argument("--config", default="configs/default.toml")
    comparisons.set_defaults(handler=_not_implemented, command_path=["app", "comparisons"])

    run_all = commands.add_parser("run-all", help="Reproduce all report artifacts")
    run_all.add_argument("--config", default="configs/default.toml")
    run_all.set_defaults(handler=_not_implemented, command_path=["run-all"])
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.handler(args)
