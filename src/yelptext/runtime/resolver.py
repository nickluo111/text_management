"""Resolve same-name interfaces from fixture or real namespaces."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from yelptext.runtime.config import RuntimeMode


INTERFACE_ROOTS: dict[RuntimeMode, str] = {
    "fixture": "tests.fake.interface",
    "real": "yelptext.interface",
}


def load_interface_module(mode: RuntimeMode, interface: str) -> ModuleType:
    """Load one semantic interface module for the selected runtime mode."""

    if not interface.isidentifier() or interface.startswith("_"):
        raise ValueError(f"Invalid interface module name: {interface!r}")
    return import_module(f"{INTERFACE_ROOTS[mode]}.{interface}")
