"""Prepare raw Yelp review/business JSONL for downstream consumers."""

from __future__ import annotations

import json
import math
import re
import sqlite3
import tempfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

from yelptext.protocol.reviewer import PREPARED_REVIEW_SCHEMA_VERSION


def _valid_string(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return value


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, default=str)


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON numeric constant: {value}")


class _Audit:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.db = connection
        self.counts: Counter[str] = Counter()
        self.db.executescript(
            """
            CREATE TABLE businesses (
                business_id TEXT PRIMARY KEY, business_name TEXT,
                categories_json TEXT, city TEXT, state TEXT
            );
            CREATE TABLE review_profile (
                doc_id TEXT PRIMARY KEY, source_line INTEGER,
                user_id TEXT, business_id TEXT, stars REAL, review_date TEXT,
                text_length INTEGER, business_matched INTEGER
            );
            CREATE TABLE anomalies (
                source TEXT, source_line INTEGER, record_id TEXT,
                issue TEXT, severity TEXT, field_name TEXT,
                raw_value_json TEXT, text_preview TEXT
            );
            CREATE TABLE summary (metric TEXT PRIMARY KEY, value INTEGER);
            CREATE TABLE run_info (key TEXT PRIMARY KEY, value TEXT);
            """
        )

    def log(
        self,
        source: str,
        line: int,
        record_id: str | None,
        issue: str,
        severity: str = "warning",
        field: str = "",
        value: object = None,
        text: object = "",
    ) -> None:
        self.counts[f"issue_{source}_{issue}"] += 1
        raw = _json_text(value)[:1200]
        preview = text[:240] if isinstance(text, str) else ""
        preview = preview.encode("utf-8", errors="backslashreplace").decode("utf-8")
        self.db.execute(
            "INSERT INTO anomalies VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (source, line, record_id, issue, severity, field, raw, preview),
        )


def _read_records(path: Path, source: str, audit: _Audit):
    with path.open("rb") as stream:
        for number, raw in enumerate(stream, 1):
            audit.counts[f"{source}_lines"] += 1
            if number % 10_000 == 0:
                audit.db.commit()
            try:
                line = raw.decode("utf-8-sig" if number == 1 else "utf-8")
            except UnicodeDecodeError:
                audit.log(
                    source,
                    number,
                    None,
                    "invalid_utf8",
                    "error",
                    value=raw[:200].hex(),
                )
                audit.counts[f"{source}_unparseable"] += 1
                continue
            try:
                row = json.loads(
                    line,
                    object_pairs_hook=_object_without_duplicates,
                    parse_constant=_reject_constant,
                )
            except (ValueError, RecursionError):
                audit.log(
                    source, number, None, "invalid_json", "error", value=line[:1000]
                )
                audit.counts[f"{source}_unparseable"] += 1
                continue
            if not isinstance(row, dict):
                audit.log(source, number, None, "non_object", "error", value=row)
                audit.counts[f"{source}_unparseable"] += 1
                continue
            yield number, row


def _categories(value: object) -> tuple[list[str] | None, str | None]:
    if value is None:
        return None, None
    if value == []:
        return [], None
    if isinstance(value, str):
        if not value.strip():
            return [], None
        items = value.split(",")
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        items = value
    else:
        return None, "invalid_categories"
    if any(_valid_string(item) is None and item.strip() for item in items):
        return None, "invalid_categories"
    return list(dict.fromkeys(item.strip() for item in items if item.strip())), None


def _clean_stars(value: object) -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, "invalid_stars"
    if not 1 <= value <= 5 or not math.isfinite(value) or value * 2 != int(value * 2):
        return None, "invalid_stars"
    return float(value), None


def _clean_date(value: object) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    try:
        if not isinstance(value, str):
            raise ValueError
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value).isoformat(), None
        if not re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", value):
            raise ValueError
        source = value[:-1] + "+00:00" if value.endswith("Z") else value
        return datetime.fromisoformat(source).date().isoformat(), None
    except (ValueError, OverflowError):
        return None, "invalid_date"


def _load_businesses(path: Path, audit: _Audit) -> None:
    for line, row in _read_records(path, "business", audit):
        business_id = _valid_string(row.get("business_id"))
        if business_id is None:
            audit.log(
                "business",
                line,
                None,
                "invalid_business_id",
                "error",
                "business_id",
                row.get("business_id"),
            )
            audit.counts["business_rejected"] += 1
            continue
        labels, issue = _categories(row.get("categories"))
        if issue:
            audit.log(
                "business",
                line,
                business_id,
                issue,
                field="categories",
                value=row.get("categories"),
            )
        values: list[str | None] = []
        for field in ("name", "city", "state"):
            raw = row.get(field)
            cleaned = _valid_string(raw)
            if raw is not None and cleaned is None:
                audit.log(
                    "business",
                    line,
                    business_id,
                    "invalid_" + field,
                    field=field,
                    value=raw,
                )
            values.append(cleaned)
        inserted = audit.db.execute(
            "INSERT OR IGNORE INTO businesses VALUES (?, ?, ?, ?, ?)",
            (
                business_id,
                values[0],
                json.dumps(labels, ensure_ascii=False) if labels is not None else None,
                values[1],
                values[2],
            ),
        ).rowcount
        if inserted:
            audit.counts["business_loaded"] += 1
        else:
            audit.counts["business_duplicate"] += 1
            audit.log(
                "business",
                line,
                business_id,
                "duplicate_business_id",
                field="business_id",
                value=business_id,
            )
    audit.db.commit()


def prepare_reviews(
    review_path: str | Path,
    business_path: str | Path,
    output_path: str | Path,
    *,
    limit: int | None = None,
    long_text_threshold: int = 50_000,
) -> dict[str, Any]:
    """Create canonical review JSONL and adjacent JSON/SQLite audit artifacts."""

    reviews = Path(review_path).expanduser().resolve()
    businesses = Path(business_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    audit_db_path = output.with_suffix(".audit.sqlite")
    audit_json_path = output.with_suffix(".audit.json")

    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    if long_text_threshold <= 0:
        raise ValueError("long_text_threshold must be positive")
    if len({reviews, businesses, output, audit_db_path, audit_json_path}) != 5:
        raise ValueError("Input and output paths must be distinct")
    for path in (reviews, businesses):
        if not path.is_file():
            raise FileNotFoundError(path)
    for path in (output, audit_db_path, audit_json_path):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite: {path}")
    output.parent.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any]
    with tempfile.TemporaryDirectory(prefix="yelp-prepare-", dir=output.parent) as folder:
        stage = Path(folder)
        db = sqlite3.connect(stage / "audit.sqlite")
        db.execute("PRAGMA cache_size=-32768")
        db.execute("PRAGMA temp_store=FILE")
        audit = _Audit(db)
        try:
            _load_businesses(businesses, audit)
            with (stage / "reviews.jsonl").open(
                "w", encoding="utf-8", newline="\n"
            ) as target:
                for line, row in _read_records(reviews, "review", audit):
                    doc_id = _valid_string(row.get("review_id")) or _valid_string(
                        row.get("doc_id")
                    )
                    text = row.get("text")
                    if doc_id is None or _valid_string(text) is None:
                        if doc_id is None:
                            audit.log(
                                "review",
                                line,
                                None,
                                "invalid_doc_id",
                                "error",
                                "review_id",
                                row.get("review_id", row.get("doc_id")),
                            )
                        if _valid_string(text) is None:
                            audit.log(
                                "review",
                                line,
                                doc_id,
                                "invalid_text",
                                "error",
                                "text",
                                text,
                            )
                        audit.counts["review_rejected"] += 1
                        continue

                    text_value = cast(str, text)
                    user_id = _valid_string(row.get("user_id"))
                    business_id = _valid_string(row.get("business_id"))
                    stars, stars_issue = _clean_stars(row.get("stars"))
                    raw_date = row.get("date", row.get("review_date"))
                    review_date, date_issue = _clean_date(raw_date)
                    business = (
                        db.execute(
                            "SELECT business_name, categories_json, city, state "
                            "FROM businesses WHERE business_id=?",
                            (business_id,),
                        ).fetchone()
                        if business_id
                        else None
                    )
                    inserted = db.execute(
                        "INSERT OR IGNORE INTO review_profile VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            doc_id,
                            line,
                            user_id,
                            business_id,
                            stars,
                            review_date,
                            len(text_value),
                            int(business is not None),
                        ),
                    ).rowcount
                    if not inserted:
                        audit.log(
                            "review",
                            line,
                            doc_id,
                            "duplicate_doc_id",
                            "error",
                            "review_id",
                            doc_id,
                            text,
                        )
                        audit.counts["review_duplicate"] += 1
                        continue
                    for issue, field, value in (
                        (stars_issue, "stars", row.get("stars")),
                        (date_issue, "date", raw_date),
                    ):
                        if issue:
                            audit.log(
                                "review",
                                line,
                                doc_id,
                                issue,
                                field=field,
                                value=value,
                                text=text,
                            )
                    if row.get("user_id") is not None and user_id is None:
                        audit.log(
                            "review",
                            line,
                            doc_id,
                            "invalid_user_id",
                            field="user_id",
                            value=row.get("user_id"),
                            text=text,
                        )
                    if business_id and business is None:
                        audit.log(
                            "review",
                            line,
                            doc_id,
                            "unmatched_business",
                            field="business_id",
                            value=business_id,
                            text=text,
                        )
                    if business_id is None:
                        audit.log(
                            "review",
                            line,
                            doc_id,
                            "missing_business_id",
                            "info",
                            "business_id",
                            row.get("business_id"),
                            text,
                        )
                    if len(text_value) > long_text_threshold:
                        audit.log(
                            "review",
                            line,
                            doc_id,
                            "long_text_candidate",
                            "info",
                            "text_length",
                            len(text_value),
                            text,
                        )
                    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]", text_value):
                        audit.log(
                            "review",
                            line,
                            doc_id,
                            "control_or_replacement_character",
                            field="text",
                            text=text,
                        )
                    record = {
                        "doc_id": doc_id,
                        "text": text_value,
                        "user_id": user_id,
                        "stars": stars,
                        "review_date": review_date,
                        "business_id": business_id,
                        "business_name": business[0] if business else None,
                        "categories": (
                            json.loads(business[1])
                            if business and business[1] is not None
                            else None
                        ),
                        "city": business[2] if business else None,
                        "state": business[3] if business else None,
                    }
                    target.write(
                        json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
                    )
                    audit.counts["review_written"] += 1
                    for field in record:
                        if field not in {"doc_id", "text"} and record[field] is None:
                            audit.counts["output_null_" + field] += 1
                    if audit.counts["review_written"] % 100_000 == 0:
                        db.commit()
                    if limit and audit.counts["review_written"] >= limit:
                        break

            report = {
                "schema_version": PREPARED_REVIEW_SCHEMA_VERSION,
                "reviews_source": str(reviews),
                "businesses_source": str(businesses),
                "output": str(output),
                "audit_database": str(audit_db_path),
                "selection": "development_prefix_not_random" if limit else "all_valid_unique",
                "limit": limit,
                "text_policy": "preserve_exactly",
                "duplicate_policy": "first_valid_record_per_exact_doc_id",
                "optional_invalid_policy": "null_and_log",
                "date_timezone_policy": "keep_calendar_date_as_written_no_timezone_conversion",
                "long_text_threshold": long_text_threshold,
                "counts": dict(sorted(audit.counts.items())),
            }
            db.executemany("INSERT INTO summary VALUES (?, ?)", report["counts"].items())
            db.executemany(
                "INSERT INTO run_info VALUES (?, ?)",
                [
                    (key, _json_text(value))
                    for key, value in report.items()
                    if key != "counts"
                ],
            )
            db.execute("CREATE INDEX anomalies_issue ON anomalies (issue)")
            db.commit()
            (stage / "audit.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        finally:
            db.close()

        (stage / "reviews.jsonl").replace(output)
        (stage / "audit.sqlite").replace(audit_db_path)
        (stage / "audit.json").replace(audit_json_path)
    return report
