"""Small, portable and deterministic JSON/JSONL.GZ storage primitives.

This module does not pretend Google Drive or a GitHub repository is a database.
No generated archive is uploaded automatically in the MVP.
"""

from __future__ import annotations

import gzip
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_jsonl_gzip_atomic(path: Path, records: Iterable[dict[str, Any]]) -> int:
    """Replace one closed archive atomically. Callers must supply the full partition."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".gz")
    count = 0
    try:
        with os.fdopen(descriptor, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
                for record in records:
                    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
                    compressed.write((line + "\n").encode("utf-8"))
                    count += 1
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return count


def read_jsonl_gzip(path: Path, max_records: int = 100_000) -> list[dict[str, Any]]:
    if max_records < 1:
        raise ValueError("max_records must be positive")
    result = []
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            if len(result) >= max_records:
                raise ValueError("Archive record limit exceeded")
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError("Archive contains a non-object record")
            result.append(obj)
    return result


def daily_index(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Produces a regular daily catalog of MODEL snapshots (not observations)."""
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        location = record.get("location") or {}
        current = record.get("current") or {}
        if not isinstance(location, dict) or not isinstance(current, dict):
            continue
        location_id, reference = location.get("id"), current.get("time")
        if not isinstance(location_id, str) or not isinstance(reference, str) or len(reference) < 10:
            continue
        key = (location_id, reference[:10])
        existing = index.get(key)
        if existing is None or str(record.get("collected_at", "")) > existing["collected_at"]:
            index[key] = {
                "location_id": location_id,
                "day_utc": reference[:10],
                "source": "open-meteo",
                "kind": "model_snapshot_not_observation",
                "collected_at": record.get("collected_at", ""),
                "temperature_c": current.get("temperature_c"),
                "wind_kmh": current.get("wind_kmh"),
            }
    return [index[key] for key in sorted(index)]
