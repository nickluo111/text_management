"""Build and query the real search engine using a selected upstream interface."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from yelptext.interface import search_engine
from yelptext.runtime import load_config, load_interface_module, runtime_mode


def _section(config: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = config.get(key, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"Configuration [{key}] must be a table")
    return value


def _path(section: Mapping[str, Any], key: str, label: str) -> Path:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Configuration must define [{label}].{key}")
    return Path(value)


def _upstream_and_tokenizer(config: Mapping[str, Any]):
    upstream = load_interface_module(
        runtime_mode(config), "data_corpus_analysis", consumer="search_engine"
    )
    settings = _section(config, "tokenizer")
    # These existing config keys describe the fixed, shared canonical policy.
    # The public factory has no switches for changing that policy.
    for key in (
        "lowercase", "preserve_contractions", "preserve_emojis", "split_hyphenated_words"
    ):
        if key in settings and settings[key] is not True:
            raise ValueError(f"[tokenizer].{key} must be true under the shared token policy")
    skips = settings.get("skip_types", ["punctuation"])
    enable_pos = settings.get("enable_pos", False)
    if not isinstance(skips, list) or any(not isinstance(item, str) for item in skips):
        raise ValueError("[tokenizer].skip_types must be an array of strings")
    if not isinstance(enable_pos, bool):
        raise ValueError("[tokenizer].enable_pos must be a boolean")
    tokenizer = upstream.create_tokenizer_pipeline(skip_types=skips, enable_pos=enable_pos)
    return upstream, tokenizer


def run_build_index(args: argparse.Namespace) -> None:
    """Stream prepared reviews into a new index; existing indexes are retained."""
    config = load_config(args.config)
    prepared_path = _path(_section(config, "data"), "prepared_path", "data")
    output_dir = args.output_dir
    if output_dir is None:
        output_dir = _path(_section(config, "index"), "output_dir", "index")
    upstream, tokenizer = _upstream_and_tokenizer(config)
    storage = _section(config, "index").get("storage", "sqlite")
    reader = upstream.create_review_reader(prepared_path)
    if storage == "compact":
        stats = search_engine.build_compact_index(
            reader, tokenizer, output_dir,
            max_memory_bytes=_section(config, "performance").get("max_memory_bytes"),
        )
        index_filename = "compact.sqlite3"
    elif storage == "sqlite":
        stats = search_engine.build_index(reader, tokenizer, output_dir)
        index_filename = "index.sqlite3"
    else:
        raise ValueError("[index].storage must be 'sqlite' or 'compact'")
    print(json.dumps({
        "status": "COMPLETED",
        "index_path": str(Path(output_dir) / index_filename),
        "stats": stats,
    }, ensure_ascii=False, indent=2, allow_nan=False))


def _write_output(path: Path, content: str, protected: set[Path]) -> None:
    if path.resolve() in protected:
        raise ValueError("Search output must not overwrite an index, input, or configuration")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content + "\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run_search(args: argparse.Namespace) -> None:
    """Load one persisted index for a single query or a batch of queries."""
    config = load_config(args.config)
    settings = _section(config, "search")
    bm25 = _section(settings, "bm25")
    top_k = args.top_k if args.top_k is not None else settings.get("top_k", 10)
    k1, b = bm25.get("k1", 1.5), bm25.get("b", 0.75)
    index_dir = args.index_dir
    if index_dir is None:
        index_dir = _path(_section(config, "index"), "output_dir", "index")
    if args.queries is not None:
        queries = load_config(args.queries).get("queries")
        if (
            not isinstance(queries, list) or not queries
            or any(not isinstance(query, str) for query in queries)
        ):
            raise ValueError("Query TOML must contain a non-empty array of strings: queries")
    else:
        queries = [args.query]

    _, tokenizer = _upstream_and_tokenizer(config)
    storage = _section(config, "index").get("storage", "sqlite")
    if storage not in {"sqlite", "compact"}:
        raise ValueError("[index].storage must be 'sqlite' or 'compact'")
    loader = search_engine.load_compact_index if storage == "compact" else search_engine.load_index
    with loader(index_dir, tokenizer) as index:
        outputs = []
        for query in queries:
            results = search_engine.search(
                index, query, ranker=args.ranker, top_k=top_k, k1=k1, b=b
            )
            payload = {
                "query": query, "ranker": args.ranker, "top_k": top_k,
                "results": [
                    {"rank": rank, **asdict(result)}
                    for rank, result in enumerate(results, 1)
                ],
            }
            if args.ranker == "bm25":
                payload["parameters"] = {"k1": k1, "b": b}
            outputs.append(payload)

    payload = outputs[0] if args.queries is None else {
        "ranker": args.ranker, "top_k": top_k, "queries": outputs,
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output is not None:
        protected = {Path(args.config).resolve()}
        protected.update((Path(index_dir) / name).resolve() for name in (
            "index.sqlite3", "compact.sqlite3", "manifest.json", "lengths.npy", "norms.npy",
        ))
        if args.queries is not None:
            protected.add(Path(args.queries).resolve())
        data = _section(config, "data")
        for key in ("prepared_path", "review_path", "business_path", "sample_path"):
            if isinstance(data.get(key), str):
                protected.add(Path(data[key]).resolve())
        _write_output(args.output, content, protected)
    print(content)
