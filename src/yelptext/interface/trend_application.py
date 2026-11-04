"""Public interface for trend-analysis applications."""

from yelptext.implementation.trend_application.comparisons import (
    comparison_pattern,
    scan_comparisons,
    split_sentences,
)

__all__ = ["comparison_pattern", "scan_comparisons", "split_sentences"]
