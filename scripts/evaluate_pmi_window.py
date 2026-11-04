"""Deterministic half-sample stability evaluation for PMI window selection."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from yelptext.implementation.trend_application.pmi import analyze_pmi_drift
from yelptext.interface.data_corpus_analysis import (
    create_review_reader,
    create_tokenizer_pipeline,
)


def _half_reviews(
    reviews: Iterable[Mapping[str, Any]], half: int
) -> Iterable[Mapping[str, Any]]:
    for review in reviews:
        doc_id = review.get("doc_id")
        if not isinstance(doc_id, str):
            raise ValueError("prepared review must contain a string doc_id")
        bucket = hashlib.blake2b(doc_id.encode("utf-8"), digest_size=1).digest()[0] % 2
        if bucket == half:
            yield review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--half", required=True, type=int, choices=(0, 1))
    parser.add_argument("--window-size", required=True, type=int)
    parser.add_argument("--target", default="service")
    args = parser.parse_args()

    rows, summary = analyze_pmi_drift(
        _half_reviews(create_review_reader(args.input).iter_reviews(), args.half),
        create_tokenizer_pipeline(),
        args.target,
        window_size=args.window_size,
        top_n=20,
        min_cooccurrence=5,
        min_cooccurrence_rate=0.001,
        progress=lambda count: print(
            f"[window={args.window_size} half={args.half}] reviews={count:,}",
            file=sys.stderr,
            flush=True,
        ),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"rows": rows, "summary": summary}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
