# Notebooks

These notebooks are the presentation layer for the report. Reusable code belongs in `src/yelptext`; notebooks should call that code and add tables, figures, qualitative examples, and written interpretation.

Recommended execution order:

1. `00_dataset_inspection.ipynb`
2. `01_zipf_heaps_tokenizer.ipynb`
3. `02_search_engine.ipynb`
4. `03_sentiment_and_pmi.ipynb`
5. `04_application_demo.ipynb`

Use `configs/sample.toml` while developing. Generate final results with `configs/full.toml` and the CLI, then load the resulting artifacts into the notebooks. Do not load the full review file into a pandas dataframe.

Before submission, restart each notebook, run it in order where practical, and clear any very large outputs.
