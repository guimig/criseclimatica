"""Regressions for incomplete rainfall, municipal failures and independent publication."""
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from observatorio.pipeline import rain_window, collect as collect_model
from observatorio.cemaden import collect as collect_rain, CemadenError
from observatorio.coverage import summarize
from build_site import build
from validate_site import validate

NOW = datetime(2026, 11, 6, 12, 30, tzinfo=timezone.utc)
STAMP = "2026-11-06T12:30:00Z"
PLACES = [{"id": "araquari", "ibge_code": "4201307"}, {"id": "joinville", "ibge_code": "4209102"}]


def hours():
    start = NOW.replace(minute=0)
    return [{"time": (start + timedelta(hours=i)).isoformat(), "precipitation_mm": 2}
            for i in range(1, 25)]


class RainWindowTests(unittest.TestCase):
    def test_complete_hourly_window_and_repeated_calculation(self):
        result = rain_window(hours(), NOW)
        self.assertEqual(result["total_mm"], 48)
        self.assertEqual(result["valid_hours"], 24)
        self.assertEqual(result["start_at"], "2026-11-06T12:00:00Z")
        self.assertEqual(result, rain_window(hours(), NOW))

    def test_missing_hour_is_partial_and_not_zero(self):
        result = rain_window(hours()[:-1], NOW)
        self.assertIsNone(result["total_mm"])
        self.assertEqual(result["partial_sum_mm"], 46)
        self.assertEqual(result["status"], "partial")

    def test_identical_duplicate_does_not_inflate_total(self):
        self.assertEqual(rain_window(hours() + hours(), NOW)["total_mm"], 48)

    def test_conflict_invalidates_hour_independent_of_order(self):
        rows = hours() + [{**hours()[0], "precipitation_mm": 20}]
        for series in (rows, list(reversed(rows))):
            result = rain_window(series, NOW)
            self.assertIsNone(result["total_mm"])
            self.assertEqual(result["valid_hours"], 23)

    def test_empty_and_invalid_values_never_become_full_total(self):
        for val in (None, True, -1, float("nan"), float("inf")):
            rows = hours()
            rows[0]["precipitation_mm"] = val
            self.assertIsNone(rain_window(rows, NOW)["total_mm"])
        self.assertIsNone(rain_window([], NOW)["partial_sum_mm"])

    def test_nonhourly_and_naive_timestamps_do_not_fill_gaps(self):
        rows = hours()[1:]
        rows.extend([{"time": "2026-11-06T13:30:00Z", "precipitation_mm": 2},
                     {"time": "2026-11-06T13:00:00", "precipitation_mm": 2}])
        self.assertEqual(rain_window(rows, NOW)["valid_hours"], 23)


class MunicipalTests(unittest.TestCase):
    def test_failure_is_not_no_station(self):
        def fetcher(code, token):
            if code == "4209102":
                raise CemadenError("offline")
            return [{"codibge": code, "codestacao": "12345", "datahora": STAMP, "acc24hr": 5}]
        result = collect_rain(PLACES, STAMP, token="test-only", now=NOW, fetcher=fetcher)
        self.assertEqual(result["diagnostic"], "partial")
        self.assertEqual(result["locations"][0]["status"], "available")
        self.assertEqual(result["locations"][1]["status"], "unavailable")
        self.assertEqual(result["locations"][1]["diagnostic"], "unavailable")

    def test_empty_success_and_unconfigured_are_distinct(self):
        empty = collect_rain(PLACES, STAMP, token="test", now=NOW, fetcher=lambda *_: [])
        missing = collect_rain(PLACES, STAMP, token="", now=NOW)
        self.assertTrue(all(r["status"] == "no_recent_data" for r in empty["locations"]))
        self.assertTrue(all(r["status"] == "not_configured" for r in missing["locations"]))


class CoverageTests(unittest.TestCase):
    def test_variables_and_unknown_units_are_not_invented(self):
        manifest = {"locations": [{"id":"araquari", "status":"available", "collected_at":STAMP,
                                  "current":{"time":STAMP,"temperature_c":25,"humidity_pct":None}}]}
        rain = {"status":"available", "checked_at":STAMP, "locations":[
                {"location_id":"araquari","status":"unavailable","stations":[]}]}
        sensors = {"status":"available", "checked_at":STAMP, "locations":[
                   {"location_id":"araquari","stations":[{"code":"12345","distance_km":50}]}],
                   "stations":[{"code":"12345","readings":[
                     {"sensor_name":"Sensor desconhecido","unit":None,"observed_at":STAMP}]}]}
        metar = {"status":"no_recent_reports","locations":[],"retrieved_at":STAMP}
        result = summarize(PLACES[:1], manifest, rain, sensors, metar, STAMP)
        products = result["locations"][0]["products"]
        self.assertEqual(products[0]["variables"], ["Temperatura (°C)"])
        self.assertEqual(products[1]["status"], "unavailable")
        self.assertEqual(products[2]["variables"], ["Sensor desconhecido (unidade não confirmada)"])
        self.assertEqual(products[2]["nearest_distance_km"], 50)
        self.assertEqual(products[2]["kind"], "nearby_station_observation")


class IndependentPublicationTests(unittest.TestCase):
    def test_model_outage_can_return_explicitly_empty_manifest(self):
        class Offline:
            def fetch(self, place):
                raise RuntimeError("offline")
        place = {"id":"araquari", "name":"Araquari", "state":"SC", "featured":True,
                 "latitude":-26.375, "longitude":-48.721}
        manifest, details = collect_model([place], Offline(), NOW, allow_empty=True)
        self.assertEqual(manifest["available_locations"], 0)
        self.assertEqual(details, {})
        self.assertIsNone(manifest["locations"][0]["current"])

    def _snapshot(self, target):
        build(target, fixture=ROOT / "tests/fixtures/open_meteo.json")
        return {path.stem: json.loads(path.read_text()) for path in (target / "data").glob("*.json")}

    def _patch_sources(self, stack, feeds, *, all_down=False):
        overview = deepcopy(feeds["latest"])
        overview.pop("fixture_mode", None)
        overview["available_locations"] = 0
        for row in overview["locations"]:
            row.update(status="unavailable", current=None, collected_at=None, rain_next_24h_mm=None)
        stack.enter_context(patch("build_site.collect", return_value=(overview, {})))
        stack.enter_context(patch("build_site.station_catalog_for_build", return_value=feeds["stations"]))
        stack.enter_context(patch("build_site.fetch_alerts", return_value=json.loads((ROOT/"tests/fixtures/inmet_alerts.json").read_text())))
        stack.enter_context(patch("build_site.fetch_metars", return_value=[]))
        mapping = {"collect_rain":"rain_gauges", "collect_archive":"inmet_archive", "collect_nasa":"nasa_power",
                   "collect_cemaden":"cemaden", "collect_cemaden_sensors":"cemaden_sensors",
                   "collect_cptec":"cptec", "collect_defesa":"defesa_civil_sc", "collect_epagri_geo":"epagri_geo",
                   "collect_epagri_notices":"epagri_notices", "collect_epagri_bulletins":"epagri_bulletins"}
        for function, name in mapping.items():
            feed = deepcopy(feeds[name])
            if feed.get("status") == "fixture_mode":
                feed["status"] = "not_configured" if name in ("rain_gauges", "cemaden", "cemaden_sensors") else "unavailable"
            if all_down:
                feed["status"] = "unavailable"
            stack.enter_context(patch("build_site."+function, return_value=feed))
        if all_down:
            from observatorio.alerts import AlertSourceError
            stack.enter_context(patch("build_site.fetch_alerts", side_effect=AlertSourceError("offline")))
            from observatorio.metar import MetarSourceError
            stack.enter_context(patch("build_site.fetch_metars", side_effect=MetarSourceError("offline")))

    def test_other_sources_publish_when_model_is_down(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/"site"
            feeds = self._snapshot(target)
            with ExitStack() as stack:
                self._patch_sources(stack, feeds)
                count, total = build(target)
            self.assertEqual(count, 0)
            self.assertEqual(total, 10)
            validate(target)
            overview = json.loads((target/"data/latest.json").read_text())
            self.assertEqual(overview["publication_status"], "partial")
            self.assertTrue(overview["official_alerts_integrated"])

    def test_total_outage_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/"site"
            feeds = self._snapshot(target)
            before = (target/"data/latest.json").read_bytes()
            with ExitStack() as stack:
                self._patch_sources(stack, feeds, all_down=True)
                with self.assertRaisesRegex(RuntimeError, "All operational sources failed"):
                    build(target)
            self.assertEqual(before, (target/"data/latest.json").read_bytes())

    def test_missing_previously_published_history_aborts(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("build_site.fetch_previous_json", side_effect=[None, {"model_history_published":True}]):
                with self.assertRaisesRegex(RuntimeError, "model history missing"):
                    build(Path(directory)/"site", previous_url="https://example.org/")

    def test_validator_rejects_partial_forecast_disguised_as_full(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/"site"
            feeds = self._snapshot(target)
            feeds["latest"]["locations"][0]["rain_next_24h_mm"] = 10
            (target/"data/latest.json").write_text(json.dumps(feeds["latest"]))
            with self.assertRaisesRegex(ValueError, "Partial forecast rain"):
                validate(target, fixture=True)


if __name__ == "__main__":
    unittest.main()
