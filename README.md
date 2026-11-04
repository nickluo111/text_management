# Yelp Text Analysis

AI6122 Text Data Management & Processing group project. Dataset analysis,
search, trend analysis, and the small comparison-sentence application are
implemented through one package and CLI.

The report workflow deliberately uses two explicit configurations:

- dataset analysis and trend analysis use all 6,990,280 prepared reviews;
- search indexing and ranking use the deterministic 50,000-review sample.

Use `configs/full.toml` for Sections 3.1 and 3.3, and `configs/sample.toml` for
Section 3.2. No component-specific input override is needed. The abandoned full
search index is not required by the assignment and is not part of the
reproducible workflow.

## 1. Install

The project targets CPython 3.12.4. From the repository root:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python -m nltk.downloader stopwords averaged_perceptron_tagger vader_lexicon
```

Check the installation:

```powershell
python --version
python -m yelptext --help
```

On macOS/Linux, activate with `source .venv/bin/activate` and use `/` in paths.

## 2. Place the Yelp data

Download the Yelp Open Dataset and place the two required JSONL files at:

```text
data/raw/yelp_academic_dataset_business.json
data/raw/yelp_academic_dataset_review.json
```

Data access and licensing notes are in `docs/DATA_ACCESS.md`. Raw and processed
data are excluded from the source submission.

## 3. Prepare the shared inputs

### 3.1 Prepare all reviews

```powershell
python -m yelptext prepare --config configs/full.toml
```

This streams and validates the raw Yelp files, joins business metadata, and
writes:

```text
data/processed/reviews-full.jsonl
data/processed/reviews-full.audit.json
data/processed/reviews-full.audit.sqlite
```

### 3.2 Create the search/tokenizer sample

```powershell
python -m yelptext sample --config configs/full.toml --size 50000 --seed 42
```

The seeded, order-independent sampler writes
`data/processed/reviews-sample.jsonl` and preserves the complete prepared-review
schema. The same sample is used by tokenizer comparison and search.

### 3.3 Build the full CF/DF vocabulary

```powershell
python -m yelptext vocab build --config configs/full.toml
```

The command produces `data/processed/vocabulary-full.sqlite`. Vocabulary
construction is explicit and disk-backed; importing the tokenizer never rebuilds
it. Zipf and Heaps verify the vocabulary status and tokenizer fingerprint before
using it.

## 4. Run Section 3.1 - Dataset analysis

The registered commands perform the computation. Notebooks only load and
present generated artifacts.

```powershell
python -m yelptext analyze zipf --config configs/full.toml
python -m yelptext analyze heaps --config configs/full.toml
python -m yelptext analyze tokenizers --config configs/full.toml
```

Outputs:

```text
artifacts/zipf/
artifacts/heaps/
artifacts/tokenizer_comparison/
```

Presentation notebooks:

```text
notebooks/01_zipf.ipynb
notebooks/02_heaps.ipynb
notebooks/03_tokenizer_comparison.ipynb
```

Zipf and Heaps use the full corpus. Heaps uses a deterministic randomized review
order (seed 2026), records 1% checkpoints, fits the declared 10/30/50/100%
checkpoints, and verifies its final token/type counts against the vocabulary.

## 5. Run Section 3.2 - Search engine

The default index input is the 50,000-review sample even though the other default
analyses use the full corpus. Run the experiment driver from the repository root:

```powershell
python scripts/run_search_experiment.py --config configs/sample.toml
```

It builds or provenance-checks the sample SQLite inverted index, then runs the
six queries declared in `[analysis.search].queries` under both TF-IDF cosine
similarity and BM25. It also records query overlap, lexical coverage, timings,
and BM25 parameter sensitivity.

Outputs:

```text
artifacts/indexes/sample/index.sqlite3
artifacts/search_engine/sample/run_manifest.json
artifacts/search_engine/sample/report.json
artifacts/search_engine/sample/rankings.csv
artifacts/search_engine/sample/comparison.csv
artifacts/search_engine/sample/bm25_parameters.csv
```

`notebooks/04_search_engine.ipynb` is presentation-only and reads these files.

Individual queries can be run through the unified CLI after the index exists:

```powershell
python -m yelptext search "good service" --ranker tfidf --config configs/sample.toml
python -m yelptext search "good service" --ranker bm25 --config configs/sample.toml
```

The original single-process SQLite builder and ranking implementation remain the
default. The optional MapReduce builder is selected by adding `workers = 2` to
`workers = 8` under `[index]` when running the experiment driver. It changes only
how documents/postings are constructed in parallel; it publishes the same index
schema and uses the same TF-IDF/BM25 loader and ranking code. It is not enabled
by `configs/sample.toml`.

## 6. Run Section 3.3 - Trend analysis

Both commands use `data/processed/reviews-full.jsonl` through `configs/full.toml`.

### 6.1 Sector sentiment

```powershell
python -m yelptext trend sentiment --config configs/full.toml
```

The default comparison is `Italian Restaurants` versus `Fast Food`, grouped by
year with mean VADER compound scores, 95% confidence intervals, sentiment
shares, review counts, and mean stars. Select configured sectors with a
comma-separated argument when needed:

```powershell
python -m yelptext trend sentiment --config configs/full.toml --sectors "Italian Restaurants,Fast Food"
```

Outputs are written under `artifacts/sentiment/`.

### 6.2 PMI co-occurrence drift

```powershell
python -m yelptext trend pmi --config configs/full.toml
```

The default centre term is `service`, with a symmetric five-token window,
yearly independent counts, top 20 terms, an absolute co-occurrence floor of 10,
and a relative floor of 0.001. CLI flags can override the term, window, Top-N,
date range, and thresholds. Outputs are written under `artifacts/pmi/`.

`notebooks/05_sentiment_and_pmi.ipynb` only validates and visualizes the saved
sentiment and PMI artifacts; it does not rescan the corpus.

## 7. Configuration choices

| Configuration | Corpus/trends | Search index | Intended use |
|---|---|---|---|
| `configs/full.toml` | full | full path (not run) | Sections 3.1 and 3.3 |
| `configs/sample.toml` | sample | sample | Section 3.2 and quick checks |
| `configs/default.toml` | full | separate default path | base configuration |

All components use the same public reviewer and tokenizer interfaces. Switching
scale changes configuration paths, not imports or algorithms.

## 8. Architecture and documentation

The dependency direction is:

```text
CLI -> command -> interface -> implementation
```

- `docs/ARCHITECTURE.md`: package boundaries and dependency rules.
- `docs/DATA_ACCESS.md`: official dataset access and local file placement.
- `docs/YELP_SEARCH_SCHEMA.md`: canonical prepared-review schema.
- `src/yelptext/implementation/search_engine/README.md`: ranking formulas,
  persistence rules, and search edge cases.
- `report/3.1_dataset_analysis.md`: tokenizer, Zipf, and Heaps report section.
- `report/3.2_search_engine.md`: search-engine report section.
- `report/3.3_trend_analysis.md`: sentiment and PMI report section.

Create the source-code submission archive with an explicit group number:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_submission.ps1 -GroupNumber 00
```

The whitelist-based packager excludes local Yelp data, generated artifacts,
virtual environments, caches, and course-provided files.

The application reuses the deterministic 50,000-review sample and the shared
tokenizer:

```powershell
python -m yelptext app comparisons --config configs/sample.toml
```

It writes detected cross-business comparison sentences and a compact summary
under `artifacts/application/comparisons/`; Notebook 06 presents those files.
