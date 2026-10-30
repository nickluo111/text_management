# Tokenizer audit and policy decisions

This document records the evidence used to review the Group A submission before
its promotion into the shared implementation. Raw Yelp samples and per-review
audit cases remain under ignored `data/interim/tokenizer_audit/`.

## Assignment boundary

The assignment requires a custom regex tokenizer for noisy Yelp reviews,
including emoji preservation, contractions such as `don't`, and run-on forms
such as `the-best-food`. It also requires a qualitative and vocabulary-size
comparison with standard tokenizers. It does not require POS tagging.

## Audit data

- Full source scan: 6,990,280 valid reviews and zero malformed lines.
- General sample: 50,000 reviews selected with seed 42 using bottom-k keyed
  priorities ordered by `(priority, doc_id)`. `source_line` is provenance only
  and is not a sampling tie-breaker.
- Edge sample: up to 200 reviews from each observed category (emoji, emoticon,
  formatted number, hashtag, long surface form, non-ASCII, punctuation-heavy,
  and URL/email), producing 1,599 unique reviews.
- The general sample estimates distributions. The deliberately enriched edge
  sample is only for finding failure cases.

The previously generated 50,000-review sample was not regenerated after the
tie-breaker correction. Its selected priorities contain zero collisions, so
changing the unused tie-breaker cannot change its membership or order.

The reusable production sampler now lives behind
`data_corpus_analysis.sample_reviews` and `yelptext sample`. It preserves the
complete input record, uses a simple seeded FNV-1a priority, and does not compute
or verify SHA-256 file hashes. The edge-category sampler remains an audit-only
tool because its deliberately biased output is unsuitable for downstream
distribution estimates.

## Final shared rules

- Normalize text to NFC, lowercase it, normalize curly apostrophes, and map
  fullwidth `？！＃` to ASCII.
- Preserve contractions such as `don't` as one token.
- Split hyphenated/run-on forms: `the-best-food` becomes `the`, `best`, `food`.
- Preserve complete emoji grapheme sequences, including skin tone, flags,
  keycaps, and common ZWJ sequences.
- Preserve URL, email, emoticon, hashtag, grouped number, fraction, money,
  percentage, numeric-plus, and temperature forms.
- Normalize `$ 12.50` to `$12.50` and `20 %` to `20%`.
- Normalize suffix money such as `250$` to `$250`; preserve `50¢`, `10+`,
  `20+%`, and `29°F`.
- Normalize backtick/acute apostrophe variants and accept repeated apostrophes
  such as `y'all's`. A trailing apostrophe is consumed as a boundary but removed
  from the normalized term.
- Preserve common complete ASCII emoticons such as `^_^`, `^_~`, `o_o`, and
  `¯\\_(ツ)_/¯`.
- Keep expressive `!` and `?` as `punctuation` tokens. Ordinary sentence
  punctuation is a delimiter. Hashtags such as `#deal` remain one token.
- Treat isolated symbols such as `+`, `=`, and `~` as delimiters. Orphaned ZWJ
  and zero-width spaces are ignored rather than made vocabulary terms.

Stable tags are:

```text
word, stop_word, conjunction,
url, email, emoticon, emoji,
number, money, percentage, temperature,
hashtag, punctuation
```

Money and percentage tokens also carry `number`. Tags are non-exclusive.

## POS policy

POS is disabled in the canonical pipeline and vocabulary. It is not needed for
the assignment's tokenizer, search ranking, Zipf/Heaps analysis, or VADER
sentiment path. An experimental `PosTagger` remains separate and opt-in; using
`pos:*` in `skip_types` without enabling it is a configuration error.

## Punctuation policy by consumer

- Tokenizer comparison retains the tokenizer's native expressive punctuation.
- Zipf/Heaps lexical analysis uses `skip_types=["punctuation"]` so `!` does not
  become a top-ranked lexical term.
- Search indexing and query processing use the same punctuation filter.
- VADER receives original review text, preserving its own capitalization and
  punctuation cues.

On the 50,000-review sample, `!` occurred 66,380 times in 24,138 reviews and
ranked eighth before filtering. This is why the filter belongs in the consumer
pipeline rather than being left implicit.

## Low-frequency and UNK policy

The canonical vocabulary uses `min_cf=1` and `min_df=1`. It reserves `<UNK>` as
term ID 0 but does not aggregate rare terms into it.

The 50,000-review audited vocabulary contains 55,928 entries including
`<UNK>`. Of the 55,927 observed types, 23,731 (42.4%) are hapax types. The high
sample-level rare-type share is evidence for reporting and downstream tuning,
not sufficient justification for destructive global pruning.

- Search keeps rare terms and drops OOV query terms rather than giving `<UNK>`
  a posting list.
- Fixed-dimensional classification may tune `min_df` on its validation data.
- Zipf/Heaps retains observed types because pruning would change the measured
  vocabulary distribution.

## Full-corpus vocabulary build

The disk-backed builder completed an explicit offline pass over the complete
review file. The resulting ignored artifact is
`data/processed/vocabulary-full.sqlite`.

| Measure | Result |
|---|---:|
| Valid reviews | 6,990,280 |
| Malformed input lines | 0 |
| Token occurrences | 745,364,150 |
| Observed terms | 685,123 |
| Entries including reserved `<UNK>` | 685,124 |
| SQLite artifact size | 46,895,104 bytes |
| Build time | 1,576.5 s |

The database passed SQLite's integrity check. Term IDs are contiguous from 0
through 685,123, `<UNK>` is ID 0 with CF=DF=0, the sum of term CF equals the
reported token count, and no term has CF below DF.

Rare forms are common: 365,917 observed terms have CF=1, while 528,325 have
CF<=5. These are corpus statistics rather than a global pruning instruction.
The longest entries are mostly complete URLs or one-off elongated/noisy user
forms such as repeated letters. Only 64 word-tagged terms have length above 80,
with 65 occurrences in total. This does not justify changing the tokenizer's
general word rule; task consumers may instead tune `min_df`, length features,
or OOV handling using their own validation objective.

Vocabulary inspection and unmatched-character inspection answer different
questions. The vocabulary reveals matched but unusual terms. It cannot reveal
characters skipped by the tokenizer, because those characters never become
terms; the span audit below remains the coverage check.

## Standard-tokenizer comparison

All methods processed the same 50,000 reviews in the same order with no
stopword, stemming, or punctuation filter:

| Tokenizer | Tokens | Vocabulary | Hapax share | Tokenization time |
|---|---:|---:|---:|---:|
| NLTK Whitespace, normalized | 5,241,869 | 148,318 | 59.1% | 2.13 s |
| NLTK WordPunct, normalized | 6,131,183 | 53,710 | 41.5% | 2.56 s |
| Custom, normalized | 5,334,708 | 55,927 | 42.4% | 10.01 s |

The custom tokenizer matched all ten constructed policy cases. Its additional
runtime pays for dataset-specific URL, contraction, grouped-number, money,
hashtag, emoticon, and emoji behavior. The optimized fast path reduced the
50,000-review custom runtime from about 24.5 seconds to about 9.9-10.0 seconds
without changing token output.

## Unmatched-character outcome

After the targeted rule updates, the general sample contains zero unmatched
characters with `policy_status=needs_rule`: 659,643 are approved delimiters and
121 are ignored ZWJ/zero-width format noise. The enriched edge sample also has
zero `needs_rule` characters: 43,900 approved delimiters and 19 ignored format
characters. The audit CSV retains every unmatched character and its explicit
status; zero `needs_rule` does not mean zero delimiters.

## Remaining limitations

- The rules are dataset-specific English-oriented heuristics, not a linguistic
  tokenizer for every language.
- NLTK's stopword list tags negations such as `not`; sentiment consumers must
  not blindly skip `stop_word`.
- Symbols used as prose separators or grades (`+`, `=`, `~`) are not retained.
- POS quality has not been evaluated and is intentionally outside the canonical
  path.
