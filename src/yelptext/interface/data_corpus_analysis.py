"""Real data/corpus facilities exposed to commands and downstream groups."""

from __future__ import annotations

from collections.abc import Callable, Iterable
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
from yelptext.implementation.data_corpus_analysis.tokenizer import (
    POS_TAGS,
    RegexTokenizer,
    create_pipeline as _create_tokenizer_pipeline,
)
from yelptext.implementation.data_corpus_analysis.tokenizer.classification import (
    STABLE_TOKEN_TYPES,
)
from yelptext.implementation.data_corpus_analysis.tokenizer.build_vocab_sqlite import (
    build_sqlite_vocabulary as _build_sqlite_vocabulary,
)
from yelptext.protocol.reviewer import PreparedReviewReader
from yelptext.protocol.tokenizer import (
    AnalyzedToken,
    Tokenizer,
    TokenizerPipeline,
)


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


def create_tokenizer_pipeline(
    *,
    skip_types: Iterable[str] = (),
    enable_pos: bool = False,
) -> TokenizerPipeline:
    """Construct the shared tokenizer with classification, POS, and filtering.

    ``tokenize()`` retains the canonical unfiltered tokenizer contract.
    Downstream consumers call ``analyze()`` for tagged occurrences or
    ``terms()`` for filtered strings. POS tagging is opt-in and requires the
    NLTK averaged perceptron tagger resource.
    """

    return _create_tokenizer_pipeline(
        skip_types=skip_types,
        enable_pos=enable_pos,
    )


def available_token_types(*, include_pos: bool = False) -> frozenset[str]:
    """Return valid tags accepted by ``create_tokenizer_pipeline`` filters."""

    return STABLE_TOKEN_TYPES | (POS_TAGS if include_pos else frozenset())


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
    "AnalyzedToken",
    "Tokenizer",
    "TokenizerPipeline",
    "YelpDataError",
    "available_token_types",
    "build_vocabulary",
    "create_review_reader",
    "create_tokenizer",
    "create_tokenizer_pipeline",
    "prepare_reviews",
    "sample_reviews",
]
