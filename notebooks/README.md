# Notebooks

This directory contains only report analysis and visualization notebooks. Code
review, interface debugging, and tokenizer audit evidence belong in source or
Markdown documentation rather than in this directory.

The notebooks use the formal reviewer/tokenizer interfaces and generated
vocabulary rather than candidate Group A scripts.

Recommended execution order:

1. `01_zipf.ipynb` — reads vocabulary CF; no review rescan
2. `02_heaps.ipynb` — streams/tokenizes prepared reviews for growth points
3. `03_tokenizer_comparison.ipynb` — compares the custom tokenizer with two NLTK baselines on the shared seed-42 sample
4. `04_search_engine.ipynb`
5. `05_sentiment_and_pmi.ipynb`
6. `06_application_demo.ipynb`

When opened directly, the analysis notebooks locate the repository root
automatically and default to `configs/full.toml`. Use `configs/sample.toml`
while developing by executing through the CLI with an explicit config; the CLI
selection overrides the notebook default:

```powershell
yelptext analyze zipf --config configs/full.toml
yelptext analyze heaps --config configs/sample.toml
yelptext analyze heaps --config configs/full.toml
yelptext analyze tokenizers --config configs/full.toml
```

Executed notebooks are written under `artifacts/notebooks/`. Each experiment
writes figures and tables directly under `artifacts/<experiment-name>/`, for
example `artifacts/zipf/`, `artifacts/heaps/`, and
`artifacts/tokenizer_comparison/`. Heaps streams reviews and must not load the
full review file into a pandas dataframe.

Before submission, restart each notebook, run it in order where practical, and clear any very large outputs.
