"""Public facilities for persisted review indexes and lexical retrieval.

Both fixture and real runs call this same interface; only the upstream reader
and tokenizer are selected by command orchestration.
"""

from yelptext.implementation.search_engine.index import (
    SearchIndex,
    SearchIndexError,
    build_index,
    load_index,
)
from yelptext.implementation.search_engine.ranking import SearchResult, search
from yelptext.implementation.search_engine.experiments import run_experiment
from yelptext.implementation.search_engine.compact import (
    CompactSearchIndex, build_compact_index, load_compact_index,
)
from yelptext.implementation.search_engine.parallel_index import build_index_mapreduce

__all__ = [
    "SearchIndex",
    "SearchIndexError",
    "SearchResult",
    "build_index",
    "load_index",
    "search",
    "run_experiment",
    "CompactSearchIndex",
    "build_compact_index",
    "load_compact_index",
    "build_index_mapreduce",
]
