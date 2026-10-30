"""Real data/corpus facilities exposed to commands and downstream groups."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from yelptext.implementation.data_corpus_analysis.preparation import (
    prepare_reviews as _prepare_reviews,
)
from yelptext.implementation.data_corpus_analysis.reviewer import (
    JsonlPreparedReviewReader,
    YelpDataError,
)
from yelptext.implementation.data_corpus_analysis.sampling import (
    sample_reviews as _sample_reviews,
)
from yelptext.implementation.data_corpus_analysis.tokenizer import RegexTokenizer
from yelptext.implementation.data_corpus_analysis.tokenizer.build_vocab_sqlite import (
    build_sqlite_vocabulary as _build_sqlite_vocabulary,
)
from yelptext.protocol.reviewer import PreparedReviewReader
from yelptext.protocol.tokenizer import Tokenizer


def prepare_reviews(
    review_path: str | Path,
    business_path: str | Path,
    output_path: str | Path,
    *,
    limit: int | None = None,
    long_text_threshold: int = 50_000,
) -> dict[str, Any]:
    """Create the canonical prepared-review file and audit artifacts."""

    return _prepare_reviews(
        review_path,
        business_path,
        output_path,
        limit=limit,
        long_text_threshold=long_text_threshold,
    )


def create_review_reader(prepared_path: str | Path) -> PreparedReviewReader:
    """Construct a streaming reader for canonical prepared-review JSONL."""

    return JsonlPreparedReviewReader(prepared_path)


def create_tokenizer() -> Tokenizer:
    """Construct the canonical vocabulary-independent shared tokenizer."""

    return RegexTokenizer()


def sample_reviews(
    input_path: str | Path,
    output_path: str | Path,
    *,
    sample_size: int,
    seed: int = 6122,
) -> dict[str, object]:
    """Write a deterministic sample while preserving every input field."""

    return _sample_reviews(
        input_path,
        output_path,
        sample_size=sample_size,
        seed=seed,
    )


def build_vocabulary(
    review_path: str | Path,
    output_path: str | Path,
    *,
    buffer_unique_terms: int = 100_000,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, object]:
    """Explicitly build the canonical disk-backed vocabulary artifact."""

    return _build_sqlite_vocabulary(
        review_path,
        output_path,
        buffer_unique_terms=buffer_unique_terms,
        progress=progress,
    )


__all__ = [
    "YelpDataError",
    "build_vocabulary",
    "create_review_reader",
    "create_tokenizer",
    "prepare_reviews",
    "sample_reviews",
]
