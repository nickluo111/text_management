"""Independent algebra, persistence, and command tests for the real search engine."""

from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path
import sqlite3

import pytest

from tests.fake.search_engine.data_corpus_analysis import (
    create_review_reader,
    create_tokenizer_pipeline,
)
from yelptext.cli.main import main
from yelptext.interface.search_engine import build_index, load_index, search
from yelptext.protocol.reviewer import PreparedReview
from yelptext.runtime import load_interface_module


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "search_engine"
REVIEWS = FIXTURES / "reviews.jsonl"
CONFIG = FIXTURES / "fixture.toml"


def review(doc_id: str, text: str) -> PreparedReview:
    return {
        "doc_id": doc_id,
        "text": text,
        "user_id": None,
        "stars": None,
        "review_date": None,
        "business_id": None,
        "business_name": None,
        "categories": None,
        "city": None,
        "state": None,
    }


class MemoryReader:
    def __init__(self, records):
        self.records = records

    def iter_reviews(self):
        yield from self.records


@pytest.fixture
def pipeline():
    return create_tokenizer_pipeline(skip_types={"punctuation"})


@pytest.fixture
def persisted(tmp_path, pipeline):
    directory = tmp_path / "index"
    stats = build_index(create_review_reader(REVIEWS), pipeline, directory)
    return directory, stats


@pytest.fixture
def index(persisted, pipeline):
    with load_index(persisted[0], pipeline) as loaded:
        yield loaded


def scores(results):
    return {result.doc_id: result.score for result in results}


def test_index_counts_postings_and_filtered_empty_document(persisted, index, pipeline):
    directory, stats = persisted
    assert (directory / "index.sqlite3").is_file()
    assert stats["document_count"] == 4
    assert stats["vocabulary_size"] == 3
    assert stats["total_terms"] == 9
    assert stats["avgdl"] == pytest.approx(9 / 4)
    assert stats["tokenizer_fingerprint"] == pipeline.fingerprint()
    assert "format_version" in stats
    assert index.stats() == stats
    assert index.postings("apple") == [("d1", 2), ("d3", 1)]
    assert index.postings("banana") == [("d1", 1), ("d2", 1)]
    assert index.postings("carrot") == [("d2", 1), ("d3", 3)]
    assert index.postings("!") == []
    assert index.postings("missing") == []


def test_tfidf_cosine_matches_independently_derived_scores(index):
    # Every term has DF=2, so its common IDF cancels from cosine.
    # The full d2 and d3 norms still include carrot, which is NOT in the query.
    a, c = 1 + math.log(2), 1 + math.log(3)
    results = search(index, "apple banana", ranker="tfidf")
    assert [hit.doc_id for hit in results] == ["d1", "d2", "d3"]
    assert scores(results) == pytest.approx({
        "d1": (a + 1) / math.sqrt(2 * (a * a + 1)),
        "d2": 0.5,
        "d3": 1 / math.sqrt(2 * (1 + c * c)),
    })


def test_tfidf_nonuniform_idf_and_full_document_norm(tmp_path, pipeline):
    records = [review("a", "apple banana"), review("b", "apple"), review("c", "carrot")]
    build_index(MemoryReader(records), pipeline, tmp_path)
    with load_index(tmp_path, pipeline) as index:
        results = search(index, "banana", ranker="tfidf")
    apple_idf = math.log(4 / 3) + 1  # DF=2 of 3
    banana_idf = math.log(2) + 1     # DF=1 of 3
    assert [hit.doc_id for hit in results] == ["a"]
    assert results[0].score == pytest.approx(
        banana_idf / math.sqrt(apple_idf ** 2 + banana_idf ** 2)
    )


def test_tfidf_query_term_frequency_uses_log_weights(index):
    a, c = 1 + math.log(2), 1 + math.log(3)
    assert scores(search(index, "apple apple banana", ranker="tfidf")) == pytest.approx({
        "d1": 1.0,
        "d2": 1 / math.sqrt(2 * (a * a + 1)),
        "d3": a / math.sqrt((a * a + 1) * (1 + c * c)),
    })


def test_bm25_matches_independently_simplified_scores(index):
    # N=4, DF=2 => IDF=ln(2). avgdl=9/4, k1=3/2, b=3/4.
    # Rational factors are derived in fixtures/search_engine/README.md.
    results = search(index, "apple banana", ranker="bm25")
    assert [hit.doc_id for hit in results] == ["d1", "d2", "d3"]
    assert scores(results) == pytest.approx({
        "d1": math.log(2) * (40 / 31 + 20 / 23),
        "d2": math.log(2) * (20 / 19),
        "d3": math.log(2) * (20 / 27),
    })


def test_bm25_b_zero_and_linear_query_frequency(index):
    assert scores(search(index, "apple", b=0)) == pytest.approx({
        "d1": math.log(2) * 10 / 7,
        "d3": math.log(2),
    })
    assert scores(search(index, "apple apple")) == pytest.approx({
        "d1": math.log(2) * 80 / 31,
        "d3": math.log(2) * 40 / 27,
    })


@pytest.mark.parametrize("ranker", ["tfidf", "bm25"])
def test_persistence_preserves_results_and_unicode_metadata(persisted, pipeline, ranker):
    directory, _ = persisted
    with load_index(directory, pipeline) as first:
        before = [asdict(hit) for hit in search(first, "apple banana", ranker=ranker)]
    # Construct a fresh tokenizer to verify stable policy identity across instances.
    same_policy = create_tokenizer_pipeline(skip_types=["punctuation"])
    with load_index(directory, same_policy) as reopened:
        after = [asdict(hit) for hit in search(reopened, "apple banana", ranker=ranker)]
    assert after == before
    assert after[0]["business_name"] == "Café 苹果"
    assert after[0]["city"] == "Montréal"
    assert after[0]["stars"] == 4.5
    assert after[1]["business_name"] is None


@pytest.mark.parametrize("ranker", ["tfidf", "bm25"])
@pytest.mark.parametrize("query", ["", "   ", "!!!", "unknown words"])
def test_empty_filtered_empty_and_oov_queries(index, ranker, query):
    assert search(index, query, ranker=ranker) == []


@pytest.mark.parametrize("ranker", ["tfidf", "bm25"])
def test_known_terms_survive_oov_and_query_filtering(index, ranker):
    plain = search(index, "apple banana", ranker=ranker)
    assert search(index, "APPLE! banana unknown", ranker=ranker) == plain
    assert search(index, "Montréal", ranker=ranker) == []  # Metadata is not indexed.
    assert search(index, "apple banana", ranker=ranker, top_k=1) == plain[:1]


@pytest.mark.parametrize("ranker", ["tfidf", "bm25"])
def test_ties_use_doc_id_not_input_order(tmp_path, pipeline, ranker):
    build_index(MemoryReader([review("z", "rare"), review("a", "rare")]), pipeline, tmp_path)
    with load_index(tmp_path, pipeline) as index:
        results = search(index, "rare", ranker=ranker)
        assert [hit.doc_id for hit in results] == ["a", "z"]
        assert results[0].score == results[1].score
        assert [hit.doc_id for hit in search(index, "rare", ranker=ranker, top_k=1)] == ["a"]


@pytest.mark.parametrize("records", [[], [review("empty", "!!!")]])
def test_empty_corpus_and_all_filtered_corpus(tmp_path, pipeline, records):
    stats = build_index(MemoryReader(records), pipeline, tmp_path)
    assert stats["document_count"] == len(records)
    assert stats["total_terms"] == stats["vocabulary_size"] == 0
    assert stats["avgdl"] == 0
    with load_index(tmp_path, pipeline) as index:
        assert search(index, "apple", ranker="tfidf") == []
        assert search(index, "apple", ranker="bm25") == []


@pytest.mark.parametrize("top_k", [0, -1, True, 1.5, "10"])
def test_reject_invalid_top_k_even_for_empty_query(index, top_k):
    with pytest.raises((ValueError, TypeError)):
        search(index, "", top_k=top_k)


@pytest.mark.parametrize("kwargs", [
    {"ranker": "unknown"},
    {"k1": 0}, {"k1": -1}, {"k1": math.inf}, {"k1": math.nan},
    {"b": -0.1}, {"b": 1.1}, {"b": math.inf}, {"b": math.nan},
])
def test_reject_invalid_ranker_or_bm25_parameters(index, kwargs):
    with pytest.raises((ValueError, TypeError)):
        search(index, "apple", **kwargs)


def test_duplicate_ids_fail_without_publishing_and_allow_retry(tmp_path, pipeline):
    reader = MemoryReader([review("same", "apple"), review("same", "banana")])
    with pytest.raises(ValueError, match="[Dd]uplicate|doc_id"):
        build_index(reader, pipeline, tmp_path)
    assert not (tmp_path / "index.sqlite3").exists()
    assert list(tmp_path.iterdir()) == []
    build_index(MemoryReader([review("unique", "apple")]), pipeline, tmp_path)
    with load_index(tmp_path, pipeline) as index:
        assert [hit.doc_id for hit in search(index, "apple")] == ["unique"]


def test_reader_failure_does_not_publish_partial_index(tmp_path, pipeline):
    class BrokenReader:
        def iter_reviews(self):
            yield review("d1", "apple")
            raise RuntimeError("fixture upstream failure")

    with pytest.raises(RuntimeError, match="fixture upstream failure"):
        build_index(BrokenReader(), pipeline, tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("field,value", [("doc_id", ""), ("doc_id", 3), ("text", " ")])
def test_invalid_review_identity_or_text_is_rejected(tmp_path, pipeline, field, value):
    record = review("d1", "apple")
    record[field] = value
    with pytest.raises((ValueError, TypeError)):
        build_index(MemoryReader([record]), pipeline, tmp_path)
    assert not (tmp_path / "index.sqlite3").exists()


def test_build_refuses_to_overwrite_existing_index(persisted, pipeline):
    directory, _ = persisted
    before = (directory / "index.sqlite3").read_bytes()
    with pytest.raises(FileExistsError):
        build_index(MemoryReader([review("new", "pear")]), pipeline, directory)
    assert (directory / "index.sqlite3").read_bytes() == before


def test_load_rejects_different_tokenizer_policy(persisted):
    with pytest.raises(ValueError, match="[Ff]ingerprint|[Tt]okenizer|policy"):
        load_index(persisted[0], create_tokenizer_pipeline())


def test_query_rejects_tokenizer_policy_changed_after_loading(index, pipeline):
    pipeline.skip_types = frozenset()
    with pytest.raises(ValueError, match="[Ff]ingerprint|[Tt]okenizer|policy"):
        search(index, "apple")


def test_load_rejects_unsupported_persisted_format(persisted, pipeline):
    with sqlite3.connect(persisted[0] / "index.sqlite3") as connection:
        connection.execute("UPDATE metadata SET value='999' WHERE key='format_version'")
    with pytest.raises(ValueError, match="[Ff]ormat|[Vv]ersion"):
        load_index(persisted[0], pipeline)


def test_load_rejects_missing_or_malformed_database(tmp_path, pipeline):
    with pytest.raises(FileNotFoundError):
        load_index(tmp_path, pipeline)
    (tmp_path / "index.sqlite3").write_bytes(b"not a SQLite database")
    with pytest.raises(ValueError):
        load_index(tmp_path, pipeline)


def test_runtime_fixture_resolves_only_upstream():
    upstream = load_interface_module("fixture", "data_corpus_analysis", consumer="search_engine")
    assert upstream.__name__ == "tests.fake.search_engine.data_corpus_analysis"
    assert build_index.__module__.startswith("yelptext.")
    assert search.__module__.startswith("yelptext.")
    assert list(upstream.create_review_reader(REVIEWS).iter_reviews())[0]["doc_id"] == "d1"


def test_cli_build_single_query_batch_and_saved_artifacts(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(ROOT)
    index_dir = tmp_path / "cli-index"
    main(["index", "build", "--config", str(CONFIG), "--output-dir", str(index_dir)])
    built = json.loads(capsys.readouterr().out)
    assert built["status"] == "COMPLETED"
    assert built["stats"]["document_count"] == 4
    assert Path(built["index_path"]).is_file()

    common = ["--config", str(CONFIG), "--index-dir", str(index_dir)]
    for ranker in ("tfidf", "bm25"):
        main(["search", "apple banana", "--ranker", ranker, "--top-k", "2", *common])
        payload = json.loads(capsys.readouterr().out)
        assert payload["query"] == "apple banana"
        assert payload["ranker"] == ranker
        assert payload["top_k"] == 2
        assert [result["doc_id"] for result in payload["results"]] == ["d1", "d2"]
        assert [result["rank"] for result in payload["results"]] == [1, 2]

    output = tmp_path / "results" / "batch.json"
    main([
        "search", "--queries", str(FIXTURES / "queries.toml"),
        "--output", str(output), *common,
    ])
    batch = json.loads(capsys.readouterr().out)
    assert json.loads(output.read_text(encoding="utf-8")) == batch
    assert len(batch["queries"]) == 5
    assert batch["queries"][0]["parameters"] == {"k1": 1.5, "b": 0.75}
    assert batch["queries"][3]["results"] == []
    assert batch["queries"][4]["results"] == []


@pytest.mark.parametrize("args", [
    ["search"],
    ["search", "apple", "--queries", "queries.toml"],
    ["search", "apple", "--ranker", "unknown"],
])
def test_cli_requires_one_query_source_and_known_ranker(args):
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2


@pytest.mark.parametrize("queries", ["queries = []", "queries = [1, 2]", 'queries = "apple"'])
def test_cli_rejects_malformed_query_files_before_loading_index(tmp_path, queries):
    query_file = tmp_path / "bad.toml"
    query_file.write_text(queries, encoding="utf-8")
    with pytest.raises(ValueError, match="queries|array"):
        main(["search", "--queries", str(query_file), "--config", str(CONFIG)])


def cli_config(tmp_path, *, tokenizer_extra=""):
    prepared = tmp_path / "reviews.jsonl"
    prepared.write_bytes(REVIEWS.read_bytes())
    index_dir = tmp_path / "index"
    config = tmp_path / "config.toml"
    config.write_text(
        '[runtime]\nmode = "fixture"\n[data]\n'
        f'prepared_path = {json.dumps(prepared.as_posix())}\n'
        '[tokenizer]\nskip_types = ["punctuation"]\nenable_pos = false\n'
        f'{tokenizer_extra}\n[index]\noutput_dir = {json.dumps(index_dir.as_posix())}\n'
        '[search]\ntop_k = 10\n[search.bm25]\nk1 = 1.5\nb = 0.75\n',
        encoding="utf-8",
    )
    return config, prepared, index_dir


def test_cli_rejects_unsupported_canonical_policy_switch(tmp_path):
    config, _, index_dir = cli_config(tmp_path, tokenizer_extra="lowercase = false")
    with pytest.raises(ValueError, match="lowercase"):
        main(["index", "build", "--config", str(config)])
    assert not (index_dir / "index.sqlite3").exists()


def test_cli_real_upstream_uses_same_small_corpus_without_global_vocabulary(tmp_path, capsys):
    config, _, index_dir = cli_config(tmp_path)
    config.write_text(
        config.read_text(encoding="utf-8").replace('mode = "fixture"', 'mode = "real"'),
        encoding="utf-8",
    )
    main(["index", "build", "--config", str(config)])
    built = json.loads(capsys.readouterr().out)
    assert built["stats"]["document_count"] == 4
    assert built["stats"]["total_terms"] == 9
    assert not built["stats"]["tokenizer_fingerprint"].startswith("fixture:")
    main(["search", "apple banana", "--config", str(config), "--ranker", "bm25"])
    payload = json.loads(capsys.readouterr().out)
    assert [hit["doc_id"] for hit in payload["results"]] == ["d1", "d2", "d3"]
    assert payload["results"][0]["score"] == pytest.approx(math.log(2) * (40 / 31 + 20 / 23))
    assert payload["results"][0]["business_name"] == "Café 苹果"
    with pytest.raises(ValueError, match="[Ff]ingerprint|[Tt]okenizer|policy"):
        load_index(index_dir, create_tokenizer_pipeline(skip_types={"punctuation"}))


def test_cli_rejects_nonpositive_top_k(tmp_path, capsys):
    config, _, _ = cli_config(tmp_path)
    main(["index", "build", "--config", str(config)])
    capsys.readouterr()
    with pytest.raises(ValueError, match="top_k"):
        main(["search", "apple", "--config", str(config), "--top-k", "0"])


@pytest.mark.parametrize("target", ["index", "config", "prepared", "queries"])
def test_cli_result_output_cannot_overwrite_inputs(tmp_path, capsys, target):
    config, prepared, index_dir = cli_config(tmp_path)
    queries = tmp_path / "queries.toml"
    queries.write_text('queries = ["apple"]\n', encoding="utf-8")
    main(["index", "build", "--config", str(config)])
    capsys.readouterr()
    path = {
        "index": index_dir / "index.sqlite3", "config": config,
        "prepared": prepared, "queries": queries,
    }[target]
    before = path.read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        main([
            "search", "--queries", str(queries), "--config", str(config),
            "--output", str(path),
        ])
    assert path.read_bytes() == before

