"""Register inverted-index commands."""

from __future__ import annotations

import argparse

from yelptext.commands._common import add_config_argument, use_placeholder


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("index", help="Manage the inverted index")
    commands = parser.add_subparsers(dest="index_command", required=True)
    build = commands.add_parser("build", help="Build and persist an inverted index")
    add_config_argument(build)
    use_placeholder(build, "index", "build")
