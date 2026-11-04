AI6122 Yelp Text Analysis
=========================

OVERVIEW
--------
This submission implements the shared data reader and tokenizer, Zipf and
Heaps analyses, a persistent inverted index with TF-IDF cosine and BM25,
sector sentiment trends, and PMI co-occurrence drift. The small comparison
application is completed through the same package separately.

The Yelp dataset, generated artifacts, virtual environment, caches, and
third-party libraries are not included in the source archive.

PYTHON AND INSTALLATION
-----------------------
CPython 3.12.4 is required. From the extracted source directory:

    py -3.12 -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    python -m pip install -e . --no-deps
    python -m nltk.downloader stopwords vader_lexicon

Experimental POS tagging additionally needs `averaged_perceptron_tagger`.

Pinned third-party libraries and official sites:

* NumPy: https://numpy.org/
* SciPy: https://scipy.org/
* pandas: https://pandas.pydata.org/
* Matplotlib: https://matplotlib.org/
* seaborn: https://seaborn.pydata.org/
* NLTK: https://www.nltk.org/
* regex: https://pypi.org/project/regex/
* tqdm: https://tqdm.github.io/
* JupyterLab: https://jupyter.org/
* pytest: https://pytest.org/

DATA
----
Download the Yelp Open Dataset from https://www.yelp.com/dataset and place
`yelp_academic_dataset_business.json` and
`yelp_academic_dataset_review.json` under `data/raw/`. See
`docs/DATA_ACCESS.md` and `docs/yelp-review.schema.json`.

PREPARATION
-----------
    python -m yelptext prepare --config configs/full.toml
    python -m yelptext sample --config configs/full.toml --size 50000 --seed 42
    python -m yelptext vocab build --config configs/full.toml

SECTION 3.1: DATASET ANALYSIS
-----------------------------
    python -m yelptext analyze zipf --config configs/full.toml
    python -m yelptext analyze heaps --config configs/full.toml
    python -m yelptext analyze tokenizers --config configs/full.toml

Validated results include 734,871,222 lexical tokens, 685,120 types, a
ranks-1--1,000 Zipf slope of -1.041, and a Heaps exponent of 0.533.
Notebooks 01--03 display the generated results.

SECTION 3.2: SEARCH ENGINE
--------------------------
    python scripts/run_search_experiment.py --config configs/sample.toml
    python -m yelptext search "good service" --ranker tfidf --config configs/sample.toml
    python -m yelptext search "good service" --ranker bm25 --config configs/sample.toml

The validated sample index contains 50,000 reviews, 56,040 terms, and average
document length 104.95468. The six experiment queries are embedded in
`configs/sample.toml`. Notebook 04 presents both rankers and sensitivity data.

SECTION 3.3: TREND ANALYSIS
---------------------------
    python -m yelptext trend sentiment --config configs/full.toml
    python -m yelptext trend pmi --config configs/full.toml

Italian Restaurants requires both `Italian` and `Restaurants`; Fast Food
requires `Fast Food`. PMI defaults to target `service`, radius 5, annual
periods, Top 20, minimum count 10, and relative support floor 0.001.
Notebook 05 presents the resulting trend tables and figures.

TESTS
-----
    python -m pytest -q --basetemp artifacts/pytest-tmp

The validated integrated suite contains 118 tests covering formulas,
persistence, failures, configuration, and CLI integration.

DIRECTORY GUIDE
---------------
* `src/yelptext/implementation/`: algorithms and persistence.
* `src/yelptext/interface/`: stable public Python interfaces.
* `src/yelptext/command/`: configuration-aware orchestration.
* `src/yelptext/cli/`: command registration and arguments.
* `configs/`: full and sample configurations.
* `notebooks/`: presentation notebooks 01--06.
* `tests/`: unit and integration tests.
* `scripts/`: experiment and submission helpers.

CONTRIBUTIONS
-------------
Member names and individual responsibilities must match the single
contribution table in the submitted report. Group A covers data/tokenization
and corpus laws; Group B covers indexing and ranking; Group C covers sentiment,
PMI, and the application; integration and final validation are shared.
