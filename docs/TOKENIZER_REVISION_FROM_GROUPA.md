# Tokenizer revision from the Group A submission

This document describes how the reviewed tokenizer differs
from the version originally submitted under `src/yelptext/groupa/tokenizer/`.
After review, the implementation was promoted to
`src/yelptext/implementation/data_corpus_analysis/tokenizer/` and is exposed
through `yelptext.interface.data_corpus_analysis.create_tokenizer()`.

## 1. Summary

The Group A submission provided a useful starting point:

- a regex tokenizer written from scratch;
- lowercase normalization;
- contractions such as `don't` kept as one token;
- hyphenated forms split into words;
- basic URL, decimal, fraction, emoticon, emoji, and punctuation handling;
- optional filtering for stopwords, conjunctions, and emoji;
- scripts for vocabulary construction and tokenizer comparison.

The reviewed version preserves that intent but separates tokenization,
classification, filtering, vocabulary construction, and vocabulary lookup. It
also fixes Unicode and noisy-text failures found on deterministic real-data
samples.

The final candidate was evaluated on the same deterministic 50,000-review
sample and an enriched 1,599-review edge-case sample. No raw Yelp text or audit
sample is committed to Git.

## 2. Architecture changes

### Group A submission

The original `our_tokenizer(text, skiptype=None)` function performed several
responsibilities together:

```text
regex recognition
-> lowercase
-> type checks
-> skiptype filtering
-> list[str]
```

Vocabulary construction and access were separate scripts, but vocabulary
access used process-wide mutable state. The tokenizer itself had no stable
fingerprint.

### Reviewed candidate

The candidate uses explicit components:

```text
RegexTokenizer
-> TokenClassifier
-> optional PosTagger
-> TokenFilter
-> VocabularyLookup
```

`TokenizerPipeline` composes these components for downstream users.

| Component | Responsibility |
|---|---|
| `RegexTokenizer` | Normalize and split text without reading a vocabulary |
| `TokenClassifier` | Add stable structural and lexical tags |
| `PosTagger` | Experimental opt-in NLTK POS tagging; disabled by default |
| `TokenFilter` | Apply validated `skip_types` |
| `VocabularyBuilder` | Calculate term IDs, CF, DF, tags, and metadata |
| `VocabularyLookup` | Map tokens under an explicit OOV policy |
| `TokenizerPipeline` | Provide one downstream-facing facade |

The public tokenizer boundary remains simple:

```python
tokenize(text: str) -> list[str]
fingerprint() -> str
```

The original `our_tokenizer()` name remains as a compatibility facade for the
existing Group A analysis scripts.

## 3. Tokenization-rule changes

### 3.1 Unicode normalization

The original implementation lowercased text but did not normalize Unicode
inside the shared tokenizer. Some comparison code normalized input externally,
which meant direct downstream calls behaved differently.

The candidate performs normalization internally:

- NFC Unicode normalization;
- lowercase normalization;
- curly apostrophes `’‘` converted to `'`;
- backtick and acute apostrophe variants converted to `'`;
- fullwidth `？！＃` converted to ASCII `?!#`.

Examples:

```text
can’t       -> can't
cafe + ◌́   -> café
didn`t      -> didn't
didn´t      -> didn't
Really？！   -> really, ?, !
```

### 3.2 Words and apostrophes

The original word rule supported at most one internal apostrophe segment.

The candidate supports repeated segments:

```text
y'all's -> one token
```

A trailing apostrophe is consumed as a boundary but removed from the normalized
term:

```text
customers' -> customers
seein'     -> seein
```

Leading and closing quotation marks remain delimiters.

### 3.3 Hyphenated and run-on forms

The original policy of splitting hyphenated forms was retained:

```text
state-of-the-art -> state, of, the, art
the-best-food    -> the, best, food
```

The hyphen is an intentional delimiter and is not added to the vocabulary.

### 3.4 Emoji

The original implementation matched broad Unicode ranges and explicitly split
composed emoji into separate code points. That caused several failures:

- skin-tone modifiers detached from their emoji;
- ZWJ family emoji split;
- regional flags split;
- keycap sequences split;
- some non-emoji supplementary characters could be labelled as emoji.

The candidate recognizes complete common grapheme sequences:

```text
👍🏽
👨‍👩‍👧‍👦
🇺🇸
1️⃣
```

The emoji ranges were narrowed so ordinary non-English text is not classified
as emoji.

### 3.5 Emoticons

The original basic forms remain supported:

```text
:)  :(  :D  XD  ;-)  T_T  ._.
```

The candidate adds common complete forms found during unmatched-character
review:

```text
^_^  ^_~  o_o  ¯\_(ツ)_/¯
```

Their internal punctuation is covered by one `emoticon` token instead of being
reported as separate unmatched symbols.

### 3.6 URLs and email addresses

The original URL rule absorbed terminal sentence punctuation because it used a
greedy non-whitespace suffix. The candidate keeps the URL as one token and
separates retained expressive punctuation:

```text
https://example.com/x!!!
-> https://example.com/x, !, !, !
```

Trailing comma, full stop, semicolon, and colon are delimiters. Email addresses
are now recognized as complete `email` tokens instead of being split into word
components.

### 3.7 Hashtags

The original implementation recognized a standalone `#`, then split the word:

```text
#deal -> #, deal
```

The candidate recognizes the complete hashtag first:

```text
#deal -> one hashtag token
```

A standalone `#` is still recognized as punctuation for compatibility with the
reviewed policy suite.

### 3.8 Numbers, money, percentages, quantities, and temperature

The original decimal rule did not preserve grouped numbers:

```text
1,234.50 -> 1, 234.50
```

The candidate supports:

```text
12.50       number
1,234.50    number
3/4         number
$12.50      money + number
$ 12.50     normalized to $12.50
250$        normalized to $250
50¢         money + number
10+         number
20%         percentage + number
20+%        percentage + number
29°F        temperature + number
```

The number recognition branches were later consolidated into one regex branch.
This retained the same output while avoiding repeated attempts of the full
number regex at each numeric position.

### 3.9 Punctuation and symbols

The candidate intentionally keeps expressive `!` and `?` tokens with the
`punctuation` tag. Ordinary sentence punctuation remains a delimiter:

```text
, . ; : ( ) [ ] " ' - /
```

Other isolated symbols remain delimiters unless they are part of an approved
structure:

```text
+ = ~ | & *
```

This is deliberate. Search and Zipf/Heaps consumers use
`skip_types=["punctuation"]`; VADER receives original review text rather than
the filtered tokenizer output.

## 4. Token classification and filtering

### Original behavior

The original function had three optional skip categories:

```text
stop_word, conjunction, emoji
```

Classification was performed inside `our_tokenizer()`, and each token had one
effective type chosen by an `if/elif` chain.

### Reviewed behavior

Tags are non-exclusive. For example:

```text
and   -> word, stop_word, conjunction
$12   -> money, number
20%   -> percentage, number
29°F  -> temperature, number
```

Stable filterable tags are:

```text
word, stop_word, conjunction,
url, email, emoticon, emoji,
number, money, percentage, temperature,
hashtag, punctuation
```

`skip_types` is validated. Unknown values are configuration errors instead of
being silently ignored.

POS tagging was removed from the stable classifier. It remains a separate,
experimental `PosTagger`. Configuring `pos:*` filters without explicitly
enabling it is an error. The canonical pipeline and vocabulary have POS turned
off.

## 5. Vocabulary changes

### Group A submission

The original builder emitted up to three overlapping JSON files:

```text
vocab_pure.json
vocab_with_type.json
vocab_with_freq.json
```

It calculated collection frequency but not document frequency. It also wrote a
large flat token text file, lacked tokenizer/configuration metadata, and caught
all exceptions as bad input lines. Filtering affected the final vocabulary but
not the flat token stream.

The original vocabulary interface used module-level mutable state and returned
sentinel values such as `-1` for missing IDs.

### Reviewed candidate

The candidate produces one versioned vocabulary artifact. Each entry contains:

```text
term
term_id
CF
DF
static tags
optional POS counts
```

The artifact also records tokenizer identity, document count, post-filter token
count, vocabulary size, filtering settings, and pruning settings.

`<UNK>` is always reserved as term ID 0. The canonical vocabulary does not merge
rare terms into `<UNK>` and uses:

```text
min_cf = 1
min_df = 1
```

Low-frequency pruning is explicitly downstream-specific:

- search retains rare terms and drops OOV query terms rather than building an
  `<UNK>` posting list;
- fixed-dimensional classifiers may tune `min_df` using validation data;
- Zipf/Heaps retains observed types because pruning would change the measured
  distribution.

`VocabularyLookup` supports explicit `unk`, `drop`, and `error` OOV policies.
The vocabulary and tokenizer each expose a stable fingerprint so an index/query
pipeline can reject incompatible preprocessing versions.

## 6. Import and dependency behavior

The original package used local absolute imports such as:

```python
from stop_words import STOP_WORDS
```

This failed when imported as `yelptext.groupa.tokenizer`. Imports are now
package-relative, while a small compatibility fallback keeps the existing
file-based Group A analysis scripts working.

The original `stop_words.py` could run `nltk.download()` during module import.
The candidate never downloads resources at import time. Missing NLTK data now
produces an explicit setup error.

## 7. Unmatched-character audit

The candidate adds `tokenize_with_spans()`. It marks token-covered offsets in
normalized text and reports every non-whitespace character not covered by a
token.

Unmatched characters now use explicit policy states:

```text
intentional_delimiter
ignored_format_noise
needs_rule
```

Covered characters appear in the token table and therefore do not appear in the
unmatched CSV.

After the rule changes:

| Audit set | Intentional delimiter | Format noise | Needs rule |
|---|---:|---:|---:|
| General 50,000 reviews | 659,643 | 121 | 0 |
| Enriched 1,599 edge reviews | 43,900 | 19 | 0 |

The ignored format characters are isolated ZWJ and zero-width spaces. A zero
`needs_rule` count does not mean that punctuation disappeared; it means every
remaining unmatched character has an approved policy.

The sample selector was also corrected to order equal priorities by `doc_id`
rather than `source_line`. Source lines remain provenance only. The existing
50,000-review sample was not regenerated because it contains zero selected
priority collisions.

## 8. Performance changes

The Group A submission rebuilt the combined pattern string and called
`re.findall()` inside every `our_tokenizer()` invocation, relying on Python's
implicit regex cache. It also performed separate type checks within the same
loop.

The reviewed implementation improves the hot path by:

- compiling regexes once at module load;
- keeping normal `tokenize()` independent of audit `TokenSpan` dataclasses;
- using direct prefix/suffix checks instead of rerunning money/percentage regexes
  for every recognized token;
- consolidating repeated numeric alternatives into one recognition branch;
- combining common character translations;
- loading stopword/POS resources outside the core regex hot path;
- keeping vocabulary lookup out of token recognition.

During review, an early span-based candidate took about 24.5 seconds to process
the fixed 50,000-review sample. The final candidate processes the same sample in
about 9.87 seconds in the native view and 10.01 seconds in the controlled
normalized view.

The final controlled comparison is:

| Tokenizer | Tokens | Vocabulary | Hapax share | Tokenization time |
|---|---:|---:|---:|---:|
| NLTK Whitespace | 5,241,869 | 148,318 | 59.1% | 2.10 s |
| NLTK WordPunct | 6,131,183 | 53,710 | 41.5% | 2.49 s |
| Reviewed custom | 5,334,708 | 55,927 | 42.4% | 10.01 s |

The custom tokenizer is slower than the general NLTK baselines, but the cost is
associated with reviewed Yelp-specific rules for URLs, contractions, grouped
numbers, currency, percentages, hashtags, emoticons, and composed emoji.

No measured runtime is reported for the original Group A file itself because it
was replaced during review before the fixed 50,000-review benchmark was
established. The numeric performance comparison above is therefore between the
instrumented intermediate candidate and the final candidate, not an invented
measurement of the original submission.

## 9. Validation results

The final candidate has:

- 5,334,708 tokens on the fixed 50,000-review sample;
- 55,927 observed types;
- 55,928 vocabulary entries including `<UNK>`;
- 23,731 hapax types;
- zero malformed sample records;
- zero `needs_rule` unmatched characters in both audit sets;
- all ten constructed tokenizer-policy cases passing;
- the complete project test suite passing with 71 tests after sampler and
  formal-interface
  integration.

The constructed cases cover contractions, hyphens, composed emoji,
punctuation, expanded emoticons, numeric/money/temperature forms, URLs, Unicode
normalization, case normalization, and negation preservation.

## 10. Files

Formal implementation:

```text
src/yelptext/implementation/data_corpus_analysis/tokenizer/tokenizer.py
src/yelptext/implementation/data_corpus_analysis/tokenizer/classification.py
src/yelptext/implementation/data_corpus_analysis/tokenizer/pos.py
src/yelptext/implementation/data_corpus_analysis/tokenizer/pipeline.py
src/yelptext/implementation/data_corpus_analysis/tokenizer/vocabulary.py
src/yelptext/implementation/data_corpus_analysis/tokenizer/sqlite_vocabulary.py
```

Audit and analysis after promotion:

```text
docs/TOKENIZER_AUDIT.md
notebooks/01_zipf.ipynb
notebooks/02_heaps.ipynb
```

The temporary `src/yelptext/groupa/` candidate area was removed after the
reviewed implementation moved into the formal package.

Tests:

```text
tests/test_tokenizer.py
tests/test_tokenizer_audit_sampling.py
```

The latest ignored real-data comparison output is under:

```text
data/interim/tokenizer_audit/comparison-final-v6/
```

Only the code, tests, notebook driver, and summarized documentation should be
committed; raw Yelp samples and generated per-review outputs remain ignored.
