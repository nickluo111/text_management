"""Command orchestration for trend and application analyses."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from yelptext.implementation.trend_application.sentiment import (
    SectorDefinition,
    analyze_sector_sentiment,
)
from yelptext.implementation.trend_application.pmi import analyze_pmi_drift
from yelptext.interface.data_corpus_analysis import (
    create_review_reader,
    create_tokenizer_pipeline,
)
from yelptext.runtime.config import load_config


_SENTIMENT_FIELDS = [
    "sector",
    "period",
    "review_count",
    "mean_compound",
    "compound_ci_lower",
    "compound_ci_upper",
    "positive_share",
    "neutral_share",
    "negative_share",
    "mean_stars",
]


def _optional_date(value: str | None, option: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{option} must use YYYY-MM-DD") from exc


def _configured_sectors(sentiment: Mapping[str, object]) -> list[SectorDefinition]:
    raw_sectors = sentiment.get("sectors")
    if not isinstance(raw_sectors, list):
        raise ValueError("Configuration must define [[trends.sentiment.sectors]]")
    sectors: list[SectorDefinition] = []
    for item in raw_sectors:
        if not isinstance(item, Mapping):
            raise ValueError("Each sentiment sector must be a table")
        name = item.get("name")
        categories = item.get("categories")
        if not isinstance(name, str) or not isinstance(categories, list) or any(
            not isinstance(category, str) for category in categories
        ):
            raise ValueError("Each sector needs a string name and categories list")
        sectors.append(SectorDefinition(name, frozenset(categories)))
    return sectors


def _select_sectors(
    configured: list[SectorDefinition], requested: str | None
) -> list[SectorDefinition]:
    if requested is None:
        return configured
    names = list(
        dict.fromkeys(name.strip() for name in requested.split(",") if name.strip())
    )
    if not names:
        raise ValueError("--sectors must contain at least one sector name")
    by_name = {sector.name: sector for sector in configured}
    unknown = [name for name in names if name not in by_name]
    if unknown:
        raise ValueError(
            f"Unknown sectors {unknown}; configured sectors are {list(by_name)}"
        )
    return [by_name[name] for name in names]


def _write_sentiment_figure(
    rows: list[dict[str, object]],
    sectors: list[SectorDefinition],
    path: Path,
) -> None:
    figure, (score_axis, count_axis) = plt.subplots(
        2, 1, figsize=(10, 7), sharex=True
    )
    plotted = False
    for sector in sectors:
        series = [row for row in rows if row["sector"] == sector.name]
        if not series:
            continue
        plotted = True
        periods = [str(row["period"]) for row in series]
        means = [float(row["mean_compound"]) for row in series]
        (score_line,) = score_axis.plot(
            periods, means, marker="o", label=sector.name
        )
        interval_series = [
            row for row in series if row["compound_ci_lower"] is not None
        ]
        if interval_series:
            score_axis.fill_between(
                [str(row["period"]) for row in interval_series],
                [float(row["compound_ci_lower"]) for row in interval_series],
                [float(row["compound_ci_upper"]) for row in interval_series],
                color=score_line.get_color(),
                alpha=0.18,
            )
        count_axis.plot(
            periods,
            [int(row["review_count"]) for row in series],
            marker="o",
            label=sector.name,
        )
    if plotted:
        score_axis.legend()
        count_axis.legend()
    else:
        score_axis.text(
            0.5,
            0.5,
            "No reviews matched the selected sectors and date range",
            ha="center",
            va="center",
            transform=score_axis.transAxes,
        )
    score_axis.set_ylabel("Mean VADER compound")
    score_axis.set_ylim(-1, 1)
    score_axis.axhline(0, color="grey", linewidth=0.8)
    score_axis.set_title("Sector sentiment trend with confidence intervals")
    count_axis.set_ylabel("Reviews")
    count_axis.set_xlabel("Review period")
    for axis in (score_axis, count_axis):
        axis.grid(alpha=0.25)
        axis.tick_params(axis="x", rotation=45)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _select_pmi_heatmap_terms(
    rows: list[dict[str, object]],
    *,
    max_terms: int = 12,
    min_periods: int = 4,
) -> list[str]:
    observations: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        observations.setdefault(str(row["associated_term"]), []).append(row)
    persistent = {
        term: term_rows
        for term, term_rows in observations.items()
        if len({str(row["period"]) for row in term_rows}) >= min_periods
    }
    pool = persistent or observations
    return sorted(
        pool,
        key=lambda term: (
            -len({str(row["period"]) for row in pool[term]}),
            median(int(row["rank"]) for row in pool[term]),
            -median(float(row["pmi"]) for row in pool[term]),
            term,
        ),
    )[:max_terms]


def run_sentiment(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    data = config.get("data")
    trends = config.get("trends")
    if not isinstance(data, Mapping) or not isinstance(trends, Mapping):
        raise ValueError("Configuration must define [data] and [trends]")
    sentiment = trends.get("sentiment")
    if not isinstance(sentiment, Mapping):
        raise ValueError("Configuration must define [trends.sentiment]")

    configured_path = data.get("prepared_path")
    if not isinstance(configured_path, str) or not configured_path:
        raise ValueError("Configuration must define [data].prepared_path")
    input_path = Path(args.input or configured_path)
    configured_sectors = _configured_sectors(sentiment)
    sectors = _select_sectors(configured_sectors, args.sectors)
    granularity = args.time_granularity or sentiment.get("time_granularity", "year")
    confidence_level = sentiment.get("confidence_level", 0.95)
    if not isinstance(confidence_level, (int, float)):
        raise ValueError("[trends.sentiment].confidence_level must be numeric")
    configured_output_dir = sentiment.get("output_dir")
    if not isinstance(configured_output_dir, str) or not configured_output_dir.strip():
        raise ValueError("Configuration must define [trends.sentiment].output_dir")

    rows, audit = analyze_sector_sentiment(
        create_review_reader(input_path).iter_reviews(),
        sectors,
        granularity=str(granularity),
        start_date=_optional_date(args.start_date, "--start-date"),
        end_date=_optional_date(args.end_date, "--end-date"),
        confidence_level=float(confidence_level),
        progress=lambda count: print(
            f"[sentiment] reviews_read={count:,}", file=sys.stderr, flush=True
        ),
    )

    output_dir = Path(args.output_dir or configured_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    table_path = output_dir / "sentiment_by_sector_period.csv"
    with table_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=_SENTIMENT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    figure_path = output_dir / "sentiment_trends.png"
    _write_sentiment_figure(rows, sectors, figure_path)

    summary = {
        "status": "COMPLETED",
        "input": str(input_path),
        "sectors": [
            {
                "name": sector.name,
                "required_categories": sorted(sector.required_categories),
            }
            for sector in sectors
        ],
        "granularity": granularity,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "confidence_level": float(confidence_level),
        "confidence_interval_method": "normal approximation of mean using online sample variance",
        "vader_thresholds": {"positive": 0.05, "negative": -0.05},
        "period_rows": len(rows),
        "audit": audit,
        "table": str(table_path),
        "figure": str(figure_path),
    }
    summary_path = output_dir / "sentiment_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({**summary, "summary": str(summary_path)}, ensure_ascii=False, indent=2))


def run_pmi(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    data = config.get("data")
    trends = config.get("trends")
    if not isinstance(data, Mapping) or not isinstance(trends, Mapping):
        raise ValueError("Configuration must define [data] and [trends]")
    pmi_config = trends.get("pmi")
    if not isinstance(pmi_config, Mapping):
        raise ValueError("Configuration must define [trends.pmi]")

    configured_path = data.get("prepared_path")
    if not isinstance(configured_path, str) or not configured_path:
        raise ValueError("Configuration must define [data].prepared_path")
    configured_output_dir = pmi_config.get("output_dir")
    if not isinstance(configured_output_dir, str) or not configured_output_dir.strip():
        raise ValueError("Configuration must define [trends.pmi].output_dir")

    input_path = Path(args.input or configured_path)
    output_dir = Path(args.output_dir or configured_output_dir)
    target = args.term or pmi_config.get("target_term", "service")
    if not isinstance(target, str) or not target.strip():
        raise ValueError("PMI target term must be a non-blank string")
    window_size = (
        args.window_size
        if args.window_size is not None
        else pmi_config.get("window_size", 5)
    )
    top_n = args.top_n if args.top_n is not None else pmi_config.get("top_n", 20)
    min_cooccurrence = (
        args.min_cooccurrence
        if args.min_cooccurrence is not None
        else pmi_config.get("min_cooccurrence", 10)
    )
    min_cooccurrence_rate = (
        args.min_cooccurrence_rate
        if args.min_cooccurrence_rate is not None
        else pmi_config.get("min_cooccurrence_rate", 0.001)
    )
    granularity = args.time_granularity or pmi_config.get("time_granularity", "year")

    rows, analysis_summary = analyze_pmi_drift(
        create_review_reader(input_path).iter_reviews(),
        create_tokenizer_pipeline(),
        target,
        window_size=int(window_size),
        top_n=int(top_n),
        min_cooccurrence=int(min_cooccurrence),
        min_cooccurrence_rate=float(min_cooccurrence_rate),
        granularity=str(granularity),
        start_date=_optional_date(args.start_date, "--start-date"),
        end_date=_optional_date(args.end_date, "--end-date"),
        progress=lambda count: print(
            f"[pmi] reviews_read={count:,}", file=sys.stderr, flush=True
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(
        r"[^a-z0-9]+", "_", str(analysis_summary["target_term"]).lower()
    ).strip("_") or "term"
    unit = "year" if granularity == "year" else "month"
    table_path = output_dir / f"pmi_drift_{slug}_by_{unit}.csv"
    fields = [
        "period",
        "target_term",
        "associated_term",
        "rank",
        "cooccurrence",
        "target_occurrences",
        "target_pair_events",
        "context_frequency",
        "total_pair_events",
        "pmi",
    ]
    with table_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    periods = [str(item["period"]) for item in analysis_summary["periods"]]
    selected_terms = _select_pmi_heatmap_terms(rows)
    figure, axis = plt.subplots(figsize=(max(9, len(selected_terms) * 0.65), 6))
    if periods and selected_terms:
        score_map = {
            (str(row["period"]), str(row["associated_term"])): float(row["pmi"])
            for row in rows
        }
        matrix = [
            [score_map.get((period, term), float("nan")) for term in selected_terms]
            for period in periods
        ]
        image = axis.imshow(
            matrix, aspect="auto", interpolation="nearest", cmap="viridis"
        )
        axis.set_xticks(
            range(len(selected_terms)), selected_terms, rotation=45, ha="right"
        )
        axis.set_yticks(range(len(periods)), periods)
        axis.set_xlabel("Associated term")
        axis.set_ylabel("Review period")
        figure.colorbar(image, ax=axis, label="PMI (bits)")
    else:
        axis.text(
            0.5,
            0.5,
            "No associations met the minimum co-occurrence threshold",
            ha="center",
            va="center",
            transform=axis.transAxes,
        )
        axis.set_axis_off()
    axis.set_title(
        f"Persistent PMI associations around '{analysis_summary['target_term']}'"
    )
    figure.tight_layout()
    figure_path = output_dir / f"pmi_drift_{slug}_heatmap.png"
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)

    result = {
        "status": "COMPLETED",
        "input": str(input_path),
        "start_date": args.start_date,
        "end_date": args.end_date,
        **analysis_summary,
        "ranked_rows": len(rows),
        "heatmap_selection": {
            "minimum_top_n_periods": 4,
            "ordering": ["period_count_desc", "median_rank_asc", "median_pmi_desc"],
            "terms": selected_terms,
        },
        "table": str(table_path),
        "figure": str(figure_path),
    }
    summary_path = output_dir / f"pmi_drift_{slug}_summary.json"
    summary_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({**result, "summary": str(summary_path)}, ensure_ascii=False, indent=2))
