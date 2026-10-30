# Local data

Expected raw files:

- `raw/yelp_academic_dataset_business.json`
- `raw/yelp_academic_dataset_review.json`

Prepare the downstream handoff with:

```powershell
yelptext prepare --config configs/full.toml
```

The full output is `processed/reviews-full.jsonl`, accompanied by
`processed/reviews-full.audit.json` and
`processed/reviews-full.audit.sqlite`. The JSONL contains the approved ten
fields; the audit files record rejected, duplicate, missing and unmatched data.

Create the schema-identical downstream development sample with:

```powershell
yelptext sample --config configs/full.toml --size 50000
```

This writes `processed/reviews-sample.jsonl`. Use `configs/sample.toml` for
downstream development and `configs/full.toml` for final runs.

All real data files in this directory are ignored by Git and must not be included in the final source-code submission. See `docs/DATA_ACCESS.md`.
