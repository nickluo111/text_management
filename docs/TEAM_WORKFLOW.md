# Six-person team workflow

## Working model

Use three responsibility groups of two people. Each group owns a coherent
assignment area, but the two members work as a pair rather than dividing it into
two isolated personal modules. This gives every area an implementer and a backup,
while still allowing the pair to rebalance work when one task takes longer than
expected.

Do not make the project a relay in which one group must completely finish before
the next group starts. Agree on small interfaces and test fixtures first; all
three groups can then implement against those contracts in parallel.

## Responsibility groups

### Group A: data and corpus analysis (two people)

Owns:

- streaming Yelp JSONL/ZIP input, validation, deterministic sampling, and the
  business-review join;
- the shared normalization and tokenizer policy;
- Zipf's law, Heaps' law, and tokenizer-comparison experiments;
- `notebooks/00_data_check.ipynb` and `notebooks/01_corpus_analysis.ipynb`;
- CLI registration in `commands/prepare.py` and `commands/analyze.py`.

Suggested internal split: one member leads data preparation and one leads corpus
analysis. Both review the tokenizer because it is a dependency of every group.

### Group B: indexing and retrieval (two people)

Owns:

- the custom inverted index, document statistics, serialization, and loading;
- TF-IDF and BM25 scoring from scratch;
- interactive search, batch queries, retrieval evaluation, and timing;
- `notebooks/02_search_evaluation.ipynb`;
- CLI registration in `commands/index.py` and `commands/search.py`.

Suggested internal split: one member leads index/storage and one leads ranking and
evaluation. Each must be able to explain the other member's formulas and tests.

### Group C: trends and application (two people)

Owns:

- VADER sentiment scoring and time/category aggregation;
- term co-occurrence, PMI calculation, and temporal drift analysis;
- the comparison-sentence application and its evaluation;
- `notebooks/03_trend_analysis.ipynb` and `notebooks/04_application.ipynb`;
- CLI registration in `commands/trend.py` and `commands/application.py`.

Suggested internal split: one member leads sentiment and one leads PMI/application.
Both review category filtering, date bucketing, and evaluation examples.

## Shared contracts agreed before implementation

Freeze the following small contracts during the first checkpoint. Changes are
allowed, but require a short cross-group review because they affect multiple
areas.

### Prepared review record

At minimum, downstream code can rely on:

| Field | Type | Meaning |
| --- | --- | --- |
| `review_id` | `str` | Stable Yelp review identifier |
| `business_id` | `str` | Join key for business metadata |
| `text` | `str` | Original review text |
| `stars` | `float` | Review rating |
| `date` | ISO date/datetime | Review timestamp |
| `categories` | `list[str]` | Normalized business categories |

Group A owns parsing these values. Groups B and C may initially use the fixture
with exactly this schema rather than waiting for full-data preparation.

### Tokenizer contract

The public operation is conceptually:

```python
tokenize(text: str) -> list[str]
```

The same implementation and configuration must be used at index time, query
time, and corpus-analysis time. Its manifest/fingerprint must be saved with a
persisted index so that incompatible indexes cannot silently be queried.

### Index-reader contract

Retrieval code should access postings, document length, corpus document count,
and document frequency through a small public reader interface. It should not
depend on the index builder's private in-memory structures. Group B may refine
the exact class names, but should publish them before other code imports them.

### Artifact contract

Every long-running command writes outputs below `artifacts/` and a manifest that
records configuration, seed, source metadata, tokenizer fingerprint, record
counts, and elapsed time. Notebooks consume these artifacts; they do not rerun
the full dataset automatically.

## Shared fixtures unblock parallel work

Create and commit a tiny artificial fixture under `tests/fixtures/` before
full-data implementation. It should contain a small business file and review
file with:

- several businesses and overlapping categories;
- reviews in multiple months or years;
- repeated and rare terms for Zipf/Heaps checks;
- punctuation, emoji, apostrophes, numbers, and mixed case for tokenization;
- positive, neutral, and negative language;
- known co-occurrences around a target such as `service`;
- a few clear comparison sentences and non-comparison controls.

Also commit expected prepared records and a very small expected index. These are
test data, not a sample copied from Yelp. The fixture lets Groups B and C start on
day one and makes failures reproducible.

## CLI ownership and merge-conflict policy

There remains one installed command, `yelptext`, but its registration is split by
area:

| File | Primary owner |
| --- | --- |
| `commands/prepare.py`, `commands/analyze.py` | Group A |
| `commands/index.py`, `commands/search.py` | Group B |
| `commands/trend.py`, `commands/application.py` | Group C |
| `commands/run_all.py` | Temporary integration group |
| `commands/_common.py`, `cli.py` | Shared; cross-group review required |

Each command module should only parse arguments and call an importable domain
function. Algorithms and file I/O belong in the domain packages, not in command
handlers. Avoid adding every implementation option to `cli.py`; this would
recreate a high-conflict shared file.

## Review and integration

Use circular cross-group review so each area receives an independent check:

- Group A reviews Group B's formulas, index assumptions, and hand-calculated
  retrieval test;
- Group B reviews Group C's aggregation, PMI formula, and evaluation method;
- Group C reviews Group A's sampling, joins, tokenizer, and corpus statistics.

For integration, temporarily nominate one person from each group. This is a
rotating role, not a fourth permanent team. The three integrators own
`commands/run_all.py`, resolve interface mismatches, reproduce the clean run, and
verify that notebooks read generated artifacts.

## Checkpoints that avoid serial dependency

1. **Contracts and fixtures:** agree on schemas, tokenizer behavior, artifact
   paths, configuration keys, and expected tiny outputs.
2. **Tiny fixture:** every command executes end to end on artificial data and
   unit tests cover hand-computable cases.
3. **Small sample:** run each area independently on a deterministic sample;
   measure time and memory before scaling.
4. **Larger sample:** integrate all artifacts, freeze figure/table schemas, and
   begin report interpretation.
5. **Full data and release:** run `yelptext run-all`, review outputs, execute the
   notebooks from a clean environment, and prepare the source archive.

A group should publish a stub artifact matching its agreed schema when its real
implementation is not ready. Downstream groups can continue against the stub
and later replace it without changing their logic.

## Git and pull-request rules

- Use short feature branches by area, for example `data/tokenizer`,
  `search/bm25`, or `trends/pmi`.
- Keep commits focused; do not combine notebook output churn with algorithm
  changes.
- Rebase or merge `main` frequently and open small pull requests.
- Require one teammate review and one circular cross-group review for shared
  contracts, formulas, or evaluation design.
- Do not commit raw Yelp data, generated large artifacts, secrets, or notebook
  cache/output that is not needed for marking.
- Record important decisions in the pull request and update this document or the
  architecture document when the decision changes a contract.

## Definition of done for a work item

A work item is complete only when it has:

- reusable implementation under `src/yelptext`, not only notebook cells;
- focused unit tests and an artificial-fixture integration test;
- a wired CLI command where applicable;
- deterministic artifact output and manifest metadata;
- a notebook section that presents the result without duplicating algorithms;
- report-ready interpretation or notes, including limitations;
- both group members able to explain and maintain it;
- the required cross-group review for formulas or shared contracts.

## Contribution record

Maintain a simple table in the final report or project log. Record concrete
deliverables and reviews rather than percentages chosen at the end.

| Member | Primary deliverables | Secondary/review work | Evidence (PR/commit/notebook) |
| --- | --- | --- | --- |
| Member 1 |  |  |  |
| Member 2 |  |  |  |
| Member 3 |  |  |  |
| Member 4 |  |  |  |
| Member 5 |  |  |  |
| Member 6 |  |  |  |
