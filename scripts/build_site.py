"""Build static Pages. Real providers in production; offline fixture is never deployable."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from observatorio.config import load_locations  # noqa: E402
from observatorio.alerts import AlertSourceError, fetch_alerts, normalize_alerts, unavailable_alerts  # noqa: E402
from observatorio.metar import MetarSourceError, fetch_metars, normalize_metars, unavailable_metars  # noqa: E402
from observatorio.history import merge_daily_publications  # noqa: E402
from observatorio.inmet import CatalogError, fetch_catalog, nearby_catalog, normalize_catalog, now_utc  # noqa: E402
from observatorio.open_meteo import OpenMeteoClient, normalize  # noqa: E402
from observatorio.pipeline import collect  # noqa: E402
from observatorio.storage import write_json_atomic  # noqa: E402


class FixtureClient:
    def __init__(self, fixture: Path):
        self.raw = json.loads(fixture.read_text(encoding="utf-8"))

    def fetch(self, location):
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        return normalize(location, self.raw, stamp)


def fetch_previous_json(base_url: str, path: str, *, max_bytes: int = 3_000_000) -> dict | None:
    """Retrieve prior published state; 404 means first publication, other errors fail closed."""
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Previous site must be a public HTTPS address")
    if not path.startswith("data/") or ".." in path:
        raise ValueError("Invalid previous data path")
    address = urljoin(base_url.rstrip("/") + "/", path)
    request = Request(address, headers={"Accept": "application/json", "User-Agent": "criseclimatica-history-merge/0.2"})
    try:
        with urlopen(request, timeout=12) as response:
            content = response.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise ValueError(f"Previous {path} exceeds safety limit")
        data = json.loads(content.decode("utf-8"))
        if not isinstance(data, dict) or data.get("fixture_mode"):
            raise ValueError("Invalid or synthetic previous data")
        return data
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise RuntimeError(f"Previous {path} not accessible: HTTP {exc.code}") from exc
    except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Previous {path} unavailable; refusing possible history loss") from exc


def station_catalog_for_build(locations: list[dict], previous: dict | None, fixture: Path | None) -> dict:
    """Refresh station METADATA daily, without blocking forecast publication on outages."""
    prior_ok = (
        isinstance(previous, dict)
        and previous.get("schema_version") == 1
        and previous.get("kind") == "station_catalog_metadata_not_measurements"
        and previous.get("source", {}).get("id") == "inmet"
        and isinstance(previous.get("locations"), list)
        and {item.get("location_id") for item in previous["locations"] if isinstance(item, dict)} == {loc["id"] for loc in locations}
    )
    stamp = now_utc()
    age = None
    if prior_ok:
        try:
            prior_dt = datetime.fromisoformat(previous["retrieved_at"].replace("Z", "+00:00"))
            if prior_dt.tzinfo is None:
                raise ValueError("Timestamp has no timezone")
            age = datetime.now(timezone.utc) - prior_dt.astimezone(timezone.utc)
        except (ValueError, TypeError, KeyError, AttributeError):
            prior_ok = False

    if fixture is None and prior_ok and timedelta(0) <= age < timedelta(hours=24):
        return {**previous, "catalog_status": "cached"}
    try:
        raw = json.loads(fixture.read_text(encoding="utf-8")) if fixture else None
        stations = normalize_catalog(raw) if fixture else fetch_catalog()
        result = nearby_catalog(locations, stations, stamp)
        result["catalog_status"] = "available"
        return result
    except (CatalogError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Station catalog unavailable: {type(exc).__name__}", file=sys.stderr)
        if prior_ok and timedelta(0) <= age <= timedelta(days=7):
            return {**previous, "catalog_status": "stale"}
        return {
            "schema_version": 1, "kind": "station_catalog_metadata_not_measurements",
            "source": {"id": "inmet", "name": "INMET", "url": "https://apitempo.inmet.gov.br/estacoes/T"},
            "retrieved_at": None, "catalog_status": "unavailable", "locations": [],
        }


def build(
    output: Path, fixture: Path | None = None, *, previous_url: str | None = None,
    station_fixture: Path | None = None, alerts_fixture: Path | None = None, metar_fixture: Path | None = None,
) -> tuple[int, int]:
    if fixture is None and any(value is not None for value in (station_fixture, alerts_fixture, metar_fixture)):
        raise ValueError("Provider fixtures can only be used in a synthetic offline build")
    locations = load_locations(ROOT / "config" / "locations.json")
    client = FixtureClient(fixture) if fixture is not None else OpenMeteoClient()

    # Never use live site state in an offline fixture build.
    previous_history = None
    previous_stations = None
    if previous_url and fixture is None:
        previous_history = fetch_previous_json(previous_url, "data/history.json")
        # A metadata outage should not disable the weather and history updates.
        try:
            previous_stations = fetch_previous_json(previous_url, "data/stations.json", max_bytes=800_000)
        except (RuntimeError, ValueError) as exc:
            print(f"Previous stations not available: {exc}", file=sys.stderr)

    manifest, details = collect(locations, client)
    if fixture is not None:
        manifest["fixture_mode"] = True

    history = merge_daily_publications(previous_history, manifest, details)
    if fixture is not None and station_fixture is None:
        station_fixture = ROOT / "tests" / "fixtures" / "inmet_catalog.json"
    stations = station_catalog_for_build(locations, previous_stations, station_fixture)
    stamp = now_utc()
    if fixture is not None:
        alert_raw = json.loads((alerts_fixture or ROOT / "tests" / "fixtures" / "inmet_alerts.json").read_text(encoding="utf-8"))
        metar_raw = json.loads((metar_fixture or ROOT / "tests" / "fixtures" / "metar.json").read_text(encoding="utf-8"))
        alerts = normalize_alerts(alert_raw, locations, stamp)
        observations = normalize_metars(metar_raw, locations, stamp)
    else:
        try:
            alerts = normalize_alerts(fetch_alerts(), locations, stamp)
        except (AlertSourceError, OSError, ValueError, TypeError) as exc:
            print(f"INMET notices unavailable: {type(exc).__name__}", file=sys.stderr)
            alerts = unavailable_alerts(locations, stamp)
        try:
            observations = normalize_metars(fetch_metars(), locations, stamp)
        except (MetarSourceError, OSError, ValueError, TypeError) as exc:
            print(f"Aviation METAR unavailable: {type(exc).__name__}", file=sys.stderr)
            observations = unavailable_metars(locations, stamp)
    manifest["official_alerts_integrated"] = alerts["status"] == "available"
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="observatorio-build-", dir=output.parent) as temp:
        staged = Path(temp) / "site"
        shutil.copytree(ROOT / "web", staged)
        data = staged / "data"
        write_json_atomic(data / "latest.json", manifest)
        write_json_atomic(data / "history.json", history)
        write_json_atomic(data / "stations.json", stations)
        write_json_atomic(data / "alerts.json", alerts)
        write_json_atomic(data / "observations.json", observations)
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
    parser.add_argument("--stations-fixture", type=Path, default=None, help="Offline INMET catalog fixture")
    parser.add_argument("--previous-url", type=str, default=None, help="Prior GitHub Pages site for rolling history")
    parser.add_argument("--alerts-fixture", type=Path, default=None, help="INMET alerts sample for offline build only")
    parser.add_argument("--metar-fixture", type=Path, default=None, help="METAR sample for offline build only")
    args = parser.parse_args()
    try:
        count, total = build(args.output, args.fixture, previous_url=args.previous_url, station_fixture=args.stations_fixture, alerts_fixture=args.alerts_fixture, metar_fixture=args.metar_fixture)
    except Exception as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"Built site for {count}/{total} locations at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
