"""Resolve consumer-owned fixture interfaces or shared real interfaces."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from yelptext.runtime.config import RuntimeMode


REAL_INTERFACE_ROOT = "yelptext.interface"
FIXTURE_INTERFACE_ROOTS = {
    "search_engine": "tests.fake.search_engine",
    "trend_application": "tests.fake.trend_application",
}


def load_interface_module(
    mode: RuntimeMode, interface: str, *, consumer: str | None = None
) -> ModuleType:
    """Load an upstream interface for a real or consumer-owned fixture run."""

    if not interface.isidentifier() or interface.startswith("_"):
        raise ValueError(f"Invalid interface module name: {interface!r}")

    if mode == "real":
        root = REAL_INTERFACE_ROOT
    else:
        if consumer not in FIXTURE_INTERFACE_ROOTS:
            choices = ", ".join(sorted(FIXTURE_INTERFACE_ROOTS))
            raise ValueError(
                f"Fixture mode requires a consumer in {{{choices}}}; got {consumer!r}"
            )
        root = FIXTURE_INTERFACE_ROOTS[consumer]
    return import_module(f"{root}.{interface}")
