# Notebooks

Notebooks are the presentation layer for report artifacts. Core sampling,
tokenization, fitting, indexing, ranking, sentiment scoring, and PMI counting
run in registered commands or the search experiment driver.

## Generate artifacts first

Sections 3.1 and 3.3 use the full prepared corpus; search uses the retained
50,000-review sample:

```powershell
python -m yelptext analyze zipf --config configs/full.toml
python -m yelptext analyze heaps --config configs/full.toml
python -m yelptext analyze tokenizers --config configs/full.toml
python scripts/run_search_experiment.py --config configs/sample.toml
python -m yelptext trend sentiment --config configs/full.toml
python -m yelptext trend pmi --config configs/full.toml
python -m yelptext app comparisons --config configs/sample.toml
```

## Presentation order

1. `01_zipf.ipynb` reads `artifacts/zipf/`.
2. `02_heaps.ipynb` reads `artifacts/heaps/`.
3. `03_tokenizer_comparison.ipynb` reads `artifacts/tokenizer_comparison/`.
4. `04_search_engine.ipynb` reads `artifacts/search_engine/sample/`.
5. `05_sentiment_and_pmi.ipynb` reads the full-data artifacts under
   `artifacts/sentiment/` and `artifacts/pmi/` and creates report-oriented
   visualizations from those aggregate tables.
6. `06_application_demo.ipynb` reads
   `artifacts/application/comparisons/` and presents detected comparison
   sentences from the shared sample.

The first four notebooks do not build or refit their underlying analyses.
Notebook 05 may reshape aggregate CSV tables and save presentation figures, but
does not rescan reviews, rerun VADER, or recompute PMI events.

The source notebooks intentionally keep outputs small or empty. Before final
submission, open them after artifacts have been generated and verify that all
tables and figures render legibly.
