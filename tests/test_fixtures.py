"""Validate synthetic handoffs, mathematical oracles, and labeled cases."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path
from statistics import fmean
import tomllib

import pytest


FIXTURES = Path(__file__).parent / "fixtures"
RAW = FIXTURES / "raw"
HANDOFFS = FIXTURES / "handoffs"
ORACLES = FIXTURES / "oracles"
CASES = FIXTURES / "cases"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_fixture_configuration_points_to_committed_inputs() -> None:
    with (FIXTURES / "fixture.toml").open("rb") as stream:
        config = tomllib.load(stream)

    assert config["data"]["sample_fraction"] == 1.0
    assert config["data"]["random_seed"] == 6122
    assert config["data"]["prepared_path"] == (
        "data/processed/reviews-fixture.jsonl"
    )
    assert config["search"]["bm25"] == {"k1": 1.5, "b": 0.75}
    assert config["trends"]["pmi"]["context"] == "document"
    for key in ("business_path", "review_path"):
        assert Path(config["data"][key]).is_file()


def test_raw_and_prepared_fixture_contract() -> None:
    businesses = load_jsonl(RAW / "businesses.jsonl")
    reviews = load_jsonl(RAW / "reviews.jsonl")
    prepared = load_jsonl(HANDOFFS / "prepared_reviews.jsonl")

    assert len(businesses) == 5
    assert len(reviews) == 21
    assert len(prepared) == 20
    assert len({item["business_id"] for item in businesses}) == len(businesses)
    assert len({item["review_id"] for item in reviews}) == len(reviews)

    businesses_by_id = {item["business_id"]: item for item in businesses}
    reviews_by_id = {item["review_id"]: item for item in reviews}
    orphan_ids = {
        item["review_id"]
        for item in reviews
        if item["business_id"] not in businesses_by_id
    }
    assert orphan_ids == {"r999"}
    assert {item["review_id"] for item in prepared} == set(reviews_by_id) - orphan_ids

    for item in prepared:
        raw_review = reviews_by_id[item["review_id"]]
        business = businesses_by_id[item["business_id"]]
        assert item["text"] == raw_review["text"]
        assert item["stars"] == raw_review["stars"]
        assert item["date"] == raw_review["date"]
        assert item["business_name"] == business["name"]
        assert item["categories"] == [
            category.strip() for category in business["categories"].split(",")
        ]
        datetime.fromisoformat(item["date"])


def test_tokenizer_fixture_has_unique_cases() -> None:
    fixture = load_json(CASES / "tokenizer_cases.json")
    cases = fixture["cases"]
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(isinstance(case["text"], str) for case in cases)
    assert all(isinstance(case["tokens"], list) for case in cases)
    assert {case["id"] for case in cases} == {
        "case_and_emoji",
        "contraction_and_hyphen",
        "numbers_and_currency",
        "unicode_words",
        "empty_text",
    }


def test_postings_are_consistent_with_fixture_documents() -> None:
    fixture = load_json(ORACLES / "postings.json")
    documents = fixture["documents"]
    lengths = {doc_id: len(tokens) for doc_id, tokens in documents.items()}

    assert fixture["document_count"] == len(documents)
    assert fixture["document_lengths"] == lengths
    assert fixture["average_document_length"] == pytest.approx(
        fmean(lengths.values())
    )

    calculated: dict[str, list[dict]] = {}
    for doc_id, tokens in documents.items():
        for term in dict.fromkeys(tokens):
            positions = [index for index, token in enumerate(tokens) if token == term]
            calculated.setdefault(term, []).append(
                {
                    "review_id": doc_id,
                    "term_frequency": len(positions),
                    "positions": positions,
                }
            )

    assert set(fixture["postings"]) == set(calculated)
    for term, entries in calculated.items():
        posting = fixture["postings"][term]
        assert posting["entries"] == entries
        assert posting["document_frequency"] == len(entries)
        assert posting["collection_frequency"] == sum(
            entry["term_frequency"] for entry in entries
        )


def test_hand_calculated_ranking_scores() -> None:
    corpus = load_json(ORACLES / "postings.json")
    fixture = load_json(ORACLES / "ranking_cases.json")
    documents = corpus["documents"]
    query_terms = fixture["query"]["tokens"]
    document_count = corpus["document_count"]
    document_frequency = {
        term: posting["document_frequency"]
        for term, posting in corpus["postings"].items()
    }

    query_counts = Counter(query_terms)
    query_weights = {
        term: count * math.log(document_count / document_frequency[term])
        for term, count in query_counts.items()
    }
    query_norm = math.sqrt(sum(weight**2 for weight in query_weights.values()))
    tfidf_scores: dict[str, float] = {}
    for doc_id, tokens in documents.items():
        token_counts = Counter(tokens)
        document_weights = {
            term: count * math.log(document_count / document_frequency[term])
            for term, count in token_counts.items()
        }
        dot_product = sum(
            document_weights.get(term, 0.0) * weight
            for term, weight in query_weights.items()
        )
        document_norm = math.sqrt(
            sum(weight**2 for weight in document_weights.values())
        )
        tfidf_scores[doc_id] = dot_product / (document_norm * query_norm)

    assert tfidf_scores == pytest.approx(fixture["tfidf"]["scores"])

    k1 = fixture["bm25"]["k1"]
    b = fixture["bm25"]["b"]
    average_length = corpus["average_document_length"]
    bm25_scores: dict[str, float] = {}
    for doc_id, tokens in documents.items():
        token_counts = Counter(tokens)
        score = 0.0
        for term in query_terms:
            frequency = token_counts[term]
            if frequency == 0:
                continue
            df = document_frequency[term]
            inverse_document_frequency = math.log(
                1 + (document_count - df + 0.5) / (df + 0.5)
            )
            denominator = frequency + k1 * (
                1 - b + b * len(tokens) / average_length
            )
            score += inverse_document_frequency * frequency * (k1 + 1) / denominator
        bm25_scores[doc_id] = score

    assert bm25_scores == pytest.approx(fixture["bm25"]["scores"])
    for name, scores in (("tfidf", tfidf_scores), ("bm25", bm25_scores)):
        ranked = [
            doc_id
            for doc_id, score in sorted(
                scores.items(), key=lambda item: (-item[1], item[0])
            )
            if score > 0
        ]
        assert ranked == fixture[name]["ranked_nonzero_review_ids"]


def test_hand_calculated_pmi_values() -> None:
    fixture = load_json(ORACLES / "pmi_cases.json")
    target = fixture["target_term"]
    for period in fixture["periods"].values():
        documents = [set(tokens) for tokens in period["documents"]]
        target_df = sum(target in document for document in documents)
        assert period["document_count"] == len(documents)
        assert period["target_document_frequency"] == target_df

        for term, oracle in period["associations"].items():
            term_df = sum(term in document for document in documents)
            cooccurrence = sum(
                target in document and term in document for document in documents
            )
            pmi = math.log(cooccurrence * len(documents) / (target_df * term_df))
            assert oracle["term_document_frequency"] == term_df
            assert oracle["cooccurrence_count"] == cooccurrence
            assert oracle["pmi"] == pytest.approx(pmi)


def test_labeled_cases_reference_the_raw_reviews() -> None:
    reviews = {
        item["review_id"]: item for item in load_jsonl(RAW / "reviews.jsonl")
    }
    sentiment = load_json(CASES / "sentiment_cases.json")["cases"]
    comparisons = load_json(CASES / "comparison_cases.json")["cases"]

    for case in sentiment:
        assert reviews[case["review_id"]]["text"] == case["text"]
        assert case["expected_label"] in {"positive", "negative", "neutral"}
    for case in comparisons:
        assert case["review_id"] in reviews
        assert isinstance(case["is_cross_business_comparison"], bool)
