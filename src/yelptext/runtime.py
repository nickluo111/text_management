"""Resolve same-name provider modules from fixture or real namespaces."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from yelptext.config import RuntimeMode


PROVIDER_ROOTS: dict[RuntimeMode, str] = {
    "fixture": "tests.fakes",
    "real": "yelptext.providers.real",
}


def load_provider_module(mode: RuntimeMode, provider: str) -> ModuleType:
    """Load a provider module without assuming an unconfirmed export schema.

    For example, ``reviews`` resolves to ``tests.fakes.reviews`` in fixture
    mode and ``yelptext.providers.real.reviews`` in real mode. Approved
    contracts will later determine the same-named classes exported by both.
    """

    if not provider.isidentifier() or provider.startswith("_"):
        raise ValueError(f"Invalid provider module name: {provider!r}")
    return import_module(f"{PROVIDER_ROOTS[mode]}.{provider}")
