"""Unified command-line entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from yelptext.cli import data_corpus_analysis, search_engine, trend_application
from yelptext.cli._common import add_config_argument, use_placeholder


COMMAND_MODULES = (data_corpus_analysis, search_engine, trend_application)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yelptext",
        description="Yelp review analysis, retrieval, and trend analysis",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for command_module in COMMAND_MODULES:
        command_module.register(commands)

    run_all = commands.add_parser("run-all", help="Reproduce all report artifacts")
    add_config_argument(run_all)
    use_placeholder(run_all, "run-all")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.handler(args)
