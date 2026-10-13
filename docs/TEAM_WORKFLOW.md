# Six-person team workflow

## Pair responsibilities

Use three pairs with flexible internal division and mutual backup:

| Feature | Assignment scope | Owned semantic files |
| --- | --- | --- |
| Data and corpus analysis | preparation, tokenizer, Zipf, Heaps, tokenizer comparison (§3.1-§3.2) | `data_corpus_analysis` files |
| Search engine | index, persistence, TF-IDF, BM25, queries and retrieval analysis (§3.3) | `search_engine` files |
| Trends and application | sentiment, PMI drift, independent application (§3.4-§3.5) | `trend_application` files |

Pairs may organize files inside their `implementation/` directory freely. Cross-team changes are limited to approved interfaces, shared configuration, fixtures, and integration code.

## What must be settled before pairs work independently

Freeze the smallest schemas that cross feature boundaries. For every boundary, agree on:

- exported names and signatures;
- field names, types, nullability, and serialized representation;
- iteration, missing-data, and error behavior;
- one example call and one serialized example;
- which pair owns the interface and fake.

The first likely boundaries are prepared reviews and the tokenizer from data/corpus analysis, followed by a read-only search index if trend/application work consumes search results. The files under `src/yelptext/protocol/` are recommendations for this discussion, not decisions.

When a schema is approved, make one coherent update containing:

1. the final protocol;
2. the real public facade in `src/yelptext/interface/<feature>.py`;
3. the same-name fake in `tests/fake/interface/<feature>.py`;
4. the smallest derived fixture needed by consumers;
5. tests that establish the agreed behavior.

The fake interface is the executable stand-in. It reads its semantic fixture directory and returns objects matching the approved schema. Consumers do not manually import a special fake class or change a path.

## Work after schemas are frozen

### Data and corpus analysis pair

Complete:

- `command/data_corpus_analysis.py`;
- `interface/data_corpus_analysis.py`;
- freely chosen modules in `implementation/data_corpus_analysis/`;
- `tests/test_data_corpus_analysis.py` and its semantic fixtures;
- data inspection and corpus-analysis notebooks.

Publish the prepared-review and tokenizer fakes early so the other pairs can start. Tokenizer behavior that is purely specified can be tested synthetically; policy selection and normalization quality must later be checked on a documented real sample.

### Search-engine pair

Complete:

- `command/search_engine.py`;
- `interface/search_engine.py`;
- freely chosen modules in `implementation/search_engine/`;
- `tests/test_search_engine.py` and search fixtures;
- the search notebook and final real-query analysis.

Start with `fixture` mode. The real search implementation consumes the fake `data_corpus_analysis` interface automatically. Use small, independently checked postings and score examples for deterministic index/ranking behavior. After the upstream real interface is ready, switch the config to `real`; do not alter imports, function signatures, or fixture paths in the search implementation.

### Trend/application pair

Complete:

- `command/trend_application.py`;
- `interface/trend_application.py`;
- freely chosen modules in `implementation/trend_application/`;
- `tests/test_trend_application.py` and trend/application fixtures;
- sentiment, PMI, and application notebooks.

Begin against fake prepared reviews (and fake tokenizer if the approved design requires it). Exact aggregation and PMI examples can be checked synthetically. Sector selection, minimum counts, sentiment interpretation, application thresholds, and error analysis require real data.

## How fixture and real modes migrate

The runtime resolver maps a semantic interface name without changing consumer code:

| Config mode | `data_corpus_analysis` resolves to |
| --- | --- |
| `fixture` | `tests.fake.interface.data_corpus_analysis` |
| `real` | `yelptext.interface.data_corpus_analysis` |

The same rule applies to the other semantic interfaces. The implementation currently under test is always real; only upstream dependencies are resolved by mode. Once all upstreams are implemented, the same feature command can run over the small invented raw data using real mode before moving to a real Yelp sample.

## What counts as an expected output

An expected file is not required merely because a fixture exists.

- Use exact expected outputs for deterministic, fully specified behavior: joins, counts, postings, formula scores, ordering/tie rules, PMI on fixed counts, or fixed-rule labels.
- Use schema checks and invariants when many valid representations exist.
- Use labeled cases only when the label was independently decided; never generate the oracle using the implementation being tested.
- For tokenizer policy, query usefulness, BM25 settings, PMI thresholds, sentiment interpretation, and application quality, fixture tests establish functional correctness only. Tune and evaluate these on documented real samples.
- A fake interface's returned data is an upstream input, not automatically the expected result of the feature under test.

Therefore CLI-oriented tests should compare structured artifacts with expected results only where a real standard answer exists. Otherwise they should validate schema, determinism, invariants, and error behavior.

## Integration rules

- Consumer code never imports `tests.fake` directly.
- No `if fixture` branches belong inside algorithms.
- A schema change requires the owner and at least one consumer to review it.
- Changes to a tokenizer fingerprint require dependent indexes to be rebuilt, not search code to be rewritten.
- Reusable logic belongs in `src/yelptext`; notebooks display and interpret it.
- Do not commit Yelp data, large artifacts, secrets, or unnecessary notebook output.
