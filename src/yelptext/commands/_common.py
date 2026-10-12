"""Shared helpers for command registration."""

from __future__ import annotations

import argparse


DEFAULT_CONFIG = "configs/default.toml"


def add_config_argument(parser: argparse.ArgumentParser) -> None:
    """Add the project-wide configuration option to a command."""
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        metavar="PATH",
        help="TOML experiment configuration (default: %(default)s)",
    )


def placeholder_handler(args: argparse.Namespace) -> None:
    """Report commands whose domain implementation has not been connected yet."""
    path = " ".join(getattr(args, "command_path", ["unknown"]))
    print(f"Command '{path}' is scaffolded but not implemented yet.")


def use_placeholder(parser: argparse.ArgumentParser, *command_path: str) -> None:
    """Attach the temporary handler and a stable command identity."""
    parser.set_defaults(handler=placeholder_handler, command_path=list(command_path))
