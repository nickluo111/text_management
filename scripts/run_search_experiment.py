"""Build or verify a search index, then run both rankers outside notebooks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter
from typing import Any, Mapping

from yelptext.interface.data_corpus_analysis import (
    create_review_reader,
    create_tokenizer_pipeline,
)
from yelptext.interface.search_engine import (
    build_index,
    build_index_mapreduce,
    load_index,
    run_experiment,
)
from yelptext.runtime import load_config


ROOT = Path(__file__).resolve().parents[1]


def _path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _section(config: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = config.get(key, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"Configuration [{key}] must be a table")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "size_bytes": stat.st_size,
        "sha256": _sha256(path),
    }


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _queries(value: object) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) < 5
        or any(not isinstance(query, str) or not query.strip() for query in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError(
            "[analysis.search].queries must contain at least five unique "
            "nonblank strings"
        )
    return value


def run(config_path: Path, *, build_only: bool = False) -> dict[str, Any]:
    config_path = _path(config_path)
    config = load_config(config_path)
    if _section(config, "runtime").get("mode") != "real":
        raise ValueError("Search experiments require [runtime].mode = 'real'")

    data = _section(config, "data")
    index_settings = _section(config, "index")
    search_settings = _section(config, "search")
    analysis = _section(_section(config, "analysis"), "search")
    tokenizer_settings = _section(config, "tokenizer")

    prepared_path = _path(data["prepared_path"])
    index_dir = _path(index_settings["output_dir"])
    index_path = index_dir / "index.sqlite3"
    workers = index_settings.get("workers", 1)
    output_dir = _path(analysis["output_dir"])
    manifest_path = _path(analysis.get("manifest_path", output_dir / "run_manifest.json"))
    expected_documents = analysis.get("expected_documents")
    repeats = analysis.get("repeats", 1)
    top_k = search_settings.get("top_k", 10)
    bm25 = _section(search_settings, "bm25")
    k1, b = bm25.get("k1", 1.5), bm25.get("b", 0.75)

    if index_settings.get("storage", "sqlite") != "sqlite":
        raise ValueError("The full experiment script uses the disk-backed SQLite index")
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError("[index].workers must be an integer between 1 and 8")
    if type(expected_documents) is not int or expected_documents <= 0:
        raise ValueError("[analysis.search].expected_documents must be positive")
    if type(repeats) is not int or repeats < 1:
        raise ValueError("[analysis.search].repeats must be positive")
    if not prepared_path.is_file():
        raise FileNotFoundError(prepared_path)

    queries = _queries(analysis.get("queries"))
    source = _file_record(prepared_path)
    tokenizer = create_tokenizer_pipeline(
        skip_types=tokenizer_settings.get("skip_types", ["punctuation"]),
        enable_pos=tokenizer_settings.get("enable_pos", False),
    )

    manifest: dict[str, Any] = {
        "status": "STARTED",
        "config": str(config_path),
        "prepared_input": source,
        "index_path": str(index_path),
        "output_dir": str(output_dir),
        "expected_documents": expected_documents,
        "workers": workers,
        "queries": queries,
    }

    if index_path.exists():
        if not manifest_path.is_file():
            raise ValueError("Existing index has no provenance manifest; use a fresh output directory")
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous.get("prepared_input", {}).get("sha256") != source["sha256"]:
            raise ValueError("Existing index provenance mismatch for prepared_input")
        manifest["build_reused"] = True
        build_seconds = previous.get("build_seconds")
    else:
        print(f"Building index from {prepared_path}", flush=True)
        started = perf_counter()
        if workers == 1:
            stats = build_index(
                create_review_reader(prepared_path),
                tokenizer,
                index_dir,
                progress=lambda count: print(f"Indexed {count:,} reviews", flush=True),
            )
        else:
            stats = build_index_mapreduce(
                prepared_path,
                index_dir,
                workers=workers,
                skip_types=tokenizer_settings.get("skip_types", ["punctuation"]),
                enable_pos=tokenizer_settings.get("enable_pos", False),
                progress=lambda event: print(
                    "MapReduce: " + json.dumps(event, ensure_ascii=False), flush=True
                ),
            )
        build_seconds = perf_counter() - started
        manifest.update({
            "status": "INDEX_READY",
            "build_reused": False,
            "build_seconds": build_seconds,
            "index_stats": stats,
        })
        _write_json_atomic(manifest_path, manifest)

    with load_index(index_dir, tokenizer) as index:
        stats = index.stats()
        if stats["document_count"] != expected_documents:
            raise ValueError(
                f"Expected {expected_documents:,} documents, indexed {stats['document_count']:,}"
            )
        manifest["index_stats"] = stats
        manifest["build_seconds"] = build_seconds
        if build_only:
            manifest["status"] = "INDEX_READY"
            _write_json_atomic(manifest_path, manifest)
            return manifest

        print(f"Running {len(queries)} queries with TF-IDF and BM25", flush=True)
        started = perf_counter()
        report = run_experiment(
            index,
            queries,
            output_dir,
            top_k=top_k,
            k1=k1,
            b=b,
            repeats=repeats,
        )
        experiment_seconds = perf_counter() - started

    manifest.update({
        "status": "COMPLETED",
        "experiment_seconds": experiment_seconds,
        "ranked_queries": len(report["queries"]),
    })
    _write_json_atomic(manifest_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/sample.toml"))
    parser.add_argument("--build-only", action="store_true")
    args = parser.parse_args()
    result = run(args.config, build_only=args.build_only)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
