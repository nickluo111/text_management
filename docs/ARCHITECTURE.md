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
- `visualization`: common report-ready plotting conventions.
- `utils`: logging and reproducibility manifests only.

Domain modules must not import the CLI. Both index-time and query-time text processing must call the same `text` package.

## Configuration and outputs

- `pyproject.toml` defines packaging and the single `yelptext` command.
- `configs/*.toml` defines experiment parameters.
- `data/` stores unsubmitted local input/intermediate data.
- `artifacts/` stores reproducible generated outputs.
- `report/` stores only selected report material and writing notes.

Every long-running command should eventually emit a manifest containing the configuration, random seed, source-file metadata, tokenizer version/fingerprint, record counts, and elapsed time.

## Notebook policy

- Notebooks are grouped by assignment section, not by individual Python module.
- A notebook may orchestrate experiments, display dataframes/figures, and explain findings.
- A notebook must import algorithms and I/O from `src/yelptext` instead of redefining them.
- Full-data preprocessing and index building should run through the CLI.
- Clear large cell outputs before creating the final source archive.

## Implementation order

1. Streaming readers, schemas, and deterministic sampling.
2. Custom tokenizer plus baseline comparisons.
3. Zipf and Heaps experiments.
4. Inverted index and persistence.
5. TF-IDF and BM25 with hand-checked tests.
6. Query evaluation.
7. Business-category linkage and sentiment trends.
8. Co-occurrence/PMI drift.
9. Small application and final `run-all` pipeline.
