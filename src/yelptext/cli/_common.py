"""Shared CLI registration helpers."""

from __future__ import annotations

import argparse


DEFAULT_CONFIG = "configs/default.toml"


def add_config_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        metavar="PATH",
        help="TOML experiment configuration (default: %(default)s)",
    )
