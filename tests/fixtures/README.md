# Synthetic test fixtures

Everything in this directory is invented for development and testing. It does
not contain Yelp review text.

## Layout

```text
fixtures/
├── fixture.toml
├── raw/          # Small source inputs
├── handoffs/     # Schema-valid stand-ins for an unfinished upstream module
├── oracles/      # Exact results that can be calculated by hand
└── cases/        # Required edge cases or manually assigned labels
```

## What each kind of fixture means

- `raw/` contains the smallest input dataset needed to exercise the pipeline.
- `handoffs/prepared_reviews.jsonl` is a virtual implementation of Group A's
  prepared-review output. It lets downstream groups start early, but it is not
  ground truth and does not describe every behavior of the real pipeline.
- `oracles/` contains exact expectations for fixed mathematics and invariants:
  postings, TF-IDF/BM25 ranking, and PMI. These values should be independently
  hand-checkable.
- `cases/` contains selected behavior examples. Tokenizer cases define required
  edge behavior; sentiment and comparison cases are small manually labeled
  sanity checks. They are not evidence for corpus-level conclusions.

## Fixed oracle policies

- Posting positions are zero-based.
- TF-IDF uses raw term frequency, `ln(N / df)`, and cosine similarity.
- BM25 uses the `k1` and `b` values in `fixture.toml`.
- PMI uses natural logarithms and binary document-level co-occurrence.

## Rules of use

Use fixtures to verify interfaces, formulas, invariants, and failure handling.
Do not tune empirical decisions such as stopwords, stemming, phrase rules,
frequency thresholds, or visualization scales against this tiny corpus. Those
choices must be checked on a reproducible sample of the real Yelp data.

When the real provider is ready, consumers should only switch configuration
from the handoff path to the produced-data path. They should not need to change
function signatures or duplicate upstream logic.
