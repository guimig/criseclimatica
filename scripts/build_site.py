"""Build the static portal. Production collects live; --fixture is only for CI/offline tests."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from observatorio.config import load_locations  # noqa: E402
from observatorio.open_meteo import OpenMeteoClient, normalize  # noqa: E402
from observatorio.pipeline import collect  # noqa: E402
from observatorio.storage import write_json_atomic  # noqa: E402


class FixtureClient:
    def __init__(self, fixture: Path):
        self.raw = json.loads(fixture.read_text(encoding="utf-8"))

    def fetch(self, location):
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        return normalize(location, self.raw, stamp)


def build(output: Path, fixture: Path | None = None) -> tuple[int, int]:
    locations = load_locations(ROOT / "config" / "locations.json")
    client = FixtureClient(fixture) if fixture is not None else OpenMeteoClient()
    manifest, details = collect(locations, client)
    if fixture is not None:
        manifest["fixture_mode"] = True
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="observatorio-build-", dir=output.parent) as temp:
        staged = Path(temp) / "site"
        shutil.copytree(ROOT / "web", staged)
        data = staged / "data"
        write_json_atomic(data / "latest.json", manifest)
        for slug, record in details.items():
            write_json_atomic(data / "places" / (slug + ".json"), record)
        (staged / ".nojekyll").write_text("", encoding="utf-8")
        if output.exists():
            shutil.rmtree(output)
        shutil.move(str(staged), str(output))
    return len(details), len(locations)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build weather observatory static pages")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--fixture", type=Path, default=None, help="Offline synthetic provider response, never deploy")
    args = parser.parse_args()
    try:
        count, total = build(args.output, args.fixture)
    except Exception as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"Built site for {count}/{total} locations at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
