"""Register data preparation and corpus-analysis commands."""

from __future__ import annotations

import argparse

from yelptext.cli._common import add_config_argument, use_placeholder


def register(subparsers: argparse._SubParsersAction) -> None:
    prepare = subparsers.add_parser(
        "prepare", help="Validate and prepare Yelp JSONL data"
    )
    add_config_argument(prepare)
    use_placeholder(prepare, "prepare")

    analyze = subparsers.add_parser(
        "analyze", help="Run corpus-analysis experiments"
    )
    analyses = analyze.add_subparsers(dest="analysis", required=True)
    for name, help_text in (
        ("zipf", "Validate Zipf's law"),
        ("heaps", "Estimate Heaps' law parameters"),
        ("tokenizers", "Compare custom and baseline tokenizers"),
    ):
        child = analyses.add_parser(name, help=help_text)
        add_config_argument(child)
        use_placeholder(child, "analyze", name)
