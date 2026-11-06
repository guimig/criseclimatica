"""Read-only configuration and geographic validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_locations(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        config = json.load(stream)
    if config.get("version") != 1 or not isinstance(config.get("locations"), list):
        raise ValueError("Invalid locations configuration or version")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in config["locations"]:
        if not isinstance(item, dict):
            raise ValueError("Each location must be an object")
        slug = item.get("id")
        name = item.get("name")
        lat, lon = item.get("latitude"), item.get("longitude")
        if not isinstance(slug, str) or not _ID_RE.fullmatch(slug) or slug in seen:
            raise ValueError(f"Invalid or repeated location id: {slug!r}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Invalid name for {slug}")
        if (not isinstance(lat, (int, float)) or isinstance(lat, bool)
                or not -90 <= lat <= 90 or not isinstance(lon, (int, float))
                or isinstance(lon, bool) or not -180 <= lon <= 180):
            raise ValueError(f"Invalid coordinates for {slug}")
        seen.add(slug)
        result.append({
            "id": slug, "name": name, "state": item.get("state", ""),
            "latitude": float(lat), "longitude": float(lon),
            "featured": bool(item.get("featured", False)),
        })
    if not result:
        raise ValueError("At least one location is required")
    return result
