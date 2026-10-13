"""Minimal configuration loading shared by fixture and real runtime modes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Mapping, cast
import tomllib


RuntimeMode = Literal["fixture", "real"]


def load_config(path: str | Path) -> dict[str, Any]:
    """Load TOML without imposing unconfirmed domain-specific settings."""

    with Path(path).open("rb") as stream:
        return tomllib.load(stream)


def runtime_mode(config: Mapping[str, Any]) -> RuntimeMode:
    """Return the confirmed interface mode from a loaded configuration."""

    runtime = config.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ValueError("Configuration must define [runtime].mode")

    mode = runtime.get("mode")
    if mode not in {"fixture", "real"}:
        raise ValueError("[runtime].mode must be 'fixture' or 'real'")
    return cast(RuntimeMode, mode)
