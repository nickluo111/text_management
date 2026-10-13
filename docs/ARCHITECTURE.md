# Architecture

## Design rule

The repository is organized by semantic feature and by responsibility layer. A file name describes the assignment capability, never a temporary team label such as `group_b`.

```text
src/yelptext/
├── cli/                    # argparse registration only
├── command/                # use-case orchestration
├── protocol/               # cross-group schemas only
│   ├── reviewer.py         # PreparedReview + PreparedReviewReader
│   └── tokenizer.py        # shared Tokenizer
├── interface/              # stable real public facades
├── implementation/         # private domain code, freely organized by each pair
│   ├── data_corpus_analysis/
│   ├── search_engine/
│   └── trend_application/
├── runtime/                # TOML loading and interface selection
├── support/                # genuinely shared non-domain helpers
└── visualization/          # shared plotting conventions
```

The three feature names repeat across layers so ownership is visible:

- `data_corpus_analysis`: raw/prepared reviews, tokenization, Zipf, Heaps, and tokenizer comparison;
- `search_engine`: index construction/storage, TF-IDF, BM25, query and retrieval analysis;
- `trend_application`: sentiment, PMI drift, and the independent NLP/IR application.

`implementation/<feature>/` deliberately does not prescribe many files. Each pair can split its private implementation as needed. Only `PreparedReviewReader` and `Tokenizer` currently cross group boundaries, so they are the only shared protocols. Search models/rankers and trend/application outputs remain private to their owning feature unless a real downstream runtime consumer is later identified.

Shared schemas are **consumer-defined and producer-implemented**. Groups B and C jointly write the `PreparedReviewReader` and `Tokenizer` protocols because they know the inputs their algorithms require. Group A reviews implementability, then implements the real interface without redefining the schema. B and C must still agree on one shared protocol rather than creating consumer-specific schema variants.

## Call direction

The normal path is:

```text
CLI registration -> command orchestration -> own real interface -> own implementation
                                           -> upstream interface selected by runtime mode
```

Rules:

1. `cli/` parses arguments and exposes commands; it contains no algorithms.
2. A feature command always invokes that feature's real interface. Fixture mode must never replace the code currently under development.
3. Only cross-feature upstream dependencies are selected through `runtime.load_interface_module()`.
4. `fixture` resolves an upstream semantic module from the current consumer's namespace (`tests.fake.search_engine` or `tests.fake.trend_application`); `real` resolves the same module name from `yelptext.interface`.
5. Consumer call signatures do not change when the mode changes.
6. Real and fake interfaces may import different private implementations or data, but must export exactly the approved schema.

For example, while building search:

```text
yelptext index build --config tests/fixtures/fixture.toml
  -> real search command
  -> real search interface and implementation
  -> search-owned fake data_corpus_analysis interface
```

The search command identifies itself to the resolver as `consumer="search_engine"`. Switching the config to `real` changes only the upstream resolution to `yelptext.interface.data_corpus_analysis`; the search algorithm and dependency calls remain unchanged.

Dependencies are declared per work unit rather than per pair. In particular, trend/application has three different input paths: sentiment consumes complete prepared-review text without the shared tokenizer, PMI consumes prepared reviews plus the shared tokenizer, and the comparison application consumes original text with sentence segmentation owned inside that feature. The detailed dependency register is maintained in `docs/TEAM_WORKFLOW.md`.

## Test layout

Tests do not mirror every production layer:

```text
tests/
├── fake/
│   ├── search_engine/              # B-owned fake A interface
│   └── trend_application/          # C-owned fake A interface
├── fixtures/
│   ├── data/raw/                   # mirrors real data/raw names
│   ├── data_corpus_analysis/
│   ├── search_engine/
│   └── trend_application/
├── test_data_corpus_analysis.py
├── test_search_engine.py
├── test_trend_application.py
├── test_raw_fixture.py
├── test_runtime.py
└── test_cli.py
```

Groups B and C each own their fake upstream, semantic fixture directory, and complete `test_<feature>.py`. Their fakes conform to the same protocol but may contain different cases appropriate to search or trend work. Tests cover implementation behavior, command orchestration, CLI fixture-mode behavior, artifacts, edge cases, and exact calculations where applicable. Group A owns tests of its real reviewer/tokenizer implementation. There is no duplicated fake CLI, fake command layer, or fake runtime.

## Configuration and presentation

- `.python-version` fixes CPython 3.12.4.
- `requirements.txt` and `pyproject.toml` pin the environment.
- `configs/*.toml` holds real experiment settings.
- `data/` holds unsubmitted local data.
- `artifacts/` holds reproducible generated outputs.
- notebooks present figures, tables, examples, and interpretation by importing package code.
