"""Validate only the schema-independent raw fixture and its edge coverage."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import tomllib


FIXTURES = Path(__file__).parent / "fixtures"
RAW = FIXTURES / "raw"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_fixture_configuration_declares_raw_fixture_mode() -> None:
    with (FIXTURES / "fixture.toml").open("rb") as stream:
        config = tomllib.load(stream)

    assert config["runtime"]["mode"] == "fixture"
    assert set(config["data"]) == {"business_path", "review_path"}
    assert Path(config["data"]["business_path"]).is_file()
    assert Path(config["data"]["review_path"]).is_file()


def test_raw_records_match_the_known_yelp_source_shapes() -> None:
    businesses = load_jsonl(RAW / "businesses.jsonl")
    reviews = load_jsonl(RAW / "reviews.jsonl")

    business_fields = {
        "business_id",
        "name",
        "address",
        "city",
        "state",
        "postal_code",
        "latitude",
        "longitude",
        "stars",
        "review_count",
        "is_open",
        "attributes",
        "categories",
        "hours",
    }
    review_fields = {
        "review_id",
        "user_id",
        "business_id",
        "stars",
        "useful",
        "funny",
        "cool",
        "text",
        "date",
    }

    assert businesses and reviews
    assert all(business_fields == record.keys() for record in businesses)
    assert all(review_fields == record.keys() for record in reviews)
    assert len({record["business_id"] for record in businesses}) == len(businesses)
    assert len({record["review_id"] for record in reviews}) == len(reviews)

    for record in businesses:
        assert isinstance(record["business_id"], str)
        assert isinstance(record["categories"], str)
        assert isinstance(record["latitude"], (int, float))
        assert isinstance(record["longitude"], (int, float))
        assert record["attributes"] is None or isinstance(record["attributes"], dict)
        assert record["hours"] is None or isinstance(record["hours"], dict)
        assert record["is_open"] in {0, 1}
        assert 0.0 <= float(record["stars"]) <= 5.0
    for record in reviews:
        assert isinstance(record["review_id"], str)
        assert isinstance(record["text"], str)
        assert 1.0 <= float(record["stars"]) <= 5.0
        datetime.fromisoformat(record["date"])


def test_raw_fixture_is_internally_consistent_except_for_the_intended_orphan() -> None:
    businesses = load_jsonl(RAW / "businesses.jsonl")
    reviews = load_jsonl(RAW / "reviews.jsonl")
    business_ids = {record["business_id"] for record in businesses}

    orphan_ids = {
        record["review_id"]
        for record in reviews
        if record["business_id"] not in business_ids
    }
    assert orphan_ids == {"r999"}

    linked_counts = Counter(
        record["business_id"]
        for record in reviews
        if record["business_id"] in business_ids
    )
    assert all(
        linked_counts[business["business_id"]] == business["review_count"]
        for business in businesses
    )


def test_raw_fixture_covers_likely_text_and_metadata_edges() -> None:
    businesses = load_jsonl(RAW / "businesses.jsonl")
    reviews = load_jsonl(RAW / "reviews.jsonl")
    texts = [record["text"] for record in reviews]
    years = {datetime.fromisoformat(record["date"]).year for record in reviews}

    assert {business["is_open"] for business in businesses} == {0, 1}
    assert any("," in business["categories"] for business in businesses)
    assert len(years) >= 2
    assert any("'" in text for text in texts)
    assert any("-" in text for text in texts)
    assert any("$" in text and any(char.isdigit() for char in text) for text in texts)
    assert any(any(ord(char) > 127 for char in text) for text in texts)
    assert any(" than " in text.lower() or "unlike" in text.lower() for text in texts)
