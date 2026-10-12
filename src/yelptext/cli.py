"""Unified command-line entry point.

Each top-level command registers itself from :mod:`yelptext.commands` so that
responsibility groups can work independently without repeatedly editing this
module.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from yelptext.commands import (
    analyze,
    application,
    index,
    prepare,
    run_all,
    search,
    trend,
)


COMMAND_MODULES = (prepare, analyze, index, search, trend, application, run_all)


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
