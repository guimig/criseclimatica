"""Offline integration tests for official notices and aerodrome observations."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from observatorio.alerts import AlertSourceError, normalize_alerts, unavailable_alerts, fetch_alerts
from observatorio.metar import MetarSourceError, normalize_metars, unavailable_metars, fetch_metars
from observatorio.config import load_locations
from observatorio.inmet_forecast import unavailable as forecast_unavailable
from observatorio.inmet_archive import unavailable_archive
from observatorio.nasa_power import unavailable as unavailable_nasa
from observatorio.epagri_geo import unavailable as unavailable_epagri_geo
from observatorio.epagri_notices import unavailable as unavailable_epagri_notices
from build_site import build
from validate_site import validate

LOCATIONS = load_locations(ROOT / "config" / "locations.json")
ALERTS = json.loads((ROOT / "tests" / "fixtures" / "inmet_alerts.json").read_text())
METAR = json.loads((ROOT / "tests" / "fixtures" / "metar.json").read_text())
NOW = datetime(2026, 11, 5, 13, 0, tzinfo=timezone.utc)
STAMP = NOW.isoformat(timespec="seconds").replace("+00:00", "Z")


class TestOfficialNotices(unittest.TestCase):
    def test_exact_municipality_geocode_and_deduplicates_revisions(self):
        result = normalize_alerts(ALERTS, LOCATIONS, STAMP)
        self.assertEqual(result["status"], "available")
        araquari = next(x for x in result["locations"] if x["location_id"] == "araquari")
        self.assertEqual(len(araquari["alerts"]), 1)
        self.assertEqual(araquari["alerts"][0]["id"], "3100")
        self.assertEqual(araquari["alerts"][0]["revision"], 2)
        self.assertEqual(araquari["alerts"][0]["severity"], "Grande Perigo")
        self.assertEqual(araquari["alerts"][0]["phases"], ["futuro", "hoje"])
        self.assertEqual(result["regional_distinct_notices"], 3)
        garuva = next(x for x in result["locations"] if x["location_id"] == "garuva")
        self.assertEqual(garuva["alerts"], [])

    def test_no_notices_is_distinct_from_network_failure(self):
        available = normalize_alerts({"hoje": [], "futuro": []}, LOCATIONS, STAMP)
        failed = unavailable_alerts(LOCATIONS, STAMP)
        self.assertEqual(available["status"], "available")
        self.assertEqual(available["regional_distinct_notices"], 0)
        self.assertEqual(failed["status"], "unavailable")
        self.assertIsNone(failed["regional_distinct_notices"])

    def test_unknown_api_structure_rejected(self):
        for obj in ({}, {"status": "ok"}, [], {"hoje": "error"}, {"hoje": [1]}):
            with self.subTest(obj=obj), self.assertRaises(AlertSourceError):
                normalize_alerts(obj, LOCATIONS, STAMP)

    def test_municipio_fallback_requires_exact_code(self):
        data = {"hoje": [{"id_aviso": 9, "municipios": "Araquari - SC (4201307),Outro - SC (4209102)"}], "futuro": []}
        result = normalize_alerts(data, LOCATIONS, STAMP)
        self.assertEqual(result["regional_distinct_notices"], 1)
        places = {x["location_id"]: len(x["alerts"]) for x in result["locations"]}
        self.assertEqual(places["araquari"], 1)
        self.assertEqual(places["itapoa"], 0)

    def test_invalid_provider_error_and_unavailable_fallback(self):
        with patch("observatorio.alerts.urlopen", side_effect=HTTPError("a", 503, "unavailable", {}, None)):
            with self.assertRaises(AlertSourceError):
                fetch_alerts()


class TestMetarObserved(unittest.TestCase):
    def test_valid_measured_units_and_station_not_municipality(self):
        result = normalize_metars(METAR, LOCATIONS, STAMP, now=NOW)
        self.assertEqual(result["status"], "available")
        self.assertEqual(len(result["stations"]), 2)
        araq = next(x for x in result["locations"] if x["location_id"] == "araquari")
        self.assertEqual(araq["observation"]["icao"], "SBJV")
        self.assertEqual(araq["observation"]["wind_kmh"], 14.8)
        self.assertEqual(araq["observation"]["gust_kmh"], 35.2)
        self.assertGreater(araq["distance_km"], 0)
        self.assertNotIn("rain_mm", araq["observation"])
        self.assertTrue(result["kind"].startswith("aerodrome_metar"))
        self.assertIsNone(next(x for x in result["stations"] if x["icao"] == "SBNF")["wind_direction_deg"])

    def test_expired_metars_not_published_as_recent(self):
        result = normalize_metars(METAR, LOCATIONS, STAMP, now=NOW + timedelta(hours=10))
        self.assertEqual(result["status"], "no_recent_reports")
        self.assertEqual(result["stations"], [])
        self.assertTrue(all(x["observation"] is None for x in result["locations"]))

    def test_missing_and_invalid_gust_are_not_zero(self):
        rec = [{**METAR[0], "wgst": "M", "wspd": 0}]
        result = normalize_metars(rec, LOCATIONS, STAMP, now=NOW)
        station = result["stations"][0]
        self.assertEqual(station["wind_kmh"], 0)
        self.assertIsNone(station["gust_kmh"])

    def test_empty_and_invalid_provider_payloads(self):
        self.assertEqual(normalize_metars([], LOCATIONS, STAMP, now=NOW)["status"], "no_recent_reports")
        with self.assertRaises(MetarSourceError):
            normalize_metars({"message": "error"}, LOCATIONS, STAMP, now=NOW)
        with patch("observatorio.metar.urlopen", side_effect=HTTPError("a", 429, "limited", {}, None)):
            with self.assertRaises(MetarSourceError):
                fetch_metars()
        self.assertEqual(unavailable_metars(LOCATIONS, STAMP)["status"], "unavailable")

    def test_repeated_normalization_is_deterministic(self):
        self.assertEqual(normalize_metars(METAR, LOCATIONS, STAMP, now=NOW), normalize_metars(METAR, LOCATIONS, STAMP, now=NOW))


class TestStaticBuild(unittest.TestCase):
    def test_outputs_are_attributed_and_not_releasable_as_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "dist"
            build(out, fixture=ROOT / "tests" / "fixtures" / "open_meteo.json")
            alerts = json.loads((out / "data" / "alerts.json").read_text())
            observations = json.loads((out / "data" / "observations.json").read_text())
            self.assertEqual(alerts["status"], "available")
            self.assertIn(observations["status"], ("available", "no_recent_reports"))
            self.assertTrue(json.loads((out / "data" / "latest.json").read_text())["fixture_mode"])
            validate(out, fixture=True)
            with self.assertRaises(ValueError):
                validate(out, fixture=False)

    def test_optional_source_failure_never_turns_into_zero_alerts(self):
        from observatorio.open_meteo import normalize as model_normalize

        class ForecastStub:
            def fetch(self, location):
                raw = json.loads((ROOT / "tests" / "fixtures" / "open_meteo.json").read_text())
                return model_normalize(location, raw, STAMP)

        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "dist"
            catalog = {"schema_version": 1, "kind": "station_catalog_metadata_not_measurements", "locations": []}
            with patch("build_site.collect_inmet_forecast", side_effect=lambda stamp, **kwargs: forecast_unavailable(stamp)), \
                 patch("build_site.collect_campus", side_effect=lambda stamp: __import__("observatorio.campus_station", fromlist=["empty"]).empty(stamp)), \
                 patch("build_site.OpenMeteoClient", return_value=ForecastStub()), \
                 patch("build_site.fetch_alerts", side_effect=AlertSourceError("service offline")), \
                 patch("build_site.fetch_metars", side_effect=MetarSourceError("service offline")), \
                 patch("build_site.station_catalog_for_build", return_value=catalog), \
                 patch("build_site.collect_archive", side_effect=lambda locations, catalog, stamp, **kwargs: unavailable_archive(stamp)), \
                 patch("build_site.collect_nasa", side_effect=lambda place, stamp, previous=None: unavailable_nasa(place, stamp)), \
                 patch("build_site.collect_epagri_geo", side_effect=lambda locations, stamp, **kwargs: unavailable_epagri_geo(stamp)), \
                 patch("build_site.collect_epagri_notices", side_effect=lambda stamp, **kwargs: unavailable_epagri_notices(stamp)), \
                 patch("build_site.collect_cptec", return_value={"schema_version":1,"kind":"cptec_inpe_daily_forecast_nearest_locality_not_station_measurements","status":"unavailable","checked_at":"2026-11-05T12:00:00Z","locations":[{"location_id":loc["id"],"status":"unavailable","days":[]} for loc in LOCATIONS]}), \
                 patch("build_site.collect_defesa", return_value={"schema_version":1,"kind":"defesa_civil_sc_publications_not_verified_active_alerts","status":"unavailable","checked_at":"2026-11-05T12:00:00Z","publications":[]}):
                build(out)
            manifest = json.loads((out / "data" / "latest.json").read_text())
            notices = json.loads((out / "data" / "alerts.json").read_text())
            metar = json.loads((out / "data" / "observations.json").read_text())
            self.assertFalse(manifest["official_alerts_integrated"])
            self.assertFalse(manifest.get("fixture_mode", False))
            self.assertEqual(notices["status"], "unavailable")
            self.assertIsNone(notices["retrieved_at"])
            self.assertEqual(metar["status"], "unavailable")
            validate(out, fixture=False)

    def test_live_build_refuses_mixed_provider_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "synthetic"):
                build(Path(folder), metar_fixture=ROOT / "tests" / "fixtures" / "metar.json")


if __name__ == "__main__":
    unittest.main()

