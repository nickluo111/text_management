"""Register the data-preparation command."""

from __future__ import annotations

import argparse

from yelptext.commands._common import add_config_argument, use_placeholder


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "prepare", help="Validate and prepare Yelp JSONL data"
    )
    add_config_argument(parser)
    use_placeholder(parser, "prepare")
