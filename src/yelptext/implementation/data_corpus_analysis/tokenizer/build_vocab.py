"""Build one versioned vocabulary artifact from canonical review JSONL.

Run as:
    python -m yelptext.implementation.data_corpus_analysis.tokenizer.build_vocab --input-file reviews.jsonl \
        --output-file vocabulary.json
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path

from .classification import TokenClassifier, TokenFilter
from .pos import PosTagger
from .tokenizer import RegexTokenizer
from .vocabulary import VocabularyBuilder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a typed vocabulary from canonical Yelp review JSONL."
    )
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    parser.add_argument(
        "--skip-type",
        action="append",
        default=[],
        help="Token tag to exclude; repeat the option for multiple tags.",
    )
    parser.add_argument("--min-cf", type=int, default=1)
    parser.add_argument("--min-df", type=int, default=1)
    parser.add_argument(
        "--enable-pos",
        action="store_true",
        help="Experimental: add NLTK POS counts; disabled in the canonical pipeline.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input_file.is_file():
        raise FileNotFoundError(args.input_file)

    stats = {"nonempty_lines": 0, "bad_lines": 0}

    def document_texts() -> Iterator[str]:
        with args.input_file.open("rb") as source:
            for line_number, raw_line in enumerate(source, start=1):
                if not raw_line.strip():
                    continue
                stats["nonempty_lines"] += 1
                try:
                    record = json.loads(raw_line)
                    text = record["text"]
                    if not isinstance(text, str):
                        raise TypeError("field 'text' must be a string")
                except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as exc:
                    stats["bad_lines"] += 1
                    print(f"Skipping line {line_number}: {exc}")
                    continue
                yield text

    tokenizer = RegexTokenizer()
    classifier = TokenClassifier()
    pos_tagger = PosTagger() if args.enable_pos else None
    token_filter = TokenFilter(args.skip_type, allow_pos=args.enable_pos)
    vocabulary = VocabularyBuilder(
        tokenizer,
        classifier,
        token_filter,
        pos_tagger,
        min_cf=args.min_cf,
        min_df=args.min_df,
    ).build(document_texts())
    vocabulary.metadata.update(
        {
            "input_file": str(args.input_file),
            "input_nonempty_lines": stats["nonempty_lines"],
            "bad_lines": stats["bad_lines"],
        }
    )
    vocabulary.save(args.output_file)
    print(
        f"Saved {len(vocabulary.entries)} entries (including <UNK>) "
        f"to {args.output_file}; skipped {stats['bad_lines']} malformed records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
