"""Register the full experiment pipeline command."""

from __future__ import annotations

import argparse

from yelptext.commands._common import add_config_argument, use_placeholder


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("run-all", help="Reproduce all report artifacts")
    add_config_argument(parser)
    use_placeholder(parser, "run-all")
