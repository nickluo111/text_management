"""Register index construction and search commands."""

from __future__ import annotations

import argparse

from yelptext.cli._common import add_config_argument, use_placeholder


def register(subparsers: argparse._SubParsersAction) -> None:
    index = subparsers.add_parser("index", help="Manage the inverted index")
    index_commands = index.add_subparsers(dest="index_command", required=True)
    build = index_commands.add_parser(
        "build", help="Build and persist an inverted index"
    )
    add_config_argument(build)
    use_placeholder(build, "index", "build")

    search = subparsers.add_parser(
        "search", help="Search reviews or evaluate rankers"
    )
    search.add_argument("query", nargs="?", help="Free-text query")
    search.add_argument("--ranker", choices=("tfidf", "bm25"), default="bm25")
    add_config_argument(search)
    search.add_argument("--queries", help="TOML file used for batch evaluation")
    use_placeholder(search, "search")
