"""The configuration mode selects parallel fake or real interfaces."""

from __future__ import annotations

import pytest

from yelptext.runtime import load_config, load_interface_module, runtime_mode


def test_fixture_mode_resolves_the_fake_namespace() -> None:
    config = load_config("tests/fixtures/fixture.toml")
    module = load_interface_module(
        runtime_mode(config), "data_corpus_analysis", consumer="search_engine"
    )

    assert module.__name__ == "tests.fake.search_engine.data_corpus_analysis"


def test_each_consumer_owns_its_fixture_interface() -> None:
    module = load_interface_module(
        "fixture", "data_corpus_analysis", consumer="trend_application"
    )

    assert module.__name__ == "tests.fake.trend_application.data_corpus_analysis"


def test_real_mode_resolves_the_source_namespace() -> None:
    config = load_config("configs/default.toml")
    module = load_interface_module(runtime_mode(config), "data_corpus_analysis")

    assert module.__name__ == "yelptext.interface.data_corpus_analysis"


def test_fixture_mode_requires_a_known_consumer() -> None:
    with pytest.raises(ValueError, match="requires a consumer"):
        load_interface_module("fixture", "data_corpus_analysis")


@pytest.mark.parametrize("mode", [None, "test", "production"])
def test_invalid_runtime_modes_are_rejected(mode: object) -> None:
    with pytest.raises(ValueError, match="runtime.*mode"):
        runtime_mode({"runtime": {"mode": mode}})


@pytest.mark.parametrize("interface", ["", "../reviews", "_private"])
def test_invalid_interface_names_are_rejected(interface: str) -> None:
    with pytest.raises(ValueError, match="Invalid interface"):
        load_interface_module("fixture", interface)
