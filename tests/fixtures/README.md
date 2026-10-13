# Fixture layout

Only raw Yelp-shaped records exist before schema approval.

```text
fixtures/
├── fixture.toml
├── data/raw/
│   ├── yelp_academic_dataset_business.json
│   └── yelp_academic_dataset_review.json
├── data_corpus_analysis/README.md
├── search_engine/README.md
└── trend_application/README.md
```

`data/raw/` mirrors the real `data/raw/` file names and source record shapes. The invented records cover multiple dates/categories, open and closed businesses, an orphan review, Unicode, emoji, contractions, hyphens, numbers, currency, repeated terms, and comparative language.

After a schema is approved, add derived input only to the semantic directory of the feature that consumes it. Its README must state the approved schema, derivation, edge cases, and whether each file is input, a labeled case, or an exact independently checked oracle. Do not invent a derived format before its interface is agreed.
