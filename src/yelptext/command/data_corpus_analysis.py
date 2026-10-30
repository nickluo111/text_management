"""Command orchestration for data preparation and corpus analysis."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from yelptext.interface.data_corpus_analysis import (
    build_vocabulary,
    prepare_reviews,
    sample_reviews,
)
from yelptext.runtime.config import load_config


def _configured_path(
    args_value: Path | None,
    data: Mapping[str, object],
    key: str,
) -> Path:
    if args_value is not None:
        return args_value
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Configuration must define [data].{key}")
    return Path(value)


def run_prepare(args: argparse.Namespace) -> None:
    """Prepare canonical review JSONL using CLI overrides or config paths."""

    config = load_config(args.config)
    data = config.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("Configuration must define [data]")
    report = prepare_reviews(
        _configured_path(args.reviews, data, "review_path"),
        _configured_path(args.businesses, data, "business_path"),
        _configured_path(args.output, data, "prepared_path"),
        limit=args.limit,
        long_text_threshold=args.long_text_threshold,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def run_build_vocabulary(args: argparse.Namespace) -> None:
    """Build the shared vocabulary only when explicitly requested."""

    config = load_config(args.config)
    data = config.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("Configuration must define [data]")
    tokenizer = config.get("tokenizer")
    if not isinstance(tokenizer, Mapping):
        raise ValueError("Configuration must define [tokenizer]")

    output_value = args.output
    if output_value is None:
        configured = tokenizer.get("vocabulary_path")
        if not isinstance(configured, str) or not configured:
            raise ValueError("Configuration must define [tokenizer].vocabulary_path")
        output_value = Path(configured)

    def report_progress(phase: str, documents: int, tokens: int) -> None:
        print(
            f"[{phase}] documents={documents:,} tokens={tokens:,}",
            file=sys.stderr,
            flush=True,
        )

    report = build_vocabulary(
        _configured_path(args.reviews, data, "review_path"),
        output_value,
        buffer_unique_terms=args.buffer_unique_terms,
        progress=report_progress,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def run_sample(args: argparse.Namespace) -> None:
    """Create a reusable schema-preserving review sample."""

    config = load_config(args.config)
    data = config.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("Configuration must define [data]")

    configured_seed = data.get("random_seed")
    seed = args.seed if args.seed is not None else configured_seed
    if not isinstance(seed, int):
        raise ValueError("Sampling requires an integer --seed or [data].random_seed")

    report = sample_reviews(
        _configured_path(args.input, data, "prepared_path"),
        _configured_path(args.output, data, "sample_path"),
        sample_size=args.size,
        seed=seed,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def run_analysis_notebook(args: argparse.Namespace) -> None:
    """Execute a report notebook with the selected project configuration."""

    notebook_names = {
        "zipf": "01_zipf.ipynb",
        "heaps": "02_heaps.ipynb",
    }
    source = Path("notebooks") / notebook_names[args.analysis]
    if not source.is_file():
        raise FileNotFoundError(source)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_name = f"{source.stem}-{Path(args.config).stem}.ipynb"
    import nbformat

    notebook = nbformat.read(source, as_version=4)
    environment_updates = {
        "YELPTEXT_CONFIG": str(Path(args.config).resolve()),
        "YELPTEXT_PROJECT_ROOT": str(Path.cwd().resolve()),
    }
    previous = {key: os.environ.get(key) for key in environment_updates}
    try:
        os.environ.update(environment_updates)
        namespace: dict[str, object] = {"__name__": "__main__"}
        execution_count = 0
        for cell_index, cell in enumerate(notebook.cells, start=1):
            if cell.cell_type != "code":
                continue
            execution_count += 1
            standard_output = io.StringIO()
            standard_error = io.StringIO()
            cell.outputs = []
            cell.execution_count = execution_count
            try:
                with contextlib.redirect_stdout(standard_output), contextlib.redirect_stderr(
                    standard_error
                ):
                    exec(
                        compile(
                            cell.source,
                            f"{source}:cell-{cell_index}",
                            "exec",
                        ),
                        namespace,
                    )
            except Exception as exc:
                cell.outputs.append(
                    nbformat.v4.new_output(
                        "error",
                        ename=type(exc).__name__,
                        evalue=str(exc),
                        traceback=[],
                    )
                )
                raise
            finally:
                if standard_output.getvalue():
                    cell.outputs.append(
                        nbformat.v4.new_output(
                            "stream", name="stdout", text=standard_output.getvalue()
                        )
                    )
                if standard_error.getvalue():
                    cell.outputs.append(
                        nbformat.v4.new_output(
                            "stream", name="stderr", text=standard_error.getvalue()
                        )
                    )
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    nbformat.write(notebook, output_dir / output_name)
    print(
        json.dumps(
            {
                "status": "COMPLETED",
                "analysis": args.analysis,
                "config": args.config,
                "executed_notebook": str(output_dir / output_name),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
