# Shared tokenizer implementation

This directory contains the reviewed Group A implementation. Downstream groups
should obtain the shared tokenizer from `yelptext.interface.data_corpus_analysis`
rather than importing this implementation package directly.

## Separation of responsibilities

- `RegexTokenizer` normalizes and splits text without reading a vocabulary.
- `TokenClassifier` adds only stable structural and NLTK stopword tags.
- `PosTagger` is a separate experimental component. The canonical pipeline does
  not instantiate it, and POS resources are never downloaded at import time.
- `TokenFilter` applies a validated `skip_types` policy. Unknown tags, or
  `pos:*` tags without an enabled `PosTagger`, are configuration errors.
- `VocabularyBuilder` calculates term IDs, CF, DF, static tags, and optional POS
  counts. `<UNK>` is always ID 0 and has zero corpus statistics.
- `VocabularyLookup` maps occurrences under one explicit OOV policy: `unk`,
  `drop`, or `error`.
- `TokenizerPipeline` is the downstream facade and verifies that its tokenizer
  and filtering policy are compatible with the vocabulary artifact.

The main vocabulary does not merge rare words into `<UNK>`. `min_cf` and
`min_df` are explicit task-specific pruning options; metadata records how many
types/tokens were pruned. Search should normally use `drop` for query OOV terms,
while a fixed-dimensional classifier may use `unk`.

Current canonical policy keeps expressive `!` and `?` tokens with a
`punctuation` tag, preserves hashtags as one token, and treats ordinary sentence
punctuation as delimiters. Zipf/Heaps lexical analysis and search indexing should
set `skip_types = ["punctuation"]`; VADER should receive original review text.
The canonical vocabulary uses `min_cf = min_df = 1`.

## Build a vocabulary

Vocabulary construction is an explicit, offline step. It is not performed when
the tokenizer is imported or when a downstream pipeline tokenizes one review.

For the complete Yelp review corpus, use the disk-backed SQLite builder:

```powershell
yelptext vocab build --config configs/default.toml
```

The lower-level module accepts explicit input/output paths for debugging, but
normal project runs should use the public CLI above.

The SQLite artifact can be opened through `SqliteVocabulary` and used by the
same `VocabularyLookup`/`TokenizerPipeline` code as the in-memory vocabulary.
An interrupted build remains marked `BUILDING` and is rejected by the reader.

For fixtures or smaller development samples, the JSON builder is convenient:

```powershell
python -m yelptext.implementation.data_corpus_analysis.tokenizer.build_vocab `
  --input-file data/processed/reviews-full.jsonl `
  --output-file data/processed/vocabulary.json
```

Use repeated `--skip-type` options only when intentionally building a filtered
task vocabulary. The canonical shared vocabulary should normally retain every
type and let downstream pipelines filter occurrences.

Do not use the vocabulary as an unmatched-character audit. A character that the
regex tokenizer does not match cannot appear in the vocabulary. Use the span
audit described below for coverage; use the vocabulary to inspect observed
terms, CF/DF distributions, long terms, and task-specific pruning choices.

Stable skip types are `word`, `stop_word`, `conjunction`, `url`, `email`,
`emoticon`, `emoji`, `number`, `money`, `percentage`, `temperature`, `hashtag`,
and `punctuation`. Money, percentage, and temperature occurrences also carry
the `number` tag.

NLTK stopwords are required by the classifier. Experimental POS tagging is
optional and requires the separately installed `averaged_perceptron_tagger` resource.
Neither resource is downloaded by library imports.

## Audit and comparison

The completed review evidence is recorded in `docs/TOKENIZER_AUDIT.md`. Audit
notebooks were removed so that `notebooks/` remains dedicated to report
visualization. The old Group A candidate scripts were removed after promotion;
production consumers use the formal interface and CLI instead.
