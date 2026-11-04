"""Register index construction and search commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from yelptext.cli._common import add_config_argument
from yelptext.command.search_engine import run_build_index, run_search


def register(subparsers: argparse._SubParsersAction) -> None:
    index = subparsers.add_parser("index", help="Manage the inverted index")
    index_commands = index.add_subparsers(dest="index_command", required=True)
    build = index_commands.add_parser(
        "build", help="Build and persist an inverted index"
    )
    add_config_argument(build)
    build.add_argument("--output-dir", type=Path, help="Override [index].output_dir")
    build.set_defaults(handler=run_build_index, command_path=["index", "build"])

    search = subparsers.add_parser(
        "search", help="Search reviews or evaluate rankers"
    )
    queries = search.add_mutually_exclusive_group(required=True)
    queries.add_argument("query", nargs="?", help="Free-text query")
    queries.add_argument("--queries", type=Path, help="TOML file containing queries")
    search.add_argument("--ranker", choices=("tfidf", "bm25"), default="bm25")
    add_config_argument(search)
    search.add_argument("--index-dir", type=Path, help="Override [index].output_dir")
    search.add_argument("--top-k", type=int, help="Override [search].top_k")
    search.add_argument("--output", type=Path, help="Also save the result JSON to this path")
    search.set_defaults(handler=run_search, command_path=["search"])
