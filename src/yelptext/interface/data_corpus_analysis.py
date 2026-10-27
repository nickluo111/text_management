"""Real data/corpus facilities exposed to downstream groups."""

from __future__ import annotations

from pathlib import Path

from yelptext.implementation.data_corpus_analysis.reviewer import (
    OrphanPolicy,
    YelpDataError,
    YelpReviewReader,
)
from yelptext.protocol.reviewer import PreparedReviewReader


def create_review_reader(
    review_path: str | Path,
    business_path: str | Path,
    *,
    orphan_policy: OrphanPolicy = "error",
) -> PreparedReviewReader:
    """Construct the real prepared-review reader from raw Yelp JSONL paths."""

    return YelpReviewReader(
        review_path,
        business_path,
        orphan_policy=orphan_policy,
    )


__all__ = ["YelpDataError", "create_review_reader"]
