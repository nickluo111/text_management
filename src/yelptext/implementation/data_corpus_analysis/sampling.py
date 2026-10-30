"""Streaming, order-independent review sampling for downstream experiments."""

from __future__ import annotations

import heapq
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_FNV_OFFSET_BASIS = 14_695_981_039_346_656_037
_FNV_PRIME = 1_099_511_628_211
_PRIORITY_MASK = (1 << 63) - 1


def stable_priority(seed: int, namespace: str, doc_id: str) -> int:
    """Return a deterministic non-cryptographic 63-bit sampling priority."""

    value = _FNV_OFFSET_BASIS
    for byte in f"{seed}\0{namespace}\0{doc_id}".encode("utf-8"):
        value ^= byte
        value = (value * _FNV_PRIME) & ((1 << 64) - 1)
    return value & _PRIORITY_MASK


@dataclass(slots=True)
class HeapItem:
    """Reverse ordering so the heap root is the worst retained item."""

    key: tuple[int, str]
    record: dict[str, Any]

    def __lt__(self, other: "HeapItem") -> bool:
        return self.key > other.key


def offer(
    heap: list[HeapItem],
    capacity: int,
    item_priority: int,
    record: dict[str, Any],
) -> None:
    """Offer a record containing canonical ``doc_id`` to a bottom-k heap."""

    if capacity <= 0:
        return
    doc_id = record.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id:
        raise ValueError("sample records must contain a non-empty string doc_id")
    entry = HeapItem((item_priority, doc_id), record)
    if len(heap) < capacity:
        heapq.heappush(heap, entry)
    elif entry.key < heap[0].key:
        heapq.heapreplace(heap, entry)


def selected(heap: list[HeapItem]) -> list[dict[str, Any]]:
    """Return retained records in stable priority/doc-id order."""

    return [item.record for item in sorted(heap, key=lambda item: item.key)]


def sample_reviews(
    input_path: str | Path,
    output_path: str | Path,
    *,
    sample_size: int,
    seed: int = 6122,
    namespace: str = "reviews",
) -> dict[str, object]:
    """Stream JSONL and write a schema-preserving deterministic review sample."""

    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    source_path = Path(input_path)
    target_path = Path(output_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if target_path.exists():
        raise FileExistsError(f"Output already exists: {target_path}")

    heap: list[HeapItem] = []
    nonempty_lines = 0
    valid_reviews = 0
    bad_lines = 0

    with source_path.open("rb") as source:
        for source_line, raw in enumerate(source, start=1):
            if not raw.strip():
                continue
            nonempty_lines += 1
            try:
                row = json.loads(raw)
                if not isinstance(row, dict):
                    raise TypeError("review record must be a JSON object")
                doc_id = row.get("doc_id") or row.get("review_id")
                if not isinstance(doc_id, str) or not doc_id:
                    raise TypeError("missing string doc_id/review_id")
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                bad_lines += 1
                continue

            valid_reviews += 1
            offer(
                heap,
                sample_size,
                stable_priority(seed, namespace, doc_id),
                {
                    "doc_id": doc_id,
                    "source_line": source_line,
                    "payload": row,
                },
            )

    sampled = selected(heap)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8", newline="\n") as output:
        for item in sampled:
            output.write(json.dumps(item["payload"], ensure_ascii=False) + "\n")

    return {
        "status": "COMPLETED",
        "input": str(source_path),
        "output": str(target_path),
        "seed": seed,
        "namespace": namespace,
        "method": "bottom-k FNV-1a priorities ordered by (priority, doc_id)",
        "nonempty_lines_scanned": nonempty_lines,
        "valid_reviews": valid_reviews,
        "bad_lines": bad_lines,
        "sample_requested": sample_size,
        "sample_written": len(sampled),
    }
