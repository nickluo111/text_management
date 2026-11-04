"""Register trend-analysis and small-application commands."""

from __future__ import annotations

import argparse

from yelptext.cli._common import add_config_argument
from yelptext.command import trend_application as trend_command_impl


def register(subparsers: argparse._SubParsersAction) -> None:
    trend = subparsers.add_parser("trend", help="Run temporal trend analyses")
    trend_commands = trend.add_subparsers(dest="trend_command", required=True)

    sentiment = trend_commands.add_parser(
        "sentiment", help="Analyze sector sentiment"
    )
    sentiment.add_argument(
        "--sectors",
        help="Comma-separated configured sector names (default: all configured)",
    )
    sentiment.add_argument(
        "--input", help="Prepared review JSONL (default: [data].prepared_path)"
    )
    sentiment.add_argument(
        "--output-dir",
        help="Artifact directory (default: [trends.sentiment].output_dir)",
    )
    sentiment.add_argument("--start-date", help="Inclusive YYYY-MM-DD lower bound")
    sentiment.add_argument("--end-date", help="Inclusive YYYY-MM-DD upper bound")
    sentiment.add_argument(
        "--time-granularity", choices=("year", "month"), help="Override configuration"
    )
    add_config_argument(sentiment)
    sentiment.set_defaults(handler=trend_command_impl.run_sentiment)

    pmi = trend_commands.add_parser("pmi", help="Analyze term co-occurrence drift")
    pmi.add_argument("--term")
    pmi.add_argument(
        "--input", help="Prepared review JSONL (default: [data].prepared_path)"
    )
    pmi.add_argument(
        "--output-dir", help="Artifact directory (default: [trends.pmi].output_dir)"
    )
    pmi.add_argument("--window-size", type=int)
    pmi.add_argument("--top-n", type=int)
    pmi.add_argument("--min-cooccurrence", type=int)
    pmi.add_argument("--min-cooccurrence-rate", type=float)
    pmi.add_argument("--start-date", help="Inclusive YYYY-MM-DD lower bound")
    pmi.add_argument("--end-date", help="Inclusive YYYY-MM-DD upper bound")
    pmi.add_argument(
        "--time-granularity", choices=("year", "month"), help="Override configuration"
    )
    add_config_argument(pmi)
    pmi.set_defaults(handler=trend_command_impl.run_pmi)

    app = subparsers.add_parser("app", help="Run the small NLP/IR application")
    app_commands = app.add_subparsers(dest="app_command", required=True)
    comparisons = app_commands.add_parser(
        "comparisons", help="Detect comparison sentences in reviews"
    )
    comparisons.add_argument(
        "--input", help="Prepared sample JSONL (default: [data].sample_path)"
    )
    comparisons.add_argument(
        "--output-dir",
        help="Artifact directory (default: [application.comparisons].output_dir)",
    )
    comparisons.add_argument("--limit", type=int, help="Maximum reviews to scan")
    add_config_argument(comparisons)
    comparisons.set_defaults(handler=trend_command_impl.run_comparisons)
