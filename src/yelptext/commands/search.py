"""Register search and retrieval-evaluation commands."""

from __future__ import annotations

import argparse

from yelptext.commands._common import add_config_argument, use_placeholder


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("search", help="Search reviews or evaluate rankers")
    parser.add_argument("query", nargs="?", help="Free-text query")
    parser.add_argument("--ranker", choices=("tfidf", "bm25"), default="bm25")
    add_config_argument(parser)
    parser.add_argument("--queries", help="TOML file used for batch evaluation")
    use_placeholder(parser, "search")
