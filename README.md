# Yelp Text Analysis

Course-project scaffold for AI6122 Text Data Management & Processing.

## Current status

The package layout and unified CLI entry point are established. Algorithm modules are placeholders and are intentionally not implemented yet.

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
yelptext --help
```

The equivalent non-installed entry point is:

```powershell
python -m yelptext --help
```

## Notebooks

The notebooks under `notebooks/` are presentation and analysis drivers. They
must import reusable logic from `src/yelptext`; core algorithms must not be
implemented only inside a notebook. Use the CLI for reproducible full runs and
the notebooks for figures, tables, comparisons, and report interpretation.

See `docs/DATA_ACCESS.md` before obtaining the Yelp dataset. Data and generated artifacts must not be committed or included in the final source-code archive.
