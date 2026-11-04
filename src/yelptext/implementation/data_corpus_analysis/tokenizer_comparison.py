"""Controlled comparison of the shared tokenizer with two NLTK baselines."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import platform
import statistics
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nltk
from nltk.tokenize import WhitespaceTokenizer, WordPunctTokenizer
import pandas as pd


_CASES = {
    "contractions": "Don't can't I'm we've y'all's didn't.",
    "hyphens": "state-of-the-art the-best-food",
    "numbers": "12.50 1,234.50 $10 250$ 50¢ 10+ 20+% 29°F",
    "url": "Visit https://my-site.com/menu?a=1&b=2!!!",
    "emoji": "Good😂😂 👍🏽 👨‍👩‍👧‍👦 🇺🇸 1️⃣",
    "punctuation": "Really?!!!! #deal #",
    "emoticons": r":) XD :D :( ;-) ^_^ o_o ¯\_(ツ)_/¯",
}


def compare_tokenizers(
    reader: Any,
    tokenizer: Any,
    sample_path: str | Path,
    output_dir: str | Path,
    *,
    expected_reviews: int = 50_000,
    seed: int = 42,
    benchmark_reviews: int = 500,
    benchmark_repeats: int = 5,
) -> dict[str, Any]:
    """Run one reproducible, normalization-controlled tokenizer comparison."""
    for name, value in (
        ("expected_reviews", expected_reviews),
        ("benchmark_reviews", benchmark_reviews),
        ("benchmark_repeats", benchmark_repeats),
    ):
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")

    texts = [review["text"] for review in reader.iter_reviews()]
    if len(texts) != expected_reviews:
        raise ValueError(
            f"Expected {expected_reviews:,} sampled reviews, found {len(texts):,}. "
            "Regenerate the configured sample before comparing tokenizers."
        )
    if benchmark_reviews > len(texts):
        raise ValueError("benchmark_reviews cannot exceed expected_reviews")

    whitespace = WhitespaceTokenizer()
    wordpunct = WordPunctTokenizer()
    methods = {
        "NLTK Whitespace": lambda text: whitespace.tokenize(tokenizer.normalize(text)),
        "NLTK WordPunct": lambda text: wordpunct.tokenize(tokenizer.normalize(text)),
        "Custom Yelp": tokenizer.tokenize,
    }

    rows: list[dict[str, Any]] = []
    for name, tokenize in methods.items():
        counts: Counter[str] = Counter()
        started = time.perf_counter()
        for text in texts:
            counts.update(tokenize(text))
        elapsed = time.perf_counter() - started
        token_total = int(sum(counts.values()))
        vocabulary_size = len(counts)
        hapax_types = sum(frequency == 1 for frequency in counts.values())
        rows.append(
            {
                "tokenizer": name,
                "reviews": len(texts),
                "tokens": token_total,
                "vocabulary": vocabulary_size,
                "hapax_types": hapax_types,
                "hapax_share": hapax_types / vocabulary_size,
                "tokens_per_review": token_total / len(texts),
                "processing_seconds": elapsed,
                "reviews_per_second_including_counting": len(texts) / elapsed,
            }
        )

    benchmark_texts = texts[:benchmark_reviews]
    timings = {name: [] for name in methods}
    method_items = list(methods.items())
    for repeat in range(benchmark_repeats):
        offset = repeat % len(method_items)
        rotated = method_items[offset:] + method_items[:offset]
        for name, tokenize in rotated:
            started = time.perf_counter()
            token_guard = sum(len(tokenize(text)) for text in benchmark_texts)
            timings[name].append(time.perf_counter() - started)
            if token_guard <= 0:
                raise ValueError(f"{name} produced no benchmark tokens")
    benchmark_rows = []
    for name, values in timings.items():
        median_seconds = statistics.median(values)
        benchmark_rows.append(
            {
                "tokenizer": name,
                "reviews": len(benchmark_texts),
                "repeats": len(values),
                "median_seconds": median_seconds,
                "median_reviews_per_second": len(benchmark_texts) / median_seconds,
            }
        )

    qualitative_rows = []
    for feature, text in _CASES.items():
        for name, tokenize in methods.items():
            qualitative_rows.append(
                {
                    "feature": feature,
                    "tokenizer": name,
                    "tokens": json.dumps(tokenize(text), ensure_ascii=False),
                }
            )

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(rows)
    benchmark = pd.DataFrame(benchmark_rows)
    qualitative = pd.DataFrame(qualitative_rows)
    summary.to_csv(output / "summary.csv", index=False)
    benchmark.to_csv(output / "runtime_benchmark.csv", index=False)
    qualitative.to_csv(output / "qualitative_cases.csv", index=False)

    colors = ["#8A94A6", "#5D83A6", "#C47A44"]
    figure, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    for axis, (column, title) in zip(
        axes.flat[:3],
        (
            ("tokens", "Total tokens"),
            ("vocabulary", "Vocabulary size"),
            ("hapax_share", "Hapax share of vocabulary"),
        ),
    ):
        axis.bar(summary["tokenizer"], summary[column], color=colors)
        axis.set_title(title)
        axis.tick_params(axis="x", rotation=15)
        axis.grid(axis="y", alpha=0.2)
    axes.flat[3].bar(
        benchmark["tokenizer"], benchmark["median_reviews_per_second"], color=colors
    )
    axes.flat[3].set_title("Bounded benchmark throughput")
    axes.flat[3].set_ylabel("Reviews / second")
    axes.flat[3].tick_params(axis="x", rotation=15)
    axes.flat[3].grid(axis="y", alpha=0.2)
    figure.suptitle("Tokenizer comparison on the same seed-42 Yelp sample", fontsize=15)
    figure.savefig(output / "tokenizer_comparison.png", dpi=220)
    plt.close(figure)

    result = {
        "status": "COMPLETED",
        "sample_path": str(Path(sample_path).resolve()),
        "sample_size": expected_reviews,
        "seed": seed,
        "normalization": "Shared RegexTokenizer.normalize applied to every method",
        "retention": "all tokens; no stopword, stemming, lemmatization, or punctuation filter",
        "python": platform.python_version(),
        "nltk": nltk.__version__,
        "results": rows,
        "benchmark": benchmark_rows,
    }
    temporary = output / "summary.json.tmp"
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output / "summary.json")
    return result


__all__ = ["compare_tokenizers"]
