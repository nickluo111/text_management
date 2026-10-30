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

The public entry points live in `yelptext.interface.data_corpus_analysis`.
Downstream groups obtain the canonical tokenizer through `create_tokenizer()`
and reusable samples through `sample_reviews()`; they do not import private
implementation modules.
