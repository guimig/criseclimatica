"""Offline end-to-end coverage for new public Epagri sources and safety rules."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from observatorio.config import load_locations
from observatorio.epagri_geo import EpagriGeoError, collect as collect_geo, normalize_registry, request_url
from observatorio.epagri_notices import EpagriNoticeError, collect as collect_notices, parse_feed
from build_site import build
from validate_site import validate

PLACES = load_locations(ROOT / "config" / "locations.json")
GEO = json.loads((ROOT / "tests" / "fixtures" / "epagri_gis.json").read_text(encoding="utf-8"))
FEED = (ROOT / "tests" / "fixtures" / "epagri_notices.xml").read_bytes()
NOW = "2026-11-06T02:00:00Z"


class EpagriGIS(unittest.TestCase):
    def test_public_arcgis_url_bounded_and_region_specific(self):
        url = request_url()
        self.assertTrue(url.startswith("https://gis.epagri.sc.gov.br/arcgis/"))
        self.assertIn("resultRecordCount=2000", url)
        self.assertIn("inSR=4326", url)
        self.assertIn("returnGeometry=false", url)

    def test_normalization_and_distance_no_live_readings(self):
        output = normalize_registry(GEO, PLACES, NOW)
        self.assertEqual(output["status"], "available")
        self.assertIn("not_live_measurements", output["kind"])
        first = output["locations"][0]["stations"]
        self.assertTrue(first)
        self.assertEqual(first[0]["code"], "1001")
        self.assertLess(first[0]["distance_km"], 1)
        self.assertNotIn("rain_mm", str(output))
        self.assertEqual(first[0]["municipality"], "Araquari")
        self.assertEqual(len(output["locations"]), len(PLACES))

    def test_invalid_geometry_and_foreign_state_excluded(self):
        copy = json.loads(json.dumps(GEO))
        copy["features"][0]["attributes"]["VL_LATIT_ESTAC"] = "not a coordinate"
        copy["features"][1]["attributes"]["SG_UF"] = "RS"
        output = normalize_registry(copy, PLACES, NOW)
        self.assertEqual(output["valid_georeferenced_stations"], 1)
        self.assertEqual(output["locations"][0]["stations"], [])

    def test_api_truncation_or_provider_error_is_unavailable(self):
        for body in ({"features": [], "exceededTransferLimit": True}, {"error": {"code": 400}}, [], {"features": "no"}):
            with self.subTest(body=body), self.assertRaises(EpagriGeoError):
                normalize_registry(body, PLACES, NOW)

    def test_cache_and_stale_fallback(self):
        previous = collect_geo(PLACES, NOW, fixture=GEO)
        later = (datetime.fromisoformat(NOW.replace("Z", "+00:00")) + timedelta(hours=1)).isoformat()
        with patch("observatorio.epagri_geo.fetch_registry", side_effect=AssertionError("cache must be reused")):
            result = collect_geo(PLACES, later, previous=previous)
        self.assertEqual(result["status"], "cached")
        late = (datetime.fromisoformat(NOW.replace("Z", "+00:00")) + timedelta(days=2)).isoformat()
        with patch("observatorio.epagri_geo.fetch_registry", side_effect=EpagriGeoError("unavailable")):
            result = collect_geo(PLACES, late, previous=previous)
        self.assertEqual(result["status"], "stale")
        very_late = (datetime.fromisoformat(NOW.replace("Z", "+00:00")) + timedelta(days=9)).isoformat()
        with patch("observatorio.epagri_geo.fetch_registry", side_effect=EpagriGeoError("unavailable")):
            result = collect_geo(PLACES, very_late, previous=previous)
        self.assertEqual(result["status"], "unavailable")


class EpagriAdvisories(unittest.TestCase):
    def test_official_rss_declared_validity_not_civil_defense_alert(self):
        data = parse_feed(FEED, NOW)
        self.assertEqual(len(data), 1)
        first = data[0]
        self.assertEqual(first["valid_from"], "2026-11-06T18:00:00Z")
        self.assertEqual(first["valid_until"], "2026-11-07T23:00:00Z")
        self.assertEqual(first["north_coast_scope"], "mentioned")
        self.assertEqual(first["window_status"], "explicit_in_publication")
        self.assertIn("not_civil_defense", first["notice_kind"])

    def test_cautious_missing_dates_and_regional_claim(self):
        sample = FEED.replace(b"Inicio", b"Inicio").replace(b"In\xc3\xadcio:", b"Per\xc3\xadodo:").replace(b"Litoral Norte", b"Oeste")
        result = parse_feed(sample, NOW)
        self.assertEqual(result[0]["window_status"], "not_confirmed")
        self.assertIsNone(result[0]["valid_from"])
        self.assertEqual(result[0]["north_coast_scope"], "other_regions_or_unclear")

    def test_invalid_rss_unsafe_url_and_duplicate(self):
        with self.assertRaises(EpagriNoticeError):
            parse_feed(b"<rss><!DOCTYPE bad><channel/>", NOW)
        with self.assertRaises(EpagriNoticeError):
            parse_feed(b"<html>not rss</html>", NOW)
        bad = FEED.replace(b"https://ciram.epagri.sc.gov.br/index.php/2026/11/05/aviso-teste/", b"https://example.com/steal")
        self.assertFalse(parse_feed(bad, NOW))
        doubled = FEED.replace(b"</channel>", FEED.split(b"<item>")[1].split(b"</item>")[0].join([b"<item>", b"</item>"]) + b"</channel>")
        # Duplicates by URL must not be published twice.
        self.assertEqual(len(parse_feed(doubled, NOW)), 1)

    def test_unavailable_not_equivalent_to_no_weather_risk(self):
        saved = collect_notices(NOW, fixture=FEED)
        nextday = (datetime.fromisoformat(NOW.replace("Z", "+00:00")) + timedelta(days=1)).isoformat()
        with patch("observatorio.epagri_notices._download", side_effect=EpagriNoticeError("offline")):
            stale = collect_notices(nextday, previous=saved)
        self.assertEqual(stale["status"], "stale")
        self.assertEqual(len(stale["notices"]), 1)
        oneweek = (datetime.fromisoformat(NOW.replace("Z", "+00:00")) + timedelta(days=7)).isoformat()
        with patch("observatorio.epagri_notices._download", side_effect=EpagriNoticeError("offline")):
            unavailable = collect_notices(oneweek, previous=saved)
        self.assertEqual(unavailable["status"], "unavailable")

    def test_repeated_build_and_static_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "dist"
            for _ in range(2):
                build(dest, fixture=ROOT / "tests" / "fixtures" / "open_meteo.json")
                validate(dest, fixture=True)
                self.assertEqual(json.loads((dest / "data" / "epagri_geo.json").read_text())["status"], "available")
                self.assertEqual(json.loads((dest / "data" / "epagri_notices.json").read_text())["status"], "available")
            with self.assertRaises(ValueError):
                validate(dest, fixture=False)


if __name__ == "__main__":
    unittest.main()
