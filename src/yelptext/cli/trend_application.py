"""Register trend-analysis and small-application commands."""

from __future__ import annotations

import argparse

from yelptext.cli._common import add_config_argument, use_placeholder


def register(subparsers: argparse._SubParsersAction) -> None:
    trend = subparsers.add_parser("trend", help="Run temporal trend analyses")
    trend_commands = trend.add_subparsers(dest="trend_command", required=True)

    sentiment = trend_commands.add_parser(
        "sentiment", help="Analyze sector sentiment"
    )
    sentiment.add_argument("--sector")
    add_config_argument(sentiment)
    use_placeholder(sentiment, "trend", "sentiment")

    pmi = trend_commands.add_parser("pmi", help="Analyze term co-occurrence drift")
    pmi.add_argument("--term")
    add_config_argument(pmi)
    use_placeholder(pmi, "trend", "pmi")

    app = subparsers.add_parser("app", help="Run the small NLP/IR application")
    app_commands = app.add_subparsers(dest="app_command", required=True)
    comparisons = app_commands.add_parser(
        "comparisons", help="Detect comparison sentences in reviews"
    )
    comparisons.add_argument("--limit", type=int, default=20)
    add_config_argument(comparisons)
    use_placeholder(comparisons, "app", "comparisons")
