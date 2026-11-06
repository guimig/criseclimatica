"""Validate public static artifact before publishing; avoids synthetic builds in Pages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(output: Path, *, fixture: bool = False) -> None:
    data = output / "data"
    overview = json.loads((data / "latest.json").read_text(encoding="utf-8"))
    history = json.loads((data / "history.json").read_text(encoding="utf-8"))
    stations = json.loads((data / "stations.json").read_text(encoding="utf-8"))
    if overview.get("schema_version") != 1 or overview.get("fixture_mode", False) is not fixture:
        raise ValueError("Unexpected manifest schema or fixture mode")
    if not overview.get("available_locations") or not overview.get("locations"):
        raise ValueError("Manifest has no available locations")
    if history.get("kind") != "daily_last_model_publication_not_station_observation":
        raise ValueError("History source classification invalid")
    if stations.get("kind") != "station_catalog_metadata_not_measurements":
        raise ValueError("INMET catalog source classification invalid")
    for loc in overview["locations"]:
        if loc["status"] == "available":
            detail = json.loads((data / "places" / (loc["id"] + ".json")).read_text(encoding="utf-8"))
            if detail.get("measurement_status") != "estimated_model_not_station_observation":
                raise ValueError(f"Source classification changed for {loc['id']}")
    if not (output / "index.html").is_file():
        raise ValueError("Missing application index")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    validate(args.output, fixture=args.fixture)
    print(f"Site validated: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
