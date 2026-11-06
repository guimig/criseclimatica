"""Offline contract, storage and pipeline tests; no network credentials needed."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from observatorio.config import load_locations
from observatorio.open_meteo import ProviderError, normalize
from observatorio.pipeline import collect, next_24h_rain
from observatorio.storage import daily_index, read_jsonl_gzip, write_json_atomic, write_jsonl_gzip_atomic
from build_site import build

FIXTURE = ROOT / "tests" / "fixtures" / "open_meteo.json"
LOCATION = {"id": "araquari", "name": "Araquari", "state": "SC", "latitude": -26.375, "longitude": -48.721, "featured": True}
TIMESTAMP = "2026-11-05T10:05:00Z"


def sample():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class TestConfiguration(unittest.TestCase):
    def test_initial_places(self):
        places = load_locations(ROOT / "config" / "locations.json")
        self.assertGreaterEqual(len(places), 5)
        self.assertEqual(places[0]["id"], "araquari")

    def test_repeated_id_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "locations.json"
            file.write_text(json.dumps({"version": 1, "locations": [LOCATION, LOCATION]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_locations(file)

    def test_out_of_range_latitude_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "locations.json"
            file.write_text(json.dumps({"version": 1, "locations": [{**LOCATION, "latitude": 111}]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_locations(file)


class TestProviderAdapter(unittest.TestCase):
    def test_normalize_and_attribution(self):
        result = normalize(LOCATION, sample(), TIMESTAMP)
        self.assertEqual(result["source"]["id"], "open-meteo")
        self.assertIn("not_station_observation", result["measurement_status"])
        self.assertEqual(result["current"]["time"], "2026-11-05T10:00Z")
        self.assertEqual(result["hourly"][1]["precipitation_mm"], .4)

    def test_missing_hourly_field_rejected(self):
        raw = sample()
        raw["hourly"].pop("wind_gusts_10m")
        with self.assertRaises(ProviderError):
            normalize(LOCATION, raw, TIMESTAMP)

    def test_inconsistent_array_lengths_rejected(self):
        raw = sample()
        raw["daily"]["temperature_2m_max"].pop()
        with self.assertRaises(ProviderError):
            normalize(LOCATION, raw, TIMESTAMP)

    def test_units_change_rejected(self):
        raw = sample()
        raw["current_units"]["wind_speed_10m"] = "m/s"
        with self.assertRaises(ProviderError):
            normalize(LOCATION, raw, TIMESTAMP)

    def test_nan_is_not_written(self):
        raw = sample()
        raw["current"]["temperature_2m"] = float("nan")
        result = normalize(LOCATION, raw, TIMESTAMP)
        self.assertIsNone(result["current"]["temperature_c"])


class FakeClient:
    def __init__(self, failed=None):
        self.failed = failed

    def fetch(self, location):
        if location["id"] == self.failed:
            raise ProviderError("Temporary API failure")
        return normalize(location, sample(), TIMESTAMP)


class TestPipeline(unittest.TestCase):
    def test_next_24_hours_rain_only_future(self):
        rows = normalize(LOCATION, sample(), TIMESTAMP)["hourly"]
        now = datetime(2026, 11, 5, 11, 30, tzinfo=timezone.utc)
        self.assertEqual(next_24h_rain(rows, now), 2.2)

    def test_partial_failure_is_visible(self):
        second = {**LOCATION, "id": "joinville", "name": "Joinville"}
        overview, records = collect([LOCATION, second], FakeClient(failed="joinville"), datetime(2026, 11, 5, 11, tzinfo=timezone.utc))
        self.assertEqual(overview["available_locations"], 1)
        self.assertEqual(overview["locations"][1]["status"], "unavailable")
        self.assertEqual(set(records), {"araquari"})
        self.assertFalse(overview["official_alerts_integrated"])

    def test_all_failed_prevents_publish(self):
        with self.assertRaises(RuntimeError):
            collect([LOCATION], FakeClient(failed="araquari"))

    def test_repeated_collection_same_ids(self):
        first, _ = collect([LOCATION], FakeClient(), datetime(2026, 11, 5, 11, tzinfo=timezone.utc))
        second, _ = collect([LOCATION], FakeClient(), datetime(2026, 11, 5, 11, tzinfo=timezone.utc))
        self.assertEqual(first, second)


class TestStorage(unittest.TestCase):
    def test_json_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "nested" / "current.json"
            write_json_atomic(target, {"ok": True})
            write_json_atomic(target, {"ok": False})
            self.assertEqual(json.loads(target.read_text()), {"ok": False})

    def test_gzip_archive_roundtrip_and_determinism(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "history" / "2026-11.jsonl.gz"
            records = [{"id": 1, "mm": 0.0}, {"id": 2, "mm": 24.3}]
            self.assertEqual(write_jsonl_gzip_atomic(target, records), 2)
            original = target.read_bytes()
            self.assertEqual(read_jsonl_gzip(target), records)
            write_jsonl_gzip_atomic(target, records)
            self.assertEqual(target.read_bytes(), original)
            with self.assertRaises(ValueError):
                read_jsonl_gzip(target, max_records=1)

    def test_daily_snapshot_is_not_mislabeled_as_observation(self):
        record = normalize(LOCATION, sample(), TIMESTAMP)
        newer = deepcopy(record)
        newer["collected_at"] = "2026-11-05T12:00:00Z"
        newer["current"]["temperature_c"] = 26
        result = daily_index([record, newer])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["temperature_c"], 26)
        self.assertEqual(result[0]["kind"], "model_snapshot_not_observation")


class TestOfflineSiteBuild(unittest.TestCase):
    def test_build_creates_site_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "dist"
            count, total = build(out, fixture=FIXTURE)
            self.assertEqual(count, total)
            overview = json.loads((out / "data" / "latest.json").read_text())
            self.assertTrue(overview["fixture_mode"])
            self.assertEqual(overview["available_locations"], total)
            self.assertTrue((out / "data" / "places" / "araquari.json").exists())
            self.assertTrue((out / "index.html").exists())
            self.assertTrue((out / ".nojekyll").exists())


if __name__ == "__main__":
    unittest.main()
