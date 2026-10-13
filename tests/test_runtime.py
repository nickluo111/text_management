"""The configuration mode selects parallel fake or real interfaces."""

from __future__ import annotations

import pytest

from yelptext.runtime import load_config, load_interface_module, runtime_mode


def test_fixture_mode_resolves_the_fake_namespace() -> None:
    config = load_config("tests/fixtures/fixture.toml")
    module = load_interface_module(runtime_mode(config), "data_corpus_analysis")

    assert module.__name__ == "tests.fake.interface.data_corpus_analysis"


def test_real_mode_resolves_the_source_namespace() -> None:
    config = load_config("configs/default.toml")
    module = load_interface_module(runtime_mode(config), "data_corpus_analysis")

    assert module.__name__ == "yelptext.interface.data_corpus_analysis"


@pytest.mark.parametrize("mode", [None, "test", "production"])
def test_invalid_runtime_modes_are_rejected(mode: object) -> None:
    with pytest.raises(ValueError, match="runtime.*mode"):
        runtime_mode({"runtime": {"mode": mode}})


@pytest.mark.parametrize("interface", ["", "../reviews", "_private"])
def test_invalid_interface_names_are_rejected(interface: str) -> None:
    with pytest.raises(ValueError, match="Invalid interface"):
        load_interface_module("fixture", interface)
