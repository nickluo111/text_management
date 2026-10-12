# Synthetic test fixtures

Everything in this directory is invented for this project. No record or text was
copied from Yelp. These small files are safe to commit and are intended to let
the three responsibility groups develop in parallel before the full pipeline is
available.

## Layout

```text
fixtures/
├── fixture.toml
├── raw/
│   ├── businesses.jsonl
│   └── reviews.jsonl
└── expected/
    ├── prepared_reviews.jsonl
    ├── tokenization.json
    ├── postings.json
    ├── ranking_cases.json
    ├── sentiment_cases.json
    ├── pmi_cases.json
    └── comparison_cases.json
```

The raw files deliberately resemble only the subset of Yelp fields used by the
project. They contain five businesses, twenty valid reviews, and one review
(`r999`) whose business does not exist. Preparation should report and exclude
that orphan. Business `review_count` values describe the valid synthetic reviews.

`prepared_reviews.jsonl` is the expected inner join. Category normalization for
this fixture means splitting the raw comma-separated value, trimming whitespace,
and preserving category spelling and case.

## Fixed policies for expected outputs

- The tokenizer lowercases text, preserves contractions and emoji, splits
  hyphenated words, drops punctuation, and retains Unicode words and numbers.
- `postings.json` indexes reviews `r001` through `r004`; positions are zero-based.
- TF-IDF uses raw term frequency, `ln(N / df)`, and cosine similarity.
- BM25 uses `k1 = 1.5`, `b = 0.75`, and
  `ln(1 + (N - df + 0.5) / (df + 0.5))`.
- PMI uses natural logarithms and binary term presence within one document:
  `ln(cooccurrence * N / (df(target) * df(term)))`.
- Sentiment fixtures assert only clear positive/negative/neutral labels because
  exact VADER floating-point scores are library-data dependent.
- Comparison labels distinguish cross-business comparisons from changes over
  time at the same business.

If the team intentionally changes one of these policies, update the relevant
fixture, its tests, and `docs/TEAM_WORKFLOW.md` in the same pull request. Do not
quietly change expected values just to make a failing implementation pass.
