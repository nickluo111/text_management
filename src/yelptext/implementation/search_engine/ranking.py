"""From-scratch TF-IDF cosine and BM25 over a common inverted index."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import heapq
import json
import math

from yelptext.implementation.search_engine.index import SearchIndex, _terms


@dataclass(frozen=True)
class SearchResult:
    doc_id: str
    score: float
    text: str
    business_id: str | None
    business_name: str | None
    stars: float | None
    city: str | None
    state: str | None


def _validate_parameters(ranker: str, top_k: int, k1: float, b: float) -> None:
    if ranker not in ("tfidf", "bm25"):
        raise ValueError("ranker must be 'tfidf' or 'bm25'")
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    if (
        isinstance(k1, bool)
        or not isinstance(k1, (int, float))
        or not math.isfinite(k1)
        or k1 <= 0
    ):
        raise ValueError("BM25 k1 must be finite and greater than zero")
    if (
        isinstance(b, bool)
        or not isinstance(b, (int, float))
        or not math.isfinite(b)
        or not 0 <= b <= 1
    ):
        raise ValueError("BM25 b must be finite and between zero and one")


def search(
    index: SearchIndex,
    query: str,
    *,
    ranker: str = "bm25",
    top_k: int = 10,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[SearchResult]:
    """Return positive-scoring matches, ordered by score then ``doc_id``.

    TF-IDF uses logarithmic TF, smoothed IDF and cosine normalization. OOV query
    terms are removed before query normalization. BM25 uses positive IDF and
    multiplies each term contribution by its query frequency. No-match queries
    return an empty list instead of arbitrary zero-scoring documents.
    """

    # The compact backend changes representation/execution, not scoring policy.
    from .compact import CompactSearchIndex, search_compact
    if isinstance(index, CompactSearchIndex):
        return search_compact(index, query, ranker=ranker, top_k=top_k, k1=k1, b=b)
    _validate_parameters(ranker, top_k, k1, b)
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    index._check_tokenizer()
    query_counts = Counter(_terms(index._tokenizer, query))
    connection = index._connection
    scores: dict[str, float] = defaultdict(float)
    query_norm_squared = 0.0
    document_count = index._metadata["document_count"]
    average_length = index._metadata["avgdl"]

    # A fixed term traversal order makes equivalent reordered queries stable.
    for term, query_tf in sorted(query_counts.items()):
        term_statistics = connection.execute(
            "SELECT df, idf FROM terms WHERE term = ?", (term,)
        ).fetchone()
        if term_statistics is None:
            continue
        df, tfidf_idf = term_statistics
        if ranker == "tfidf":
            query_weight = (1.0 + math.log(query_tf)) * tfidf_idf
            query_norm_squared += query_weight ** 2
        else:
            bm25_idf = math.log1p((document_count - df + 0.5) / (df + 0.5))

        postings = connection.execute(
            "SELECT d.doc_id, p.tf, d.length, d.norm FROM postings p "
            "JOIN documents d ON d.docno = p.docno WHERE p.term = ?",
            (term,),
        )
        for doc_id, tf, document_length, document_norm in postings:
            if ranker == "tfidf":
                document_weight = (1.0 + math.log(tf)) * tfidf_idf
                scores[doc_id] += document_weight * query_weight / document_norm
            else:
                length_normalization = 1.0 - b + b * document_length / average_length
                # Dividing numerator and denominator by k1 for large values
                # avoids overflowing intermediate products for finite inputs.
                if k1 >= 1:
                    tf_weight = tf * (1.0 + 1.0 / k1) / (tf / k1 + length_normalization)
                else:
                    tf_weight = tf * (k1 + 1.0) / (tf + k1 * length_normalization)
                scores[doc_id] += bm25_idf * tf_weight * query_tf

    if ranker == "tfidf" and query_norm_squared:
        query_norm = math.sqrt(query_norm_squared)
        scores = {doc_id: score / query_norm for doc_id, score in scores.items()}

    best = heapq.nsmallest(
        top_k,
        ((doc_id, score) for doc_id, score in scores.items() if score > 0),
        key=lambda result: (-result[1], result[0]),
    )
    results = []
    for doc_id, score in best:
        (serialized,) = connection.execute(
            "SELECT review_json FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        review = json.loads(serialized)
        results.append(SearchResult(
            doc_id=doc_id,
            score=score,
            text=review["text"],
            business_id=review.get("business_id"),
            business_name=review.get("business_name"),
            stars=review.get("stars"),
            city=review.get("city"),
            state=review.get("state"),
        ))
    return results

