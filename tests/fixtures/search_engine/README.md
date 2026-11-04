# Search algebra fixture

This four-document corpus is synthetic input to the **real** index and rankers.
The search-owned fake upstream implements the shared reader/tokenizer API, with
an explicit `fixture:` fingerprint. It does not define production token policy.

With punctuation filtered:

| Document | Terms | Length |
| --- | --- | ---: |
| d1 | apple apple banana | 3 |
| d2 | banana carrot | 2 |
| d3 | apple carrot carrot carrot | 4 |
| d4 | (empty) | 0 |

Thus N=4, total terms=9, average length=9/4, and all three terms have DF=2.
The empty document is retained in N. Metadata includes Unicode and nulls.

For query `apple banana`, TF-IDF uses `idf = ln(5/3)+1` for every term;
this common factor cancels from cosine. Let `a=1+ln(2)`, `c=1+ln(3)`:

- d1: `(a+1) / sqrt(2*(a*a+1))`
- d2: `1/2`
- d3: `1 / sqrt(2*(1+c*c))`

With BM25 k1=3/2 and b=3/4, every query term has IDF=ln(2). Substituting the
document lengths into the saturation denominator gives:

- d1: `ln(2) * (40/31 + 20/23)`
- d2: `ln(2) * (20/19)`
- d3: `ln(2) * (20/27)`

These independently derived expectations are written directly in the tests.
Additional tests use isolated corpora for ties, nonuniform IDF, and failures.
The five queries in `queries.toml` are deterministic smoke cases; they do not
replace the assignment's later real-data query analysis.

`fixture.toml` selects the search-owned fake upstream and needs no NLTK data.
`real.toml` uses the same small corpus with the real shared reader and tokenizer;
it requires the project dependencies and NLTK `stopwords` data. Its index is
written separately to `artifacts/indexes/fixture-real`. The two modes have
different fingerprints, so their indexes cannot be exchanged silently.

