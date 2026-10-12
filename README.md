# Yelp Text Analysis

Course-project scaffold for AI6122 Text Data Management & Processing.

## Current status

The package layout and unified CLI entry point are established. Algorithm modules are placeholders and are intentionally not implemented yet.

## Quick start

The project is pinned to **CPython 3.12.4**. Confirm the interpreter before
creating the environment:

```powershell
python --version
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python -m nltk.downloader vader_lexicon
yelptext --help
```

The NLTK download installs the VADER lexicon data used by the sentiment
experiment; it is not a Python package and therefore cannot be listed in
`requirements.txt`.

The equivalent non-installed entry point is:

```powershell
python -m yelptext --help
```

## Development with synthetic data

There is no separate test CLI. Development and full-data runs use the same
`yelptext` entry point. Runtime configuration will select same-contract fixture
or real providers after the team approves those contracts.

```powershell
python -m pytest tests/test_fixtures.py -q
```

At present only Yelp-shaped raw fixture records exist. Proposed Protocols are
under `src/yelptext/contracts/`, but no derived fixture or fake/real provider is
implemented until the team confirms its schema. Consequently, the CLI commands
still confirm registration and dispatch only.

After approval, each interface owner adds its fake, group-specific derived
fixture, and contract tests together. Fixture and real modes then use the same
CLI and consumer calls; only runtime provider composition changes. See
`tests/fixtures/README.md` and `docs/TEAM_WORKFLOW.md`.

## Notebooks

The notebooks under `notebooks/` are presentation and analysis drivers. They
must import reusable logic from `src/yelptext`; core algorithms must not be
implemented only inside a notebook. Use the CLI for reproducible full runs and
the notebooks for figures, tables, comparisons, and report interpretation.

See `docs/DATA_ACCESS.md` before obtaining the Yelp dataset. Data and generated artifacts must not be committed or included in the final source-code archive.

Project boundaries are documented in `docs/ARCHITECTURE.md`; the six-person
group workflow, shared interfaces, reviews, and integration checkpoints are in
`docs/TEAM_WORKFLOW.md`.
