# Data and corpus analysis implementation

- `preparation.py` streams raw Yelp review/business JSONL, joins the approved
  metadata, and writes canonical ten-field JSONL plus JSON/SQLite audit files.
- `reviewer.py` validates and streams only that canonical handoff. Downstream
  groups therefore never parse or join raw Yelp records.
- `sampling.py` provides a streaming, order-independent bottom-k sampler that
  preserves each complete input record. It uses seeded non-cryptographic
  FNV-1a priorities and no file-content hash verification.
- `tokenizer/` contains the reviewed regex tokenizer, structural classifier,
  optional filters/POS stage, and JSON/SQLite vocabulary facilities. Full
  vocabulary construction is an explicit command, not an import-time action.
- `zipf.py` reads the completed, unpruned SQLite vocabulary and produces the
  rank-frequency table, sensitivity fits, provenance metadata, and plots.
- `heaps.py` streams prepared reviews through the shared reader/tokenizer after
  a deterministic seeded random ordering. It validates its final token/type
  counts against the vocabulary and records fit, sensitivity, and prediction
  artifacts.
- `tokenizer_comparison.py` runs the controlled custom/Whitespace/WordPunct
  comparison and writes all tables, metadata, and figures consumed by notebook
  03.

The public entry points live in `yelptext.interface.data_corpus_analysis`.
Downstream groups obtain the canonical tokenizer through `create_tokenizer()`
and reusable samples through `sample_reviews()`; they do not import private
implementation modules.

Run the analyses through the unified CLI; the notebooks only display the
resulting artifacts:

```text
python -m yelptext analyze zipf --config configs/full.toml
python -m yelptext analyze heaps --config configs/full.toml
```
