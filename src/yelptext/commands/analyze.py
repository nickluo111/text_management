"""Register dataset-analysis commands."""

from __future__ import annotations

import argparse

from yelptext.commands._common import add_config_argument, use_placeholder


ANALYSES = (
    ("zipf", "Validate Zipf's law"),
    ("heaps", "Estimate Heaps' law parameters"),
    ("tokenizers", "Compare custom and baseline tokenizers"),
)


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("analyze", help="Run dataset-analysis experiments")
    analyses = parser.add_subparsers(dest="analysis", required=True)
    for name, help_text in ANALYSES:
        child = analyses.add_parser(name, help=help_text)
        add_config_argument(child)
        use_placeholder(child, "analyze", name)
