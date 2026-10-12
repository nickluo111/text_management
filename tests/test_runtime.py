"""The configuration mode selects parallel fake or real provider namespaces."""

from __future__ import annotations

import pytest

from yelptext.config import load_config, runtime_mode
from yelptext.runtime import load_provider_module


def test_fixture_mode_resolves_the_fake_namespace() -> None:
    config = load_config("tests/fixtures/fixture.toml")
    module = load_provider_module(runtime_mode(config), "reviews")

    assert module.__name__ == "tests.fakes.reviews"


def test_real_mode_resolves_the_source_namespace() -> None:
    config = load_config("configs/default.toml")
    module = load_provider_module(runtime_mode(config), "reviews")

    assert module.__name__ == "yelptext.providers.real.reviews"


@pytest.mark.parametrize("mode", [None, "test", "production"])
def test_invalid_runtime_modes_are_rejected(mode: object) -> None:
    with pytest.raises(ValueError, match="runtime.*mode"):
        runtime_mode({"runtime": {"mode": mode}})


@pytest.mark.parametrize("provider", ["", "../reviews", "_private"])
def test_invalid_provider_names_are_rejected(provider: str) -> None:
    with pytest.raises(ValueError, match="Invalid provider"):
        load_provider_module("fixture", provider)
