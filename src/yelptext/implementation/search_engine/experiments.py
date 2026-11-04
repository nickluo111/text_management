"""Reproducible ranking comparisons without unjudged relevance claims.

This module runs the real rankers against a persisted index. Overlap, term
coverage, and document length describe retrieval behavior; none is a substitute
for relevance judgments. Presentation belongs in the report notebook.
"""

from __future__ import annotations

from collections.abc import Sequence
import csv
from dataclasses import asdict
import io
import json
import os
from pathlib import Path
import statistics
import tempfile
from time import perf_counter
from typing import Any

from .index import SearchIndex, _terms
from .ranking import SearchResult, _validate_parameters, search


def _comparison(
    left: list[dict[str, Any]], right: list[dict[str, Any]],
) -> dict[str, Any]:
    left_ranks = {hit["doc_id"]: hit["rank"] for hit in left}
    right_ranks = {hit["doc_id"]: hit["rank"] for hit in right}
    common = left_ranks.keys() & right_ranks.keys()
    union = left_ranks.keys() | right_ranks.keys()
    return {
        "overlap_count": len(common),
        "jaccard": len(common) / len(union) if union else None,
        "top1_match": left[0]["doc_id"] == right[0]["doc_id"] if left and right else None,
        # Positive means a document moved closer to the top under BM25.
        "common_rank_shifts": [
            {
                "doc_id": doc_id,
                "tfidf_rank": left_ranks[doc_id],
                "bm25_rank": right_ranks[doc_id],
                "shift_to_bm25": left_ranks[doc_id] - right_ranks[doc_id],
            }
            for doc_id in sorted(common, key=lambda item: left_ranks[item])
        ],
    }


def _summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mean_document_length": (
            statistics.mean(hit["document_length"] for hit in results) if results else None
        ),
        "all_query_terms_coverage": (
            sum(hit["all_query_terms_matched"] for hit in results) / len(results)
            if results else None
        ),
    }


def _enrich(
    index: SearchIndex,
    results: list[SearchResult],
    query_terms: set[str],
    document_terms: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Calculate display diagnostics outside the search timing interval."""
    enriched = []
    for rank, hit in enumerate(results, 1):
        if hit.doc_id not in document_terms:
            document_terms[hit.doc_id] = _terms(index._tokenizer, hit.text)
        terms = document_terms[hit.doc_id]
        matched = query_terms.intersection(terms)
        enriched.append({
            "rank": rank,
            **asdict(hit),
            "document_length": len(terms),
            "matched_query_terms": sorted(matched),
            # Includes OOV query terms, so an impossible full match is not
            # silently reported as complete coverage of only the known subset.
            "all_query_terms_matched": bool(query_terms) and query_terms <= matched,
        })
    return enriched


def _timed_search(
    index: SearchIndex, query: str, ranker: str, top_k: int,
    k1: float, b: float, repeats: int,
) -> tuple[list[SearchResult], dict[str, Any]]:
    search(index, query, ranker=ranker, top_k=top_k, k1=k1, b=b)
    runs_ms = []
    for _ in range(repeats):
        start = perf_counter()
        results = search(index, query, ranker=ranker, top_k=top_k, k1=k1, b=b)
        runs_ms.append((perf_counter() - start) * 1000)
    return results, {
        "median_ms": statistics.median(runs_ms),
        "min_ms": min(runs_ms),
        "runs_ms": runs_ms,
    }


def _write_atomic(path: Path, content: str) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _csv_content(rows: list[dict[str, Any]], fields: list[str]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _export(report: dict[str, Any], output_dir: Path) -> None:
    ranking_rows, comparison_rows, parameter_rows = [], [], []
    for record in report["queries"]:
        rankers = record["rankers"]
        for ranker, run in rankers.items():
            for hit in run["results"]:
                ranking_rows.append({
                    "query": record["query"], "ranker": ranker,
                    **{key: value for key, value in hit.items() if key not in {"text", "matched_query_terms"}},
                    "matched_query_terms": json.dumps(hit["matched_query_terms"], ensure_ascii=False),
                    "text_excerpt": " ".join(hit["text"].split())[:300],
                })
        comparison_rows.append({
            "query": record["query"], "top_k": report["settings"]["top_k"],
            "tfidf_results": len(rankers["tfidf"]["results"]),
            "bm25_results": len(rankers["bm25"]["results"]),
            **{key: record["comparison"][key] for key in ("overlap_count", "jaccard", "top1_match")},
            **{
                f"{ranker}_{key}": rankers[ranker][key]
                for ranker in ("tfidf", "bm25")
                for key in ("mean_document_length", "all_query_terms_coverage")
            },
            "tfidf_median_ms": rankers["tfidf"]["timing"]["median_ms"],
            "bm25_median_ms": rankers["bm25"]["timing"]["median_ms"],
            "known_terms": json.dumps(record["known_terms"], ensure_ascii=False),
            "oov_terms": json.dumps(record["oov_terms"], ensure_ascii=False),
        })
        for variant in record["bm25_parameters"]:
            results = variant["results"]
            parameter_rows.append({
                "query": record["query"],
                **{key: value for key, value in variant.items() if key != "results"},
                "top_doc_id": results[0]["doc_id"] if results else None,
                "ranking_doc_ids": json.dumps([hit["doc_id"] for hit in results], ensure_ascii=False),
            })

    tables = (
        ("rankings.csv", ranking_rows, [
            "query", "ranker", "rank", "doc_id", "score", "business_id", "business_name",
            "stars", "city", "state", "document_length", "matched_query_terms",
            "all_query_terms_matched", "text_excerpt",
        ]),
        ("comparison.csv", comparison_rows, [
            "query", "top_k", "tfidf_results", "bm25_results", "overlap_count", "jaccard",
            "top1_match", "tfidf_mean_document_length", "tfidf_all_query_terms_coverage",
            "bm25_mean_document_length", "bm25_all_query_terms_coverage", "tfidf_median_ms",
            "bm25_median_ms", "known_terms", "oov_terms",
        ]),
        ("bm25_parameters.csv", parameter_rows, [
            "query", "k1", "b", "overlap_with_default", "default_jaccard",
            "top1_matches_default", "mean_document_length", "all_query_terms_coverage",
            "top_doc_id", "ranking_doc_ids",
        ]),
    )
    # Calculate all serializations before modifying any previous artifact.
    exports = [(name, _csv_content(rows, fields)) for name, rows, fields in tables]
    exports.append(("report.json", json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"))
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in exports:
        _write_atomic(output_dir / name, content)


def run_experiment(
    index: SearchIndex,
    queries: Sequence[str],
    output_dir: str | Path,
    *,
    top_k: int = 10,
    k1: float = 1.5,
    b: float = 0.75,
    repeats: int = 3,
) -> dict[str, Any]:
    """Compare TF-IDF/BM25, save tables, and return a JSON-compatible report.

    The caller supplies provenance and chooses the document set. This function
    never labels synthetic input as real Yelp data and does not impose the
    notebook's 50,000-document or five-query experiment requirements.

    Every ranker/query gets one untimed warm-up and ``repeats`` timed calls in
    the same process. Retokenization for display, CSV generation, and parameter
    sensitivity runs occur outside timed regions. These are warm query latency
    observations, not cold-start, multi-user, or hardware-controlled benchmarks.

    Coverage is the fraction of returned documents containing every unique
    filtered query term, including OOV terms. Empty result sets have null
    coverage, mean length, Jaccard, and top-result agreement where undefined.
    """
    _validate_parameters("bm25", top_k, k1, b)
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    if isinstance(queries, (str, bytes)) or not isinstance(queries, Sequence) or not queries:
        raise ValueError("queries must be a non-empty sequence of query strings")
    if any(not isinstance(query, str) or not query.strip() for query in queries):
        raise ValueError("Every experiment query must be a nonblank string")
    if len(set(queries)) != len(queries):
        raise ValueError("Experiment queries must be unique")
    index._check_tokenizer()

    report = {
        "schema_version": 1,
        "corpus": index.stats(),
        "settings": {
            "top_k": top_k, "k1": k1, "b": b, "repeats": repeats,
            "notes": [
                "Timing: one untimed warm-up per query/ranker, followed by repeated calls in the same process; times are milliseconds.",
                "Timing includes query tokenization, scoring, sorting, and result loading; diagnostic tokenization and exports are excluded.",
                "TF-IDF is timed before BM25 for each query; caches are not reset. Timings are observations, not a controlled benchmark.",
                "Overlap, lexical coverage, and retrieved document length describe ranking behavior; they are not relevance metrics.",
                "Coverage requires all unique filtered query terms, including OOV terms; empty result sets use null rather than a perfect score.",
                "BM25 settings are a sensitivity comparison, not parameters optimized against relevance judgments.",
            ],
        },
        "queries": [],
    }
    parameter_settings = list(dict.fromkeys([(k1, b), (k1, 0.0), (k1, 1.0), (0.5, b), (2.0, b)]))
    cached_document_terms: dict[str, list[str]] = {}
    for query in queries:
        terms = _terms(index._tokenizer, query)
        unique_terms = set(terms)
        # Compact full-corpus indexes expose DF directly: do not allocate a
        # million-document posting list merely to count its entries.
        document_frequencies = {
            term: index.term_df(term) if hasattr(index, "term_df") else len(index.postings(term))
            for term in sorted(unique_terms)
        }
        record = {
            "query": query,
            "terms": terms,
            "known_terms": [term for term, count in document_frequencies.items() if count],
            "oov_terms": [term for term, count in document_frequencies.items() if not count],
            "term_document_frequencies": document_frequencies,
            "rankers": {},
            "bm25_parameters": [],
        }
        for ranker in ("tfidf", "bm25"):
            results, timing = _timed_search(index, query, ranker, top_k, k1, b, repeats)
            enriched = _enrich(index, results, unique_terms, cached_document_terms)
            record["rankers"][ranker] = {
                "results": enriched, "timing": timing, **_summarize_results(enriched),
            }
        left = record["rankers"]["tfidf"]["results"]
        baseline = record["rankers"]["bm25"]["results"]
        record["comparison"] = _comparison(left, baseline)
        for variant_k1, variant_b in parameter_settings:
            if (variant_k1, variant_b) == (k1, b):
                enriched = baseline
            else:
                results = search(index, query, ranker="bm25", top_k=top_k, k1=variant_k1, b=variant_b)
                enriched = _enrich(index, results, unique_terms, cached_document_terms)
            comparison = _comparison(baseline, enriched)
            record["bm25_parameters"].append({
                "k1": variant_k1, "b": variant_b,
                "overlap_with_default": comparison["overlap_count"],
                "default_jaccard": comparison["jaccard"],
                "top1_matches_default": comparison["top1_match"],
                "results": enriched,
                **_summarize_results(enriched),
            })
        report["queries"].append(record)
    _export(report, Path(output_dir))
    return report

