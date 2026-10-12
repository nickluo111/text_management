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
  business-review join (`D1`);
- the shared normalization and tokenizer policy (`DA3`);
- Zipf's law, Heaps' law, and tokenizer-comparison experiments (`DA1`, `DA2`,
  `DA4`);
- `notebooks/00_data_check.ipynb` and `notebooks/01_corpus_analysis.ipynb`;
- CLI registration in `commands/prepare.py` and `commands/analyze.py`.

Suggested internal split: one member leads data preparation and one leads corpus
analysis. Both review the tokenizer because it is a dependency of every group.

### Group B: indexing and retrieval (two people)

Owns:

- the custom inverted index, document statistics, serialization, and loading
  (`SE1`);
- TF-IDF and BM25 scoring from scratch (`SE2`, `SE3`);
- interactive search, at least five batch queries, retrieval evaluation, and
  timing (`SE4`);
- `notebooks/02_search_evaluation.ipynb`;
- CLI registration in `commands/index.py` and `commands/search.py`.

Suggested internal split: one member leads index/storage and one leads ranking and
evaluation. Each must be able to explain the other member's formulas and tests.

### Group C: trends and application (two people)

Owns:

- VADER sentiment scoring and time/category aggregation (`TA1`, `TA2`);
- term co-occurrence, PMI calculation, and temporal drift analysis (`TA3`,
  `TA4`, and `TA5`);
- the comparison-sentence application and its evaluation (`APP1`);
- `notebooks/03_trend_analysis.ipynb` and `notebooks/04_application.ipynb`;
- CLI registration in `commands/trend.py` and `commands/application.py`.

Suggested internal split: one member leads sentiment and one leads PMI/application.
Both review category filtering, date bucketing, and evaluation examples.

## Dependency overview

The references in this document were checked against the September 2026
assignment brief. The brief numbers sections, but does not number the bullets
inside each section. Therefore, `§3.4.2 bullet 2` means the second visible bullet
under section 3.4.2. Requirements written as prose rather than bullets are named
`Dataset paragraph`, `Indexing paragraph`, `Analysis paragraph`, or
`Application paragraph`. The Work IDs below are project-local shorthand, not
official assignment numbering.

### Dependency flowchart

![Dependency map for the three parallel responsibility groups](assets/team-workflow-dependencies.png)

Solid arrows are hard data or implementation dependencies. The dashed arrow is
optional reuse: the application may reuse the shared tokenizer, but §3.5 allows
another defensible NLP/IR approach. The fixture is deliberately placed before
all three groups so Group B and Group C can develop against stable test records
while Group A is still preparing the real Yelp data.

The critical path is not “Group A finishes, then B, then C.” It is:

1. confirm fixture schemas and tokenizer behavior;
2. develop the three branches in parallel;
3. integrate only their stable artifacts and public interfaces;
4. run the full dataset and finish report evidence.

## Delivery timeline: 13 October to 5 November 2026

This timeline is the source of truth for who publishes each dependency, when
parallel work may begin, and what evidence closes each phase. Dates are proposed
working deadlines ahead of the official 5 November submission deadline.

| Dates | Gate | Primary responsibility | Exit evidence |
| --- | --- | --- | --- |
| 13 Oct | Contract confirmation | One contract owner from each group | Schema examples reviewed; fixture validation passes |
| 14 Oct | Virtual-upstream sign-off | Each group signs off its expected outputs | Downstream code can run without unfinished upstream algorithms |
| 14-23 Oct | Parallel implementation | Groups A, B, and C work independently | Unit tests and fixture CLI runs pass for each branch |
| 24 Oct | Fixture integration | One rotating integrator from each group | `run-all` succeeds on `fixture.toml` with no test-only CLI path |
| 25-29 Oct | Sample and full-data runs | Component owners plus integrators | Stable artifacts, manifests, timing, and record counts |
| 30 Oct-2 Nov | Analysis and report assembly | All groups | Final plots/tables, limitations, code snippets, contribution log |
| 3-4 Nov | Release rehearsal and freeze | Entire team | Clean install succeeds; submission archive inspected |
| 5 Nov | Submission | One nominated submitter | Hardcopy and final softcopy/source submission completed |

**Parallel work starts on 14 October**, as soon as the contract PR is merged and
`python -m pytest tests/test_fixtures.py -q` passes. It does not wait for Group A
to process the real Yelp data.

### Phase 0 - confirm four contracts (13 October)

#### 1. Prepared review schema - Group A publishes

Group A defines the typed model in `src/yelptext/data/models.py`. The serialized
form is JSONL and must match the committed fixture. Minimum example:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True, slots=True)
class PreparedReview:
    review_id: str
    business_id: str
    business_name: str
    text: str
    stars: float
    date: datetime
    categories: tuple[str, ...]
```

```json
{"review_id":"r001","business_id":"b_italian","business_name":"Pasta Point","text":"Great pizza, friendly service!","stars":5.0,"date":"2021-01-15 12:00:00","categories":["Italian","Restaurants"]}
```

Decisions frozen with this schema:

- dates use an ISO-8601 string on disk and `datetime` in Python;
- categories are trimmed strings in a list and preserve dataset spelling;
- reviews without a matching business are counted, reported, and excluded;
- text remains unchanged in the prepared record; normalization happens in the
  tokenizer rather than during data preparation;
- `prepare` writes `[data].prepared_path`, and all downstream CLI commands read
  that same path instead of repeating the business-review join.

Group C reviews category/date semantics. Group B reviews whether `review_id` is
sufficient as the document identifier.

#### 2. Tokenizer contract - Group A publishes

The implementation belongs in `src/yelptext/text/tokenizer.py`; the behavior
oracle lives in `tests/fixtures/expected/tokenization.json`.

```python
from typing import Protocol

class Tokenizer(Protocol):
    def tokenize(self, text: str) -> list[str]: ...
    def fingerprint(self) -> str: ...
```

The fingerprint covers every option that changes tokens. Group B stores it with
the index and rejects incompatible query-time tokenizers. The fixture fixes the
first edge cases: case folding, contractions, emoji, hyphens, numbers, Unicode,
punctuation, and empty text.

#### 3. Index-reader contract - Group B publishes

Group B defines public records in `src/yelptext/search/models.py` and persistence
behind `src/yelptext/search/storage.py`. Ranking code must not import the index
builder's private dictionaries.

```python
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True, slots=True)
class Posting:
    review_id: str
    term_frequency: int
    positions: tuple[int, ...]

class IndexReader(Protocol):
    document_count: int
    average_document_length: float
    tokenizer_fingerprint: str
    def postings(self, term: str) -> Sequence[Posting]: ...
    def document_length(self, review_id: str) -> int: ...
```

`tests/fixtures/expected/postings.json` is the executable example. Group A
reviews tokenizer compatibility; Group C checks whether any reusable retrieval
function is useful for the application.

#### 4. Artifact schemas - each producing group publishes

Every long command writes a manifest containing at least:

```json
{
  "schema_version": "1",
  "run_id": "fixture",
  "config_path": "tests/fixtures/fixture.toml",
  "random_seed": 6122,
  "tokenizer_fingerprint": "pending-real-value",
  "record_counts": {"read": 21, "written": 20, "orphaned": 1},
  "elapsed_seconds": 0.0
}
```

The minimum tabular schemas are frozen before algorithms are implemented:

- Group A: Zipf (`term, frequency, rank`), Heaps
  (`sample_fraction, tokens, vocabulary, k, beta`), and tokenizer comparison;
- Group B: ranked results (`query_id, ranker, rank, review_id, score`) and query
  comparison summary;
- Group C: sentiment trend (`period, sector, review_count, mean_compound`), PMI
  (`period, target, term, cooccurrence, pmi, rank`), and application predictions
  (`review_id, sentence, predicted_label, cue`).

Manifests go to `artifacts/manifests/`; tables, figures, indexes, and search
results go to their existing `artifacts/` subdirectories.

### Phase 1 - sign off virtual upstreams (14 October)

Do not write fake algorithms under `src/` and do not add a `--test-data` branch.
The expected fixture files are the virtual upstream: they represent what an
unfinished producer promises to emit.

| Virtual provider | Owner | Location | Unblocks |
| --- | --- | --- | --- |
| Prepared reviews | Group A | `tests/fixtures/expected/prepared_reviews.jsonl` | Groups B and C data ingestion |
| Token outputs | Group A | `tests/fixtures/expected/tokenization.json` | Corpus analysis, indexing, query processing |
| Postings and rank scores | Group B | `tests/fixtures/expected/postings.json`, `ranking_cases.json` | Ranking and search orchestration |
| Sentiment, PMI, comparison labels | Group C | `tests/fixtures/expected/*_cases.json` | Trend/application evaluation |

Group A also publishes one real streaming adapter in
`src/yelptext/data/reader.py` by the end of this phase. Groups B and C use the
same call with either the virtual or real prepared file:

```python
from pathlib import Path
from yelptext.data.reader import iter_prepared_reviews

reviews = iter_prepared_reviews(
    Path("tests/fixtures/expected/prepared_reviews.jsonl")
)
```

This small adapter is the hand-off boundary: downstream modules consume an
iterator of `PreparedReview` objects and do not know whether the JSONL was
hand-authored, produced from a sample, or produced from the full dataset.

If an in-memory object is required before its real producer exists, its minimal
test double goes in `tests/fakes/` and is owned by the group that owns the public
interface, for example `tests/fakes/index_reader.py`. Production code must never
import `tests.fakes`; tests inject the fake through a function argument or
constructor.

The virtual-upstream gate is:

```powershell
python -m pytest tests/test_fixtures.py -q
python -m yelptext prepare --config tests/fixtures/fixture.toml
python -m yelptext search "great pizza" --config tests/fixtures/fixture.toml
```

At this stage the CLI may only dispatch to a stub handler, but parsing, paths,
schemas, and expected files must already agree.

### Phase 2 - three groups implement in parallel (14-23 October)

#### Group A - data, tokenizer, Zipf, and Heaps

Inputs:

- `tests/fixtures/raw/*.jsonl` for daily tests;
- Yelp files under `data/raw/` for sample/full runs;
- `tests/fixtures/expected/prepared_reviews.jsonl` and `tokenization.json` as
  exact acceptance oracles.

Daily commands:

```powershell
python -m pytest tests/test_tokenizer.py tests/test_fixtures.py -q
python -m yelptext prepare --config tests/fixtures/fixture.toml
python -m yelptext analyze zipf --config tests/fixtures/fixture.toml
python -m yelptext analyze heaps --config tests/fixtures/fixture.toml
python -m yelptext analyze tokenizers --config tests/fixtures/fixture.toml
```

Exit result: prepared JSONL plus manifest; tokenizer contract and edge-case tests;
Zipf plot/table; Heaps fit/prediction table; tokenizer quantitative and
qualitative comparison.

#### Group B - index, ranking, and query analysis

Inputs:

- Group A's prepared-review schema and tokenizer protocol;
- `prepared_reviews.jsonl` while Group A's real pipeline is unfinished;
- `postings.json` and `ranking_cases.json` for hand-calculated assertions;
- at least five queries in `configs/queries.toml`.

Before the fixture integration gate, Group B's domain tests read the expected
prepared JSONL through `iter_prepared_reviews(...)`; `index build` must not call
the preparation algorithm internally. At integration time the configured path
is switched to Group A's generated artifact without changing indexing code.

Daily commands:

```powershell
python -m pytest tests/test_index.py tests/test_tfidf.py tests/test_bm25.py -q
python -m yelptext index build --config tests/fixtures/fixture.toml
python -m yelptext search "great pizza" --ranker tfidf --config tests/fixtures/fixture.toml
python -m yelptext search "great pizza" --ranker bm25 --config tests/fixtures/fixture.toml
```

Exit result: persisted index plus metadata/fingerprint; exact fixture scores;
ranked results for five or more queries on both rankers; comparison table and
interpretation notes.

#### Group C - sentiment, PMI drift, and application

Inputs:

- prepared reviews with `date`, `categories`, and unchanged `text`;
- `sentiment_cases.json`, `pmi_cases.json`, and `comparison_cases.json`;
- Group A's tokenizer only where token-based PMI/application logic requires it.

Group C follows the same rule: domain tests consume the expected prepared JSONL
directly, while the integrated CLI consumes Group A's generated file. Trend and
application code must not own a second business-review join.

Daily commands:

```powershell
python -m pytest tests/test_pmi.py tests/test_fixtures.py -q
python -m yelptext trend sentiment --config tests/fixtures/fixture.toml
python -m yelptext trend pmi --term service --config tests/fixtures/fixture.toml
python -m yelptext app comparisons --config tests/fixtures/fixture.toml
```

Exit result: sentiment-by-sector/time table and figure; yearly top-N PMI table
and drift figure; comparison predictions and evaluation; report notes covering
lexicon and rule-based limitations.

### Phase 3 - fixture integration gate (24 October)

One member from each group forms the temporary integration group. They wire
`commands/run_all.py`; component owners remain responsible for fixing failures
inside their own domain.

```powershell
python -m pytest -q
python -m yelptext run-all --config tests/fixtures/fixture.toml
```

The gate closes only when:

- all commands use the same prepared-review and tokenizer contracts;
- expected fixture outputs match without a test-specific production branch;
- every artifact has a manifest and stable schema;
- a second fixture run produces the same substantive outputs;
- notebooks can read artifacts without reimplementing algorithms.

### Phase 4 - sample, full data, and performance (25-29 October)

Run the sample first; do not debug schema or memory problems during the full run.

```powershell
python -m yelptext run-all --config configs/sample.toml
python -m yelptext run-all --config configs/full.toml
```

After the sample run, each group signs off record counts, runtime/memory notes,
empty-period handling, and figure/table readability. The full run starts only
after those checks. A failed full run resumes from persisted upstream artifacts
rather than restarting unrelated completed stages.

Expected result by 29 October: one complete, reproducible artifact set; at least
five search-query comparisons; report-ready Zipf/Heaps, sentiment, and PMI
figures; application evaluation; and manifests that tie every result to its
configuration and input counts.

### Phase 5 - report, rehearsal, and freeze (30 October-5 November)

- 30 Oct-2 Nov: each pair writes its method, result interpretation, assumptions,
  and limitations directly from the frozen artifacts.
- 3 Nov: a clean environment installs dependencies and reproduces the fixture;
  notebooks execute in order without hidden state.
- 4 Nov: freeze code, inspect `Readme.txt`, archive only own source, exclude Yelp
  data/libraries, proofread printed figures, and complete the contribution table.
- 5 Nov: one nominated member submits the matching hardcopy/softcopy report and
  source archive according to the assignment instructions.

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
