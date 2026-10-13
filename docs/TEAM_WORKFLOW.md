# Six-person team workflow

## Dependency logic

The project uses three pairs, but the work does not begin as three independent branches. Everyone first agrees on the cross-feature boundaries; after that gate, the pairs can work in parallel against stable fake upstreams.

![Team dependency and ownership flow](assets/team-dependency.svg)

### Facility dependency register

| Work unit | Required upstream facilities | Work performed | Facilities/artifacts provided |
| --- | --- | --- | --- |
| data preparation | raw Yelp business and review JSON | stream, validate, join business metadata, apply orphan/date/category policy | `PreparedReviewReader` and optional prepared-review artifact |
| tokenizer | prepared review text plus approved token policy | normalize/tokenize and emit a compatibility fingerprint | shared `Tokenizer` |
| Zipf/Heaps/tokenizer comparison | `PreparedReviewReader`, shared tokenizer, baseline tokenizers | corpus counting, fitting and comparison | metrics, tables and figures; no new cross-group runtime dependency |
| index build/storage | `PreparedReviewReader` + shared `Tokenizer` | build postings/statistics, persist index and tokenizer metadata | index artifact and real `SearchIndex`/reader facade |
| query/ranking/evaluation | index facade + the same shared `Tokenizer` | tokenize queries, score TF-IDF/BM25, rank and evaluate | ranked results, query evaluation and report artifacts |
| sector sentiment | `PreparedReviewReader`: original `text`, `date`, `categories` | run VADER on the full original review text, then aggregate by period/sector | sentiment time series with review counts |
| PMI drift | `PreparedReviewReader` + shared `Tokenizer` | form the approved context, count co-occurrence and compute/filter PMI | ranked term associations by period |
| comparison application | `PreparedReviewReader`: original `text` and `review_id` | sentence splitting plus comparison detection/evaluation inside Group C | matched sentences, cues/labels and evaluation metrics |

The shared tokenizer is therefore **not** a blanket dependency of trend/application work. Sentiment should preserve the complete review string because VADER uses punctuation, capitalization, emoji and negation cues. PMI requires the shared tokenizer so term identity is stable across periods. The comparison application uses original text and owns its sentence segmentation; it should depend on the shared tokenizer only if the final approved method genuinely needs token-level cues.

The required order is:

1. agree on assignment scope, raw Yelp shapes, and which outputs cross feature boundaries;
2. downstream consumers state what they need, and the upstream producer freezes a jointly approved schema;
3. create the fake interface and minimum baseline test kit from that schema;
4. let all three pairs implement and test their own complete feature in parallel;
5. replace fake upstreams with real upstreams by switching runtime mode only;
6. tune empirical choices on real samples, then run final notebooks and report experiments.

The serial dependency stops at the approved schema and usable fake. Group B does not wait for Group A's real tokenizer or prepared dataset, and Group C does not wait for Group A's full-data experiments.

## Responsibilities

| Pair | Assignment scope | Upstream dependency | Outputs consumed elsewhere |
| --- | --- | --- | --- |
| Data and corpus analysis | preparation, tokenizer, Zipf, Heaps, tokenizer comparison (§3.1-§3.2) | raw Yelp business/review records | prepared reviews and tokenizer |
| Search engine | index, persistence, TF-IDF, BM25, query and retrieval analysis (§3.3) | prepared reviews and tokenizer | read-only search/index interface only if another feature needs it |
| Trends and application | sentiment, PMI drift, independent NLP/IR application (§3.4-§3.5) | prepared reviews for all tasks; shared tokenizer for PMI only | sentiment series, PMI rankings, comparison matches and evaluation artifacts |

An internal helper is not a shared schema. Create a cross-feature protocol only when another pair actually consumes it.

## Who defines and who implements a schema

Use a **consumer-driven, producer-owned** rule:

- downstream consumers write the required use cases, fields, example calls, edge cases, and serialized examples;
- the upstream producer checks feasibility, removes accidental implementation details, and becomes steward of the final protocol file;
- producer and every affected consumer approve the schema before it is frozen;
- the upstream producer implements the real interface and owns its compatibility;
- consumers may request changes but must not create a second version of the same schema.

This is preferable to either side deciding alone. A producer-only design can omit data the consumer needs; a consumer-only design can expose unstable or expensive internals. The target is **consumer-complete and minimal**, not speculative redundancy. A derived field belongs in the shared schema only when its meaning is common, stable, and recomputing it in several consumers would be inconsistent or needlessly expensive.

### Boundary ownership

| Boundary | Requirements proposed by | Protocol steward | Real implementation |
| --- | --- | --- | --- |
| prepared reviews | search pair + trend/application pair, with corpus needs from the data pair | data/corpus pair | data/corpus pair |
| tokenizer | every pair that tokenizes text | data/corpus pair | data/corpus pair |
| read-only index/search | trend/application pair only if it consumes this boundary; otherwise search-internal | search pair | search pair |
| trend/application artifacts | notebook/report consumers | trend/application pair | trend/application pair |

The steward maintains `src/yelptext/protocol/<feature>.py` and `src/yelptext/interface/<feature>.py`. The implementation remains inside `src/yelptext/implementation/<feature>/`.

## What is created when a schema is frozen

For each approved boundary, create one coherent change containing:

1. the approved protocol and serialized example;
2. the real interface facade with the approved exported names;
3. the same-name fake interface under `tests/fake/interface/`;
4. the smallest schema-valid derived fixture needed to unblock consumers;
5. baseline acceptance cases and independently checked answers where an exact answer exists.

An LLM may construct this baseline kit after the human team fixes the schema. It may enumerate edge cases, produce small records, and calculate deterministic examples. The schema steward and at least one consumer must review it. The LLM must not silently decide an unresolved tokenizer policy, ranking convention, threshold, label, or other ground truth.

The baseline kit is not the complete feature test suite. It only proves the shared boundary is usable and gives downstream work a stable input.

## What each pair writes after the shared gate

### Data and corpus analysis pair

Owned locations:

```text
src/yelptext/cli/data_corpus_analysis.py
src/yelptext/command/data_corpus_analysis.py
src/yelptext/protocol/data_corpus_analysis.py
src/yelptext/interface/data_corpus_analysis.py
src/yelptext/implementation/data_corpus_analysis/**
tests/fake/interface/data_corpus_analysis.py
tests/fixtures/data_corpus_analysis/**
tests/test_data_corpus_analysis.py
notebooks/00_dataset_inspection.ipynb
notebooks/01_zipf_heaps_tokenizer.ipynb
```

The pair implements preparation, tokenizer behavior, corpus statistics, command orchestration, and report evidence. It also maintains the prepared-review and tokenizer boundary. Synthetic tests cover fixed behavior and edge cases; tokenizer policy and corpus-level quality require real-sample analysis.

### Search-engine pair

Owned locations:

```text
src/yelptext/cli/search_engine.py
src/yelptext/command/search_engine.py
src/yelptext/protocol/search_engine.py
src/yelptext/interface/search_engine.py
src/yelptext/implementation/search_engine/**
tests/fake/interface/search_engine.py
tests/fixtures/search_engine/**
tests/test_search_engine.py
notebooks/02_search_engine.ipynb
```

The pair tests more than its interface: index construction, persistence, exact TF-IDF/BM25 calculations, ordering and ties, empty/missing terms, command orchestration, CLI fixture-mode artifacts, and real-query analysis. While Group A is unfinished, its real search implementation receives the fake data/corpus interface automatically.

### Trend/application pair

Owned locations:

```text
src/yelptext/cli/trend_application.py
src/yelptext/command/trend_application.py
src/yelptext/protocol/trend_application.py
src/yelptext/interface/trend_application.py
src/yelptext/implementation/trend_application/**
tests/fake/interface/trend_application.py
tests/fixtures/trend_application/**
tests/test_trend_application.py
notebooks/03_sentiment_and_pmi.ipynb
notebooks/04_application_demo.ipynb
```

The pair owns sentiment, aggregation, PMI, sentence-level comparison detection, CLI artifacts, and report interpretation. Sentiment passes each original review string directly to VADER and does not use the shared tokenizer. PMI consumes the shared tokenizer. The comparison application owns sentence segmentation and consumes original review text. Exact counts and PMI examples can use fixtures; sector choice, minimum counts, sentiment interpretation, thresholds, and application quality require real samples.

Each pair writes and expands its own `test_<feature>.py` while implementing the feature. The LLM-generated baseline cases do not replace these tests.

## Fixture mode and real mode

The function under development is always real. Runtime mode selects only its upstream dependencies:

```text
fixture: tests.fake.interface.<upstream_feature>
real:    yelptext.interface.<upstream_feature>
```

For example, a search fixture run follows:

```text
CLI search/index command
  -> real search command
  -> real search interface and implementation
  -> fake data_corpus_analysis interface
```

Changing the config to `real` resolves the last line to `yelptext.interface.data_corpus_analysis`. Search imports, signatures, function calls, and internal file paths do not change.

## Test cases and standard answers

Use an expected answer only when the approved behavior has a defensible exact result:

- exact answers: joins, counts, postings, formula scores, deterministic ordering, fixed PMI examples, explicitly defined rule labels;
- structural checks: schemas, serialization, determinism, invariants, error behavior, artifact completeness;
- real-data evaluation: tokenizer policy, query usefulness, BM25 settings, PMI thresholds/stability, sentiment interpretation, application precision/recall, performance and memory.

A fake interface's returned data is an input to the feature under test, not that feature's expected output. Never generate an oracle with the implementation being tested, and never change an oracle merely to make a failing implementation pass.

## Shared-file rule

- `src/yelptext/cli/main.py` and `src/yelptext/runtime/` are integration-owned; change them only when composition itself changes.
- Each pair edits its own semantic files and directories.
- A protocol change requires its steward and at least one affected consumer.
- Consumer code never imports `tests.fake` directly and algorithms contain no `if fixture` branch.
- Reusable logic belongs in `src/yelptext`; notebooks display and interpret it.
- Do not commit Yelp data, large artifacts, secrets, or unnecessary notebook output.
