"""Tests for the real data/corpus facilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yelptext.implementation.data_corpus_analysis.reviewer import YelpDataError
from yelptext.interface.data_corpus_analysis import create_review_reader


RAW = Path(__file__).parent / "fixtures" / "data" / "raw"
BUSINESSES = RAW / "yelp_academic_dataset_business.json"
REVIEWS = RAW / "yelp_academic_dataset_review.json"


def test_reader_joins_business_metadata_into_the_protocol_shape() -> None:
    reader = create_review_reader(REVIEWS, BUSINESSES, orphan_policy="skip")

    first = next(iter(reader.iter_reviews()))

    assert first == {
        "review_id": "r001",
        "business_id": "b_italian",
        "business_name": "Pasta Point",
        "categories": ["Italian", "Restaurants"],
        "stars": 5.0,
        "text": "Great pizza, friendly service!",
        "date": "2021-01-15",
    }


def test_reader_streams_all_linked_reviews_and_is_repeatable() -> None:
    reader = create_review_reader(REVIEWS, BUSINESSES, orphan_policy="skip")

    first_pass = list(reader.iter_reviews())
    second_pass = list(reader.iter_reviews())

    assert len(first_pass) == 20
    assert second_pass == first_pass
    assert all(list(review) == [
        "review_id",
        "business_id",
        "business_name",
        "categories",
        "stars",
        "text",
        "date",
    ] for review in first_pass)


def test_reader_reports_an_orphan_with_source_location() -> None:
    reader = create_review_reader(REVIEWS, BUSINESSES)

    with pytest.raises(
        YelpDataError,
        match=r"yelp_academic_dataset_review\.json:21:.*b_missing",
    ):
        list(reader.iter_reviews())


def test_null_business_categories_become_an_empty_list(tmp_path: Path) -> None:
    business_path = tmp_path / "business.jsonl"
    review_path = tmp_path / "review.jsonl"
    business_path.write_text(
        json.dumps({"business_id": "b1", "name": "No Category", "categories": None})
        + "\n",
        encoding="utf-8",
    )
    review_path.write_text(
        json.dumps(
            {
                "review_id": "r1",
                "business_id": "b1",
                "stars": 4.0,
                "text": "Good.",
                "date": "2022-03-04 12:30:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    review = next(
        iter(create_review_reader(review_path, business_path).iter_reviews())
    )

    assert review["categories"] == []
    assert review["date"] == "2022-03-04"


def test_reader_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    business_path = tmp_path / "business.jsonl"
    review_path = tmp_path / "review.jsonl"
    business_path.write_text(
        '{"business_id":"b1","business_id":"b2","name":"Duplicate"}\n',
        encoding="utf-8",
    )
    review_path.write_text("", encoding="utf-8")

    reader = create_review_reader(review_path, business_path)
    with pytest.raises(YelpDataError, match="duplicate JSON key: business_id"):
        list(reader.iter_reviews())
