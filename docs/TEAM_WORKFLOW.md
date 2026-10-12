# Six-person team workflow

## Working model

Use three pairs with shared interfaces, not six isolated personal tasks and not
one long relay. Each pair owns a coherent assignment area; both members should
be able to explain and maintain the whole area.

- **Group A - data and corpus analysis:** preparation, tokenizer, Zipf, Heaps,
  and tokenizer comparison (§3.1-§3.2).
- **Group B - search:** index, TF-IDF, BM25, queries, and retrieval analysis
  (§3.3).
- **Group C - trends and application:** sentiment, PMI drift, and the small
  NLP/IR application (§3.4-§3.5).

The assignment references in the visual use `section + bullet position`, because
the bullets inside the official brief are not individually numbered.

## Dependency overview

![Dependency map for the three parallel responsibility groups](assets/team-workflow-dependencies.png)

The fixture and public interfaces are the parallel starting point. Group B and
Group C should not wait for Group A to finish processing the real Yelp files.

## Confirm before the groups implement

Only shared boundaries need to be agreed first. Internal helper functions remain
under the owning pair's control.

### Prepared review schema

Group A owns the model in `src/yelptext/data/models.py` and the streaming reader
in `src/yelptext/data/reader.py`.

```python
@dataclass(frozen=True, slots=True)
class PreparedReview:
    review_id: str
    business_id: str
    business_name: str
    text: str
    stars: float
    date: datetime
    categories: tuple[str, ...]

def iter_prepared_reviews(path: Path) -> Iterator[PreparedReview]: ...
```

Serialized JSONL example:

```json
{"review_id":"r001","business_id":"b_italian","business_name":"Pasta Point","text":"Great pizza, friendly service!","stars":5.0,"date":"2021-01-15 12:00:00","categories":["Italian","Restaurants"]}
```

The shared decisions are:

- raw review text is preserved;
- dates use ISO-8601 on disk and `datetime` in Python;
- categories are trimmed but retain dataset spelling;
- an orphan review is counted and excluded;
- `prepare` writes `[data].prepared_path`; all downstream CLI commands read the
  same path and never repeat the business-review join.

### Text and index interfaces

Group A owns `Tokenizer`; Group B owns `IndexReader`. Consumers depend on these
protocols rather than concrete private structures.

```python
class Tokenizer(Protocol):
    def tokenize(self, text: str) -> list[str]: ...
    def fingerprint(self) -> str: ...

class IndexReader(Protocol):
    document_count: int
    average_document_length: float
    tokenizer_fingerprint: str
    def postings(self, term: str) -> Sequence[Posting]: ...
    def document_length(self, review_id: str) -> int: ...
```

The tokenizer fingerprint is stored with the index. A query cannot silently use
a tokenizer configuration different from the one used to build that index.

### Output contracts

Agree on column names before producing report artifacts:

- Zipf: `term, frequency, rank`;
- Heaps: `sample_fraction, tokens, vocabulary, k, beta`;
- search: `query_id, ranker, rank, review_id, score`;
- sentiment: `period, sector, review_count, mean_compound`;
- PMI: `period, target, term, cooccurrence, pmi, rank`;
- application: `review_id, sentence, predicted_label, cue`.

Every long-running command also writes a manifest with configuration, seed,
tokenizer fingerprint, source metadata, record counts, and elapsed time.

## What the fixture files mean

There is no single `expected/` directory because not every fixture has a known
correct answer. The files are separated by purpose:

| Directory | Meaning | May be treated as a correct answer? |
| --- | --- | --- |
| `tests/fixtures/raw/` | Invented Yelp-like input records | No; they are input only |
| `tests/fixtures/handoffs/` | Schema-valid output supplied by an unfinished upstream module | No; it is a virtual provider |
| `tests/fixtures/oracles/` | Small, hand-calculable results for fixed mathematics/invariants | Yes |
| `tests/fixtures/cases/` | Required edge cases or manually labeled examples | Only for the stated case/label |

For example, `handoffs/prepared_reviews.jsonl` does not claim to predict the
real preparation output distribution. It simply lets Groups B and C consume the
agreed `PreparedReview` schema. In contrast, BM25 scores in
`oracles/ranking_cases.json` are true expected values because the corpus,
formula, and parameters are fully specified and can be calculated by hand.

Tokenizer cases cover assignment-mandated behavior such as emoji, contractions,
and hyphenated words. They do not prove that the tokenizer is suitable for the
real Yelp corpus; that requires real-data inspection.

## Replacing virtual providers with real providers

The consumer function must not change when the real upstream becomes available.
Only the provider or configured path changes.

| Boundary | Virtual provider and owner | Real provider and owner | Consumer change |
| --- | --- | --- | --- |
| Prepared reviews | Group A: `tests/fixtures/handoffs/prepared_reviews.jsonl` | Group A: `data.prepare.prepare_reviews(...)` writes `[data].prepared_path` | Path changes; reader and algorithms do not |
| Tokenizer | Group A: first protocol-compatible `RegexTokenizer` configuration | Group A: same class after real-sample refinement | Injected config/fingerprint changes; rebuild the index |
| Index reader | Group B: optional `tests/fakes/index_reader.py` backed by oracle postings | Group B: `search.storage.load_index(...)` | Concrete provider changes; ranker functions do not |
| Trend/application labels | Group C: files under `tests/fixtures/cases/` | Group C: predictions over prepared Yelp reviews | Data changes; scoring/evaluation interfaces do not |

Prepared-review example:

```python
# During independent development
path = Path("tests/fixtures/handoffs/prepared_reviews.jsonl")

# During integrated sample/full runs
path = Path(config["data"]["prepared_path"])

reviews = iter_prepared_reviews(path)
results = build_index(reviews, tokenizer)
```

No production module may import `tests.fakes`. A fake is injected through a
protocol argument in tests. Do not add a second CLI or a `--test-data` code path.

## Group A deliverables: data and corpus analysis

| File | Required public content |
| --- | --- |
| `data/models.py` | `Business`, `Review`, `PreparedReview`, preparation summary records |
| `data/reader.py` | streaming `iter_jsonl(...)`, `iter_businesses(...)`, `iter_reviews(...)`, `iter_prepared_reviews(...)` |
| `data/sampler.py` | deterministic sampling using the configured fraction and seed |
| `data/prepare.py` | business lookup/join and `prepare_reviews(...)` writing `[data].prepared_path` |
| `text/normalization.py` | explicit normalization policy; no hidden index/query differences |
| `text/tokenizer.py` | `RegexTokenizer.tokenize(...)` and stable fingerprint |
| `text/baselines.py` | whitespace and WordPunct adapters used only for comparison |
| `analysis/zipf.py` | term-frequency/rank table and Zipf figure data |
| `analysis/heaps.py` | vocabulary growth points and fitted `k`, `beta` |
| `analysis/tokenizer_comparison.py` | vocabulary-size and qualitative comparison table |
| `commands/prepare.py`, `commands/analyze.py` | real handlers calling the functions above |

Fixture-first commands:

```powershell
python -m pytest tests/test_tokenizer.py tests/test_fixtures.py -q
python -m yelptext prepare --config tests/fixtures/fixture.toml
python -m yelptext analyze zipf --config tests/fixtures/fixture.toml
```

`00_data_check.ipynb` should show counts, orphan handling, category/date coverage,
and sampling reproducibility. `01_corpus_analysis.ipynb` should show the Zipf
log-log plot, Heaps observations and fitted curve, tokenizer vocabulary sizes,
and representative tokenization examples. The report needs the sample
definition, regex decisions, fitted parameters, findings, and limitations.

## Group B deliverables: search

| File | Required public content |
| --- | --- |
| `search/models.py` | `Posting`, `IndexMetadata`, `RankedResult`, `IndexReader` protocol |
| `search/index.py` | `build_index(reviews, tokenizer)` with postings, lengths, DF, and global `avgdl` |
| `search/storage.py` | `save_index(...)` and `load_index(...)` with tokenizer metadata |
| `search/rankers/tfidf.py` | from-scratch TF-IDF cosine scoring |
| `search/rankers/bm25.py` | from-scratch BM25 using configurable `k1`, `b` |
| `search/query.py` | shared query tokenization and `search(...)` orchestration |
| `search/evaluation.py` | run and compare at least five queries on both rankers |
| `commands/index.py`, `commands/search.py` | real build/search/batch-evaluation handlers |

Fixture-first commands:

```powershell
python -m pytest tests/test_index.py tests/test_tfidf.py tests/test_bm25.py -q
python -m yelptext index build --config tests/fixtures/fixture.toml
python -m yelptext search "great pizza" --ranker bm25 --config tests/fixtures/fixture.toml
```

`02_search_evaluation.ipynb` should show index statistics, formula/parameter
choices, and side-by-side top results for at least five diverse real queries.
Useful report evidence is where TF-IDF and BM25 agree or diverge and why; a
decorative score chart is not required.

## Group C deliverables: trends and application

| File | Required public content |
| --- | --- |
| `trends/sentiment.py` | VADER scoring with raw component/compound values |
| `trends/aggregation.py` | category matching and year/season aggregation |
| `trends/cooccurrence.py` | documented co-occurrence context/counting |
| `trends/pmi.py` | PMI calculation, filtering, top-N extraction, temporal comparison |
| `applications/comparison_detector.py` | comparison detection and evaluation records |
| `commands/trend.py`, `commands/application.py` | real sentiment/PMI/application handlers |

Fixture-first commands:

```powershell
python -m pytest tests/test_pmi.py tests/test_fixtures.py -q
python -m yelptext trend sentiment --config tests/fixtures/fixture.toml
python -m yelptext trend pmi --term service --config tests/fixtures/fixture.toml
python -m yelptext app comparisons --config tests/fixtures/fixture.toml
```

`03_trend_analysis.ipynb` should show sector sentiment over time with review
counts and top-N PMI associations across periods. `04_application.ipynb` should
show evaluation metrics plus representative successes and errors. The report
must discuss lexicon limitations, PMI filtering/context choices, observed drift,
and application failure modes.

## What can be fixed with synthetic data and what needs real data

| Component | Synthetic data can establish | Real data is required for |
| --- | --- | --- |
| Streaming/join | schema, orphan behavior, deterministic sampling | scale, malformed-record frequency, memory/runtime |
| Tokenizer | mandatory emoji/contraction/hyphen behavior and index/query consistency | discovering frequent noise, deciding useful regex/normalization, vocabulary impact |
| Zipf/Heaps | correct counting, sampling, fitting code | actual plots, fitted `k`/`beta`, interpretation |
| Inverted index | postings, DF, positions, lengths, `avgdl` invariants | size, persistence/runtime, real vocabulary distribution |
| TF-IDF | exact scores for the chosen TF/IDF definition | usefulness on diverse Yelp queries |
| BM25 | exact formula for any supplied `k1`/`b` | selecting/reporting production parameters and result quality |
| Sentiment | wrapper behavior and aggregation shape | real sector/year trends and limitations |
| PMI | exact counts/PMI for a declared context and log base | target term, minimum count, top-N stability, semantic drift |
| Application | evaluation code and a few labeled controls | rule/threshold refinement and credible error analysis |

The team should never tune an empirical choice until the synthetic fixture
passes. Conversely, it should never claim a synthetic result answers an
empirical assignment question. Tokenizer refinement, query selection, category
matching, PMI thresholds, and application rules must be checked on a documented
real sample before the full run.

## Integration and review

Integration has only three gates:

1. every group's unit tests pass against its fixture/oracle/cases;
2. `yelptext run-all --config tests/fixtures/fixture.toml` exercises the real
   handlers and artifact schemas;
3. the same code runs with `configs/sample.toml` and then `configs/full.toml` by
   changing configuration and rebuilding data-dependent artifacts, not by
   changing function signatures.

Use circular review: Group A reviews Group B's formulas and hand calculations;
Group B reviews Group C's PMI/evaluation; Group C reviews Group A's data joins,
sampling, and tokenizer evidence. One temporary integrator from each group owns
`commands/run_all.py` and the clean-environment reproduction.

## Git and definition of done

- Use short area branches and small pull requests.
- A shared-interface change requires one reviewer from another group.
- Do not commit Yelp data, generated large artifacts, secrets, or unnecessary
  notebook output.
- A work item is done when it has reusable `src/yelptext` code, focused tests,
  a wired CLI handler, deterministic artifact/manifest output, notebook/report
  evidence, and both pair members can explain it.
- Record each member's implementation, review, experiment, and writing evidence
  in the final contribution table required by §2 bullet 2.
