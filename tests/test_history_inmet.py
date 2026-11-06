"""INMET metadata and rolling model publication history, always offline."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_site import build, fetch_previous_json, station_catalog_for_build
from observatorio.config import load_locations
from observatorio.history import merge_daily_publications
from observatorio.inmet import CatalogError, haversine_km, nearby_catalog, normalize_catalog
from observatorio.open_meteo import normalize
from observatorio.pipeline import collect

FORECAST = ROOT / "tests" / "fixtures" / "open_meteo.json"
STATIONS = ROOT / "tests" / "fixtures" / "inmet_catalog.json"
NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
LOCATIONS = load_locations(ROOT / "config" / "locations.json")


class FakeForecast:
    def fetch(self, location):
        return normalize(location, json.loads(FORECAST.read_text(encoding="utf-8")), "2026-11-05T11:59:00Z")


def collected():
    return collect(LOCATIONS[:2], FakeForecast(), NOW)


class TestInmetCatalog(unittest.TestCase):
    def test_deduplicates_and_rejects_invalid_coordinates(self):
        stations = normalize_catalog(json.loads(STATIONS.read_text(encoding="utf-8")))
        self.assertEqual([s["code"] for s in stations], ["A001", "A002", "A003"])
        self.assertEqual(stations[1]["catalog_status"], "Pane")

    def test_nearest_order_and_metadata_label(self):
        stations = normalize_catalog(json.loads(STATIONS.read_text(encoding="utf-8")))
        record = nearby_catalog(LOCATIONS[:2], stations, "2026-11-05T12:00:00Z")
        self.assertEqual(record["kind"], "station_catalog_metadata_not_measurements")
        near = record["locations"][0]["stations"]
        self.assertEqual(near[0]["code"], "A001")
        self.assertLess(near[0]["distance_km"], 1)
        self.assertNotIn("A003", [s["code"] for s in near])
        self.assertLess(haversine_km(-26.375, -48.721, -26.3044, -48.8487), 20)

    def test_empty_and_invalid_payload(self):
        for payload in ([], {}, ["bad", {"CD_ESTACAO": "A"}]):
            with self.subTest(payload=payload), self.assertRaises(CatalogError):
                normalize_catalog(payload)

    def test_cached_catalog_does_not_fetch_provider(self):
        previous = nearby_catalog(LOCATIONS[:1], normalize_catalog(json.loads(STATIONS.read_text())), datetime.now(timezone.utc).isoformat())
        with patch("build_site.fetch_catalog", side_effect=AssertionError("Unnecessary refresh")):
            result = station_catalog_for_build(LOCATIONS[:1], previous, None)
        self.assertEqual(result["catalog_status"], "cached")

    def test_provider_outage_preserves_recent_catalog(self):
        timestamp = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        previous = nearby_catalog(LOCATIONS[:1], normalize_catalog(json.loads(STATIONS.read_text())), timestamp)
        with patch("build_site.fetch_catalog", side_effect=CatalogError("Network down")):
            result = station_catalog_for_build(LOCATIONS[:1], previous, None)
        self.assertEqual(result["catalog_status"], "stale")
        self.assertEqual(result["retrieved_at"], timestamp)

    def test_provider_outage_does_not_publish_misleading_station_data(self):
        with patch("build_site.fetch_catalog", side_effect=CatalogError("Network down")):
            result = station_catalog_for_build(LOCATIONS[:1], None, None)
        self.assertEqual(result["catalog_status"], "unavailable")
        self.assertEqual(result["locations"], [])


class TestDailyModelHistory(unittest.TestCase):
    def test_first_collection_and_repeat_are_idempotent(self):
        manifest, details = collected()
        first = merge_daily_publications(None, manifest, details, now=NOW)
        twice = merge_daily_publications(first, manifest, details, now=NOW)
        self.assertEqual(first, twice)
        self.assertEqual(len(first["records"]), 2)
        self.assertEqual(first["records"][0]["day_local"], "2026-11-05")
        self.assertIn("not_station_observation", first["kind"])

    def test_recent_replaces_older_value_within_same_day(self):
        manifest, details = collected()
        earlier = merge_daily_publications(None, manifest, details, now=NOW)
        details["araquari"]["current"]["temperature_c"] = 29
        details["araquari"]["collected_at"] = "2026-11-05T12:10:00Z"
        later = merge_daily_publications(earlier, manifest, details, now=datetime(2026, 11, 5, 12, 15, tzinfo=timezone.utc))
        self.assertEqual(next(x for x in later["records"] if x["location_id"] == "araquari")["temperature_c"], 29)
        self.assertEqual(len(later["records"]), 2)

    def test_brazil_local_date_not_utc_day(self):
        manifest, details = collected()
        details["araquari"]["collected_at"] = "2026-11-06T01:20:00Z"
        result = merge_daily_publications(None, manifest, {"araquari": details["araquari"]}, now=datetime(2026, 11, 6, 1, 30, tzinfo=timezone.utc))
        self.assertEqual(result["records"][0]["day_local"], "2026-11-05")

    def test_previous_outside_retention_removed(self):
        manifest, details = collected()
        previous = merge_daily_publications(None, manifest, details, now=NOW)
        previous["records"][0]["day_local"] = "2023-11-01"
        result = merge_daily_publications(previous, manifest, details, now=NOW, keep_days=20)
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual({row["day_local"] for row in result["records"]}, {"2026-11-05"})

    def test_malformed_or_duplicate_history_rejected(self):
        manifest, details = collected()
        previous = merge_daily_publications(None, manifest, details, now=NOW)
        bad = {**previous, "kind": "measured_climate"}
        with self.assertRaises(ValueError):
            merge_daily_publications(bad, manifest, details, now=NOW)
        duplicated = {**previous, "records": previous["records"] + [previous["records"][0]]}
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            merge_daily_publications(duplicated, manifest, details, now=NOW)
        with self.assertRaises(ValueError):
            merge_daily_publications(previous, manifest, details, now=NOW, keep_days=999)

    def test_missing_previous_url_initializes_history_only_on_404(self):
        with patch("build_site.urlopen", side_effect=HTTPError("https://example.org/data/history.json", 404, "Not Found", {}, None)):
            self.assertIsNone(fetch_previous_json("https://example.org/", "data/history.json"))
        with patch("build_site.urlopen", side_effect=URLError("network down")):
            with self.assertRaisesRegex(RuntimeError, "history loss"):
                fetch_previous_json("https://example.org/", "data/history.json")
        with self.assertRaises(ValueError):
            fetch_previous_json("http://example.org/", "data/history.json")


class TestBuildWithNewData(unittest.TestCase):
    def test_fixture_generates_history_and_station_catalog(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "dist"
            n, total = build(destination, fixture=FORECAST, station_fixture=STATIONS)
            self.assertEqual(n, total)
            history = json.loads((destination / "data" / "history.json").read_text())
            stations = json.loads((destination / "data" / "stations.json").read_text())
            self.assertEqual(len(history["records"]), len(LOCATIONS))
            self.assertEqual(stations["source"]["id"], "inmet")
            self.assertTrue(stations["locations"][0]["stations"])
            self.assertNotIn("precipitation_measured_mm", json.dumps(stations))
            self.assertTrue(json.loads((destination / "data" / "latest.json").read_text())["fixture_mode"])


if __name__ == "__main__":
    unittest.main()
