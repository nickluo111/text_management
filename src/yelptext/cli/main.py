"""Unified command-line entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from yelptext.cli import data_corpus_analysis, search_engine, trend_application


COMMAND_MODULES = (data_corpus_analysis, search_engine, trend_application)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yelptext",
        description="Yelp review analysis, retrieval, and trend analysis",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for command_module in COMMAND_MODULES:
        command_module.register(commands)

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.handler(args)
