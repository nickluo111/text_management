# Architecture

## Design rule

The repository is organized by semantic feature and by responsibility layer. A file name describes the assignment capability, never a temporary team label such as `group_b`.

```text
src/yelptext/
├── cli/                    # argparse registration only
├── command/                # use-case orchestration
├── protocol/               # proposed/approved shared schemas
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

`implementation/<feature>/` deliberately does not prescribe many files. Each pair can split its private implementation as needed. Only the approved public interface and serialized artifacts are cross-team commitments.

Shared schemas are consumer-driven and producer-owned. Downstream pairs specify the information and behavior they need; the upstream pair validates feasibility, maintains the protocol and real interface, and implements it. The producer and every affected consumer approve the boundary. This keeps one source of truth without letting either side define it alone.

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
4. `fixture` resolves an upstream semantic module from `tests.fake.interface`; `real` resolves the same module name from `yelptext.interface`.
5. Consumer call signatures do not change when the mode changes.
6. Real and fake interfaces may import different private implementations or data, but must export exactly the approved schema.

For example, while building search:

```text
yelptext index build --config tests/fixtures/fixture.toml
  -> real search command
  -> real search interface and implementation
  -> fake data_corpus_analysis interface
```

Switching the config to `real` changes only the upstream resolution to `yelptext.interface.data_corpus_analysis`; the search code and call sites remain unchanged.

## Test layout

Tests do not mirror every production layer:

```text
tests/
├── fake/interface/                 # only fake public interfaces
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

Each feature pair owns its complete `test_<feature>.py`, including implementation behavior, command orchestration, CLI fixture-mode behavior, output artifacts, edge cases, and exact calculations where applicable. Schema approval may add an LLM-assisted baseline fake/fixture and a few reviewed acceptance cases, but it does not prewrite the feature's test suite. A small direct test of a public interface is useful when it verifies the shared boundary or makes failures easier to locate. There is no duplicated fake CLI, fake command layer, or fake runtime.

## Configuration and presentation

- `.python-version` fixes CPython 3.12.4.
- `requirements.txt` and `pyproject.toml` pin the environment.
- `configs/*.toml` holds real experiment settings.
- `data/` holds unsubmitted local data.
- `artifacts/` holds reproducible generated outputs.
- notebooks present figures, tables, examples, and interpretation by importing package code.
