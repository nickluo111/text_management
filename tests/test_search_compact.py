"""Compact storage must preserve the independently tested reference rankers."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from tests.fake.search_engine.data_corpus_analysis import create_review_reader, create_tokenizer_pipeline
from tests.test_search_engine import MemoryReader, review
from yelptext.interface.search_engine import (
    build_index, load_index, build_compact_index, load_compact_index, search,
)

FIXTURE = Path(__file__).parent / "fixtures/search_engine/reviews.jsonl"


@pytest.fixture
def pipeline():
    return create_tokenizer_pipeline(skip_types={"punctuation"})


@pytest.fixture
def backends(tmp_path, pipeline):
    build_index(create_review_reader(FIXTURE), pipeline, tmp_path / "reference")
    build_compact_index(create_review_reader(FIXTURE), pipeline, tmp_path / "compact")
    with load_index(tmp_path / "reference", pipeline) as reference:
        with load_compact_index(tmp_path / "compact", pipeline) as compact:
            yield reference, compact


@pytest.mark.parametrize("ranker", ["tfidf", "bm25"])
@pytest.mark.parametrize("query", ["apple banana", "apple apple banana", "carrot", "apple unknown", "!!!", "missing"])
def test_scores_and_result_order_equal_reference(backends, ranker, query):
    reference, compact = backends
    expected = search(reference, query, ranker=ranker)
    actual = search(compact, query, ranker=ranker)
    assert [hit.doc_id for hit in actual] == [hit.doc_id for hit in expected]
    assert [hit.score for hit in actual] == pytest.approx([hit.score for hit in expected], rel=1e-13, abs=1e-15)
    assert [hit.text for hit in actual] == [hit.text for hit in expected]
    assert [hit.business_name for hit in actual] == [hit.business_name for hit in expected]


def test_statistics_and_posting_diagnostics(backends):
    reference, compact = backends
    for key in ("document_count", "vocabulary_size", "total_terms", "avgdl", "tokenizer_fingerprint"):
        assert compact.stats()[key] == reference.stats()[key]
    assert compact.stats()["posting_count"] == 6
    assert compact.stats()["backend"] == "compact-v1"
    for term in ("apple", "banana", "carrot", "missing"):
        assert compact.postings(term) == reference.postings(term)
        assert compact.term_df(term) == len(reference.postings(term))
    assert compact.lengths.tolist() == [3, 2, 4, 0]


@pytest.mark.parametrize("ranker", ["tfidf", "bm25"])
def test_nonuniform_idf_and_boundary_ties(tmp_path, pipeline, ranker):
    records = [review("z", "apple banana"), review("a", "apple banana"), review("b", "apple"), review("c", "carrot")]
    build_index(MemoryReader(records), pipeline, tmp_path / "reference")
    build_compact_index(MemoryReader(records), pipeline, tmp_path / "compact")
    with load_index(tmp_path / "reference", pipeline) as reference, load_compact_index(tmp_path / "compact", pipeline) as compact:
        for top_k in (1, 2, 3, 10):
            expected = search(reference, "banana", ranker=ranker, top_k=top_k)
            actual = search(compact, "banana", ranker=ranker, top_k=top_k)
            assert [hit.doc_id for hit in actual] == [hit.doc_id for hit in expected]
            assert [hit.score for hit in actual] == pytest.approx([hit.score for hit in expected])
        assert search(compact, "banana", ranker=ranker, top_k=1)[0].doc_id == "a"


def test_large_tie_set_uses_lexicographic_ids_across_query_batches(tmp_path, pipeline):
    records = [review(f"doc-{number:04}", "apple") for number in reversed(range(1901))]
    build_compact_index(MemoryReader(records), pipeline, tmp_path / "compact")
    with load_compact_index(tmp_path / "compact", pipeline) as compact:
        assert [hit.doc_id for hit in search(compact, "apple", top_k=3)] == ["doc-0000", "doc-0001", "doc-0002"]


@pytest.mark.parametrize("records", [[], [review("empty", "!!!")]])
def test_empty_indexes_are_supported(tmp_path, pipeline, records):
    path = tmp_path / "compact"
    stats = build_compact_index(MemoryReader(records), pipeline, path)
    assert stats["total_terms"] == stats["vocabulary_size"] == 0
    with load_compact_index(path, pipeline) as compact:
        assert search(compact, "apple", ranker="bm25") == []
        assert search(compact, "apple", ranker="tfidf") == []


def test_duplicate_id_and_memory_limit_never_publish_partial_index(tmp_path, pipeline):
    path = tmp_path / "compact"
    with pytest.raises(ValueError, match="Duplicate"):
        build_compact_index(MemoryReader([review("a", "apple"), review("a", "banana")]), pipeline, path)
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(MemoryError):
        build_compact_index(MemoryReader([review("a", "apple")]), pipeline, path, max_memory_bytes=1)
    assert list(tmp_path.iterdir()) == []


def test_reload_fingerprint_version_and_no_overwrite(tmp_path, pipeline):
    path = tmp_path / "compact"
    build_compact_index(create_review_reader(FIXTURE), pipeline, path)
    with load_compact_index(path, pipeline) as first:
        expected = search(first, "apple banana")
    with load_compact_index(path, create_tokenizer_pipeline(skip_types={"punctuation"})) as reopened:
        assert search(reopened, "apple banana") == expected
    with pytest.raises(FileExistsError):
        build_compact_index(create_review_reader(FIXTURE), pipeline, path)
    with pytest.raises(ValueError, match="fingerprint"):
        load_compact_index(path, create_tokenizer_pipeline())
    metadata = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    metadata["format_version"] = 999
    (path / "manifest.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="format"):
        load_compact_index(path, pipeline)


def test_truncated_vector_is_rejected(tmp_path, pipeline):
    path = tmp_path / "compact"
    build_compact_index(create_review_reader(FIXTURE), pipeline, path)
    np.save(path / "norms.npy", np.zeros(2, dtype="<f8"), allow_pickle=False)
    with pytest.raises(ValueError, match="sizes"):
        load_compact_index(path, pipeline)


def test_progress_reports_scanning_and_completion(tmp_path, pipeline):
    events = []
    build_compact_index(create_review_reader(FIXTURE), pipeline, tmp_path / "compact", progress=events.append)
    assert [event["stage"] for event in events] == ["document_scan_complete", "complete"]
    assert events[-1]["documents"] == 4
    assert events[-1]["postings"] == 6

