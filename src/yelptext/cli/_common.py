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


def placeholder_handler(args: argparse.Namespace) -> None:
    """Temporary handler used until the corresponding command is implemented."""

    path = " ".join(getattr(args, "command_path", ["unknown"]))
    print(f"Command '{path}' is scaffolded but not implemented yet.")


def use_placeholder(parser: argparse.ArgumentParser, *command_path: str) -> None:
    parser.set_defaults(handler=placeholder_handler, command_path=list(command_path))
