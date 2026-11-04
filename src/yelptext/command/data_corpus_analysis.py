"""Command orchestration for data preparation and corpus analysis."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

from yelptext.interface.data_corpus_analysis import (
    analyze_heaps,
    analyze_zipf,
    build_vocabulary,
    compare_tokenizers,
    prepare_reviews,
    sample_reviews,
)
from yelptext.runtime.config import load_config


def _configured_path(
    args_value: Path | None,
    data: Mapping[str, object],
    key: str,
) -> Path:
    if args_value is not None:
        return args_value
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Configuration must define [data].{key}")
    return Path(value)


def run_prepare(args: argparse.Namespace) -> None:
    """Prepare canonical review JSONL using CLI overrides or config paths."""

    config = load_config(args.config)
    data = config.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("Configuration must define [data]")
    report = prepare_reviews(
        _configured_path(args.reviews, data, "review_path"),
        _configured_path(args.businesses, data, "business_path"),
        _configured_path(args.output, data, "prepared_path"),
        limit=args.limit,
        long_text_threshold=args.long_text_threshold,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def run_build_vocabulary(args: argparse.Namespace) -> None:
    """Build the shared vocabulary only when explicitly requested."""

    config = load_config(args.config)
    data = config.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("Configuration must define [data]")
    tokenizer = config.get("tokenizer")
    if not isinstance(tokenizer, Mapping):
        raise ValueError("Configuration must define [tokenizer]")

    output_value = args.output
    if output_value is None:
        configured = tokenizer.get("vocabulary_path")
        if not isinstance(configured, str) or not configured:
            raise ValueError("Configuration must define [tokenizer].vocabulary_path")
        output_value = Path(configured)

    def report_progress(phase: str, documents: int, tokens: int) -> None:
        print(
            f"[{phase}] documents={documents:,} tokens={tokens:,}",
            file=sys.stderr,
            flush=True,
        )

    report = build_vocabulary(
        _configured_path(args.reviews, data, "review_path"),
        output_value,
        buffer_unique_terms=args.buffer_unique_terms,
        progress=report_progress,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def run_sample(args: argparse.Namespace) -> None:
    """Create a reusable schema-preserving review sample."""

    config = load_config(args.config)
    data = config.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("Configuration must define [data]")

    configured_seed = data.get("random_seed")
    seed = args.seed if args.seed is not None else configured_seed
    if not isinstance(seed, int):
        raise ValueError("Sampling requires an integer --seed or [data].random_seed")

    report = sample_reviews(
        _configured_path(args.input, data, "prepared_path"),
        _configured_path(args.output, data, "sample_path"),
        sample_size=args.size,
        seed=seed,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _analysis_settings(config: Mapping[str, object], name: str) -> Mapping[str, object]:
    analysis = config.get("analysis", {})
    if not isinstance(analysis, Mapping):
        raise ValueError("Configuration [analysis] must be a table")
    settings = analysis.get(name, {})
    if not isinstance(settings, Mapping):
        raise ValueError(f"Configuration [analysis.{name}] must be a table")
    return settings


def _required_config_path(
    section: Mapping[str, object], key: str, label: str
) -> Path:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Configuration must define [{label}].{key}")
    return Path(value)


def run_zipf_analysis(args: argparse.Namespace) -> None:
    """Generate reproducible Zipf artifacts without executing a notebook."""
    config = load_config(args.config)
    tokenizer = config.get("tokenizer")
    if not isinstance(tokenizer, Mapping):
        raise ValueError("Configuration must define [tokenizer]")
    settings = _analysis_settings(config, "zipf")
    output_dir = args.output_dir or _required_config_path(
        settings, "output_dir", "analysis.zipf"
    )
    analyze_zipf(
        _required_config_path(tokenizer, "vocabulary_path", "tokenizer"),
        output_dir,
        backup_root=Path.cwd(),
    )


def run_heaps_analysis(args: argparse.Namespace) -> None:
    """Generate reproducible randomized-order Heaps artifacts."""
    config = load_config(args.config)
    data = config.get("data")
    tokenizer = config.get("tokenizer")
    if not isinstance(data, Mapping) or not isinstance(tokenizer, Mapping):
        raise ValueError("Configuration must define [data] and [tokenizer]")
    settings = _analysis_settings(config, "heaps")
    configured_seed = settings.get("seed", 2026)
    seed = args.seed if args.seed is not None else configured_seed
    if type(seed) is not int:
        raise ValueError("Heaps seed must be an integer")
    keep_random_order = (
        True if args.keep_random_order else settings.get("keep_random_order", False)
    )
    if not isinstance(keep_random_order, bool):
        raise ValueError("[analysis.heaps].keep_random_order must be boolean")
    output_dir = args.output_dir or _required_config_path(
        settings, "output_dir", "analysis.heaps"
    )
    analyze_heaps(
        _required_config_path(data, "prepared_path", "data"),
        _required_config_path(tokenizer, "vocabulary_path", "tokenizer"),
        output_dir,
        seed=seed,
        keep_random_order=keep_random_order,
        backup_root=Path.cwd(),
    )


def run_tokenizer_comparison(args: argparse.Namespace) -> None:
    """Generate tokenizer comparison artifacts outside the report notebook."""
    config = load_config(args.config)
    data = config.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("Configuration must define [data]")
    settings = _analysis_settings(config, "tokenizers")
    sample_path = _required_config_path(data, "sample_path", "data")
    output_dir = args.output_dir or _required_config_path(
        settings, "output_dir", "analysis.tokenizers"
    )
    expected_reviews = settings.get("sample_size", 50_000)
    seed = settings.get("seed", data.get("random_seed", 42))
    benchmark_reviews = settings.get("benchmark_reviews", 500)
    benchmark_repeats = settings.get("benchmark_repeats", 5)
    result = compare_tokenizers(
        sample_path,
        output_dir,
        expected_reviews=expected_reviews,
        seed=seed,
        benchmark_reviews=benchmark_reviews,
        benchmark_repeats=benchmark_repeats,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
