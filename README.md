# Yelp Text Analysis

Course-project scaffold for AI6122 Text Data Management & Processing. The project uses one installable Python package, one public CLI, small presentation notebooks, and semantic feature boundaries that six contributors can work on as three flexible pairs.

## Quick start

The reference interpreter is **CPython 3.12.4**.

```powershell
python --version
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python -m nltk.downloader vader_lexicon
python -m pytest -q
yelptext --help
```

The VADER lexicon is runtime data rather than a Python package, so it cannot be pinned in `requirements.txt`.

## Current status

The repository is intentionally in a pre-schema state:

- CLI registration, TOML loading, runtime mode selection, raw synthetic data, and structural tests work now.
- `src/yelptext/protocol/reviewer.py` and `tokenizer.py` contain the only two cross-group schema recommendations; they are not yet approved contracts.
- real interfaces, fake interfaces, command implementations, and domain implementations remain empty until the schemas are approved.
- derived fixtures and exact expected outputs will be added only where the approved behavior makes them meaningful.

There is no second test CLI. The normal command accepts either `configs/default.toml` (`real`) or `tests/fixtures/fixture.toml` (`fixture`). The domain being developed always runs its real implementation; fixture mode substitutes only unfinished upstream interfaces.

```powershell
yelptext index build --config tests/fixtures/fixture.toml
yelptext search "great service" --config configs/default.toml
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for layer boundaries and [docs/TEAM_WORKFLOW.md](docs/TEAM_WORKFLOW.md) for the collaboration procedure.

## Data and notebooks

Place the Yelp business and review files under `data/raw/` using the names documented in `data/README.md`. Real data and generated artifacts are ignored and must not be submitted. Acquisition notes are in `docs/DATA_ACCESS.md`.

Notebooks are presentation drivers. They import reusable work from `src/yelptext`; algorithms must not exist only in notebooks.
