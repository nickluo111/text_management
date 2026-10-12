"""Register the independent NLP/IR application commands."""

from __future__ import annotations

import argparse

from yelptext.commands._common import add_config_argument, use_placeholder


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("app", help="Run the small NLP/IR application")
    commands = parser.add_subparsers(dest="app_command", required=True)
    comparisons = commands.add_parser(
        "comparisons", help="Detect comparison sentences in reviews"
    )
    comparisons.add_argument("--limit", type=int, default=20)
    add_config_argument(comparisons)
    use_placeholder(comparisons, "app", "comparisons")
