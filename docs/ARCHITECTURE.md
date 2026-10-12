# Architecture

## Principle

The project is one installable Python package with one unified CLI. The CLI only parses arguments and delegates work; algorithms remain importable and testable independently. A small set of notebooks provides the human-readable experiment and report layer without duplicating the implementation.

```text
CLI
 ├─ data preparation ──> prepared sample/business lookup
 ├─ dataset analysis ──> Zipf, Heaps, tokenizer comparison
 ├─ index build ───────> persisted inverted index + metadata
 ├─ search ────────────> TF-IDF or BM25 ranked results
 ├─ trend analysis ────> sentiment and PMI outputs
 └─ application ───────> comparison-sentence results
```

## Package boundaries

- `data`: streaming I/O, validation, sampling, and business/review linkage.
- `text`: the single shared tokenization/normalization policy.
- `analysis`: Zipf, Heaps, and tokenizer-comparison experiments.
- `search`: custom inverted index, storage, query orchestration, and evaluation.
- `search.rankers`: ranking formulas implemented from scratch.
- `trends`: lexicon sentiment, aggregation, co-occurrence, and PMI drift.
- `applications`: the independent 10-mark NLP/IR application.
- `contracts`: provisional cross-group structural interfaces.
- `providers`: only runtime-selectable adapters for confirmed cross-group
  boundaries; it does not contain the groups' domain algorithms.
- `visualization`: common report-ready plotting conventions.
- `utils`: logging and reproducibility manifests only.

Domain modules must not import the CLI. Both index-time and query-time text processing must call the same `text` package.

Top-level commands register independently under `yelptext.commands`. The root
`cli.py` only composes those registration modules, which reduces merge conflicts
between responsibility groups. Team ownership and integration rules are defined
in `docs/TEAM_WORKFLOW.md`.

## Configuration and outputs

- `.python-version` fixes the reference interpreter to CPython 3.12.4.
- `requirements.txt` pins the complete reproducible coursework environment.
- `pyproject.toml` defines packaging and the single `yelptext` command.
- `configs/*.toml` defines experiment parameters.
- `data/` stores unsubmitted local input/intermediate data.
- `artifacts/` stores reproducible generated outputs.
- `report/` stores only selected report material and writing notes.

Every long-running command should eventually emit a manifest containing the configuration, random seed, source-file metadata, tokenizer version/fingerprint, record counts, and elapsed time.

There is deliberately no separate test CLI and no `--test-data` algorithm
branch. The intended composition root selects same-contract providers from
`tests/fakes` in fixture mode and from `src/yelptext/providers/real` in real
mode. Domain functions receive those providers through their confirmed
interfaces and never import a fake directly. The schema-independent module
resolver is implemented; the provider modules intentionally export no classes
until their contracts are approved.

The current `tests/fixtures/fixture.toml` declares fixture mode and raw source
paths only. Group-specific fixture and provider modules are reserved as empty
placeholders; derived data and implementations are added only after the relevant
schema is approved. The final fixture integration run exercises real providers
over small invented data before sample/full runs.

## Notebook policy

- Notebooks are grouped by assignment section, not by individual Python module.
- A notebook may orchestrate experiments, display dataframes/figures, and explain findings.
- A notebook must import algorithms and I/O from `src/yelptext` instead of redefining them.
- Full-data preprocessing and index building should run through the CLI.
- Clear large cell outputs before creating the final source archive.

## Implementation order

1. Approve cross-group contracts and serialized examples.
2. Add same-contract fake providers, group fixtures, and contract tests.
3. Implement real streaming readers, preparation, and deterministic sampling.
4. Implement and refine the real tokenizer against a documented sample.
5. Develop corpus analysis, search, and trends in parallel against fake upstreams.
6. Make real providers pass the same contract tests and switch composition.
7. Run sample/full experiments, notebooks, and the final `run-all` pipeline.
