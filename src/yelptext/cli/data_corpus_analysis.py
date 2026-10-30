"""Register data preparation and corpus-analysis commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from yelptext.cli._common import add_config_argument
from yelptext.command.data_corpus_analysis import (
    run_analysis_notebook,
    run_build_vocabulary,
    run_prepare,
    run_sample,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    prepare = subparsers.add_parser(
        "prepare", help="Validate and prepare Yelp JSONL data"
    )
    add_config_argument(prepare)
    prepare.add_argument("--reviews", type=Path, help="Override [data].review_path")
    prepare.add_argument(
        "--businesses", type=Path, help="Override [data].business_path"
    )
    prepare.add_argument("--output", type=Path, help="Override [data].prepared_path")
    prepare.add_argument(
        "--limit", type=int, help="Development prefix size; not a random sample"
    )
    prepare.add_argument(
        "--long-text-threshold",
        type=int,
        default=50_000,
        help="Audit threshold only; long reviews are retained (default: %(default)s)",
    )
    prepare.set_defaults(handler=run_prepare, command_path=["prepare"])

    vocabulary = subparsers.add_parser(
        "vocab", help="Manage the shared tokenizer vocabulary"
    )
    vocabulary_commands = vocabulary.add_subparsers(
        dest="vocabulary_command", required=True
    )
    build = vocabulary_commands.add_parser(
        "build", help="Build the full CF/DF SQLite vocabulary"
    )
    add_config_argument(build)
    build.add_argument("--reviews", type=Path, help="Override [data].review_path")
    build.add_argument(
        "--output", type=Path, help="Override [tokenizer].vocabulary_path"
    )
    build.add_argument("--buffer-unique-terms", type=int, default=100_000)
    build.set_defaults(handler=run_build_vocabulary, command_path=["vocab", "build"])

    sample = subparsers.add_parser(
        "sample", help="Create a deterministic schema-preserving review sample"
    )
    add_config_argument(sample)
    sample.add_argument("--input", type=Path, help="Override [data].prepared_path")
    sample.add_argument("--output", type=Path, help="Override [data].sample_path")
    sample.add_argument("--size", type=int, default=50_000)
    sample.add_argument("--seed", type=int, help="Override [data].random_seed")
    sample.set_defaults(handler=run_sample, command_path=["sample"])

    analyze = subparsers.add_parser(
        "analyze", help="Run corpus-analysis experiments"
    )
    analyses = analyze.add_subparsers(dest="analysis", required=True)
    for name, help_text in (
        ("zipf", "Execute the Zipf analysis notebook"),
        ("heaps", "Execute the Heaps analysis notebook"),
        ("tokenizers", "Compare custom and baseline tokenizers"),
    ):
        child = analyses.add_parser(name, help=help_text)
        add_config_argument(child)
        child.add_argument(
            "--output-dir",
            default="artifacts/notebooks",
            help="Directory for the executed notebook",
        )
        child.set_defaults(
            handler=run_analysis_notebook,
            command_path=["analyze", name],
        )
