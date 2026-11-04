# Search engine

The public entry point is `yelptext.interface.search_engine`. `index.py` owns
SQLite construction/storage and read-only access; `ranking.py` implements
TF-IDF cosine and BM25 without a third-party ranker. Commands resolve only the
upstream data/tokenizer interface through the shared runtime resolver.

The default SQLite backend has completed the real 50,000-review experiment:
index construction, persistence/reload, six queries under both rankers, and BM25
parameter analysis are stored under `artifacts/search_engine/sample/` and
presented by `notebooks/04_search_engine.ipynb`.
The optional compact backend is implemented and was checked against the default
backend during development.
The full-corpus performance run was cancelled; there are no completed
full-corpus build-time, query-latency, or memory measurements.

## Reproduce the sampled experiment

After preparing the shared 50,000-review sample, run the experiment driver from
the repository root:

```powershell
python scripts/run_search_experiment.py --config configs/sample.toml
python -m yelptext search "good service" --ranker tfidf --config configs/sample.toml
python -m yelptext search "good service" --ranker bm25 --config configs/sample.toml
```

Paths in configuration files are relative to the current working directory, as
with the other project commands.

The default build saves `index.sqlite3` under `[index].output_dir`. It refuses to replace
an existing index. Use `index build --output-dir <new-directory>` and the matching
`search --index-dir <new-directory>` for a separate run. `search --top-k N`
overrides `[search].top_k`. A query and `--queries` are mutually exclusive.
Single and batch queries print JSON; `--output` also writes that same JSON
atomically. Batch output contains rankings, not relevance metrics: those require
separately judged relevance labels.

## Public Python API

```python
from yelptext.interface.data_corpus_analysis import (
    create_review_reader, create_tokenizer_pipeline,
)
from yelptext.interface.search_engine import build_index, load_index, search

pipeline = create_tokenizer_pipeline(skip_types={"punctuation"}, enable_pos=False)
reader = create_review_reader("data/processed/reviews-sample.jsonl")
stats = build_index(reader, pipeline, "artifacts/indexes/example")
with load_index("artifacts/indexes/example", pipeline) as index:
    hits = search(index, "good service", ranker="bm25", top_k=10)
    print(index.stats())
    print(index.postings("service"))
    for hit in hits:
        print(hit.doc_id, hit.score, hit.business_name, hit.text)
```

Real mode requires the standard prepared-review schema and the shared pipeline's
NLTK stopwords resource. POS is disabled by default. Search does not read or
require the full vocabulary database. It computes its own statistics from the
actual indexed documents and filtered terms. `tokenizer.skip_types` and
`tokenizer.enable_pos` configure the pipeline; the existing canonical policy
flags must remain true because the shared public factory does not expose those
switches.

## Optional compact storage

Omitting `[index].storage` selects `"sqlite"`. The separate
`configs/sample-compact.toml` selects `storage = "compact"` in its `[index]`
section and uses its own output directory. Build and search must use the same
storage selection:

```powershell
python -m yelptext index build --config configs/sample-compact.toml
python -m yelptext search "good service" --ranker tfidf --config configs/sample-compact.toml
python -m yelptext search "good service" --ranker bm25 --config configs/sample-compact.toml
```

The compact output directory must not already exist. For another build, pass
`--output-dir <new-directory>` and use `--index-dir <new-directory>` when
searching. Keep `configs/sample.toml` and its existing SQLite output intact:
the sample notebook runner uses that backend and verifies its recorded hashes.
The temporary compact trial index was removed during cleanup; the commands above
rebuild it from the retained prepared sample.

Python callers select the compact builder and loader explicitly. The same
`search()` function supports both backends:

```python
from yelptext.interface.data_corpus_analysis import (
    create_review_reader, create_tokenizer_pipeline,
)
from yelptext.interface.search_engine import (
    build_compact_index, load_compact_index, search,
)

pipeline = create_tokenizer_pipeline(skip_types={"punctuation"}, enable_pos=False)
reader = create_review_reader("data/processed/reviews-sample.jsonl")
stats = build_compact_index(reader, pipeline, "artifacts/indexes/compact-example")
with load_compact_index("artifacts/indexes/compact-example", pipeline) as index:
    hits = search(index, "good service", ranker="bm25", top_k=10)
    print(index.stats(), index.term_df("service"))
```

`build_compact_index()` also accepts `progress` (a callback receiving progress
dictionaries) and `max_memory_bytes` (an estimated build working-set budget).
The CLI reads that budget from `[performance].max_memory_bytes`. It is not a
hard process-memory limit: compact construction keeps packed postings in memory,
so larger runs still require a fresh resource check.

Compact storage consists of `compact.sqlite3`, `lengths.npy`, `norms.npy`, and
`manifest.json`. It stores integer document numbers and packed term/document
postings, with review metadata in SQLite and lengths/norms in NumPy arrays.
The completed directory is published atomically. Loading validates metadata,
array layout, and the tokenizer fingerprint. Scoring retains the formulas,
full document normalization, OOV handling, and document-ID tie breaking below.
Neither this storage design nor a sample trial establishes full-corpus
performance.

## Scoring conventions

For indexed term `t`, let `tf(t,d)` be its count in document `d`, `df(t)` the
number of indexed documents containing it, and `N` the number of documents.
All logarithms below are natural.

* TF-IDF: `idf(t) = ln((N + 1) / (df(t) + 1)) + 1` and, for a nonzero count,
  `w(t,d) = (1 + ln(tf(t,d))) * idf(t)`. Query weights use the same definition.
  Score is the dot product divided by both vector norms. The document norm
  includes **all** indexed terms in the document, not just query matches.
* BM25: `idf(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))`. Each query term
  contributes `qtf(t) * idf(t) * tf(t,d) * (k1 + 1) /
  (tf(t,d) + k1 * (1 - b + b * length(d) / avgdl))`.
  Defaults: `k1=1.5`, `b=0.75`; repeated query terms contribute linearly.
* Unknown query terms are dropped before computing query weights/norms. No
  `<UNK>` posting is created and rare terms are retained.
* Empty, punctuation-only (under the default filter), and all-unknown queries
  return an empty list. Nonmatching documents are not padded into Top-K.
* A valid review whose terms become empty remains in `N` with length zero.
  `avgdl = total_terms / N`, or zero for an empty corpus. Such documents never
  match; an empty corpus/index is supported without division by zero.
* Results sort by descending score, then ascending `doc_id`. Text and business
  metadata are returned unchanged and do not influence the relevance score.

## Persistence and validation

The default SQLite index stores review metadata, document lengths/norms, term DF/IDF,
postings, format/formula versions, and the pipeline fingerprint. The builder
streams the reader and stores intermediate counts on disk. A temporary database
is published only after a successful build; a failed build leaves no published
partial index. Duplicate document IDs are errors.

Loading opens the database read-only and verifies its metadata and format.
Both load and query verify tokenizer compatibility; changing filtering requires
rebuilding the index. `SearchIndex` is a context manager and should be closed.
`stats()` returns a copy of metadata and `postings(term)` provides diagnostic
access sorted by document ID.

Tests cover hand-counted postings, independent TF-IDF/BM25 scores, repeated/OOV
terms, stable ties, empty data, persistence/reload, incompatible tokenizers,
invalid parameters, failure cleanup, runtime switching, and CLI artifacts.
The default backend accumulates matching candidate scores in memory; the compact
backend uses a dense score array and vectorized posting operations. Full-corpus
performance and judged relevance have not been established by these tests.

## Real 50,000-review experiment

The completed experiment uses `configs/sample.toml` and the default SQLite
backend. The prepared sample, index, and result artifacts are retained after
cleanup. These sample artifacts are sufficient to rerun search and display the
notebook analysis:

```powershell
python -m yelptext search "good service" --ranker bm25 --config configs/sample.toml
```

The sample contains 50,000 documents, 56,040 indexed terms and 5,247,734 filtered
term occurrences (`avgdl = 104.95468`). Its index is
`artifacts/indexes/sample/index.sqlite3`; the prepared input is
`data/processed/reviews-sample.jsonl`. The index includes the review text and
business metadata needed to return search results.

To verify the retained sample and rerun the search experiment, run:

```powershell
python scripts/run_search_experiment.py --config configs/sample.toml
```

The runner checks the exact sample count, builds the SQLite index, records input
provenance and measured build time, and runs the queries declared directly in
`[analysis.search].queries`. Notebook 04 only reads those artifacts. An existing
index is reused only when the prepared-input hash matches its prior manifest;
changing the configured queries reruns analysis without unnecessarily rebuilding
the query-independent index. `--build-only` stops after index/manifest
preparation.

The public `run_experiment()` helper compares each configured query under both
rankers, records warm query timings, and checks BM25 parameter sensitivity.
It writes `report.json`, `rankings.csv`, `comparison.csv`, and
`bm25_parameters.csv` to `artifacts/search_engine/sample/`. The notebook adds
figures, source metadata and per-query interpretation. Overlap and lexical term
coverage describe ranking behavior; neither is a relevance metric or evidence
that one ranker is universally better. These are sample results, not full-corpus
scalability conclusions.

Raw review/business files are not needed to query the retained index or rerun
the sample experiment. Creating a new sample or prepared corpus requires the
original Yelp files; see `docs/DATA_ACCESS.md`.
