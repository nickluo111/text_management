"""Register temporal trend-analysis commands."""

from __future__ import annotations

import argparse

from yelptext.commands._common import add_config_argument, use_placeholder


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("trend", help="Run temporal trend analyses")
    commands = parser.add_subparsers(dest="trend_command", required=True)

    sentiment = commands.add_parser("sentiment", help="Analyze sector sentiment")
    sentiment.add_argument("--sector")
    add_config_argument(sentiment)
    use_placeholder(sentiment, "trend", "sentiment")

    pmi = commands.add_parser("pmi", help="Analyze term co-occurrence drift")
    pmi.add_argument("--term")
    add_config_argument(pmi)
    use_placeholder(pmi, "trend", "pmi")
