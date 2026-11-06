"""Offline contracts for official CPTEC forecasts, SC Civil Defense and INMET networks."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from observatorio.config import load_locations
from observatorio.cptec import CptecError, parse_forecast, collect as collect_cptec
from observatorio.defesa_civil_sc import CivilDefenseError, parse_rss, parse_wp_json, collect as collect_defesa
from observatorio.inmet import normalize_catalog, nearby_catalog, CatalogError
from build_site import build, station_catalog_for_build
from validate_site import validate

LOCATIONS = load_locations(ROOT / "config" / "locations.json")
NOW = datetime(2026, 11, 5, 23, 40, tzinfo=timezone.utc)
STAMP = NOW.isoformat().replace("+00:00", "Z")
CPTEC = (ROOT / "tests/fixtures/cptec.xml").read_bytes()
RSS = (ROOT / "tests/fixtures/defesa_sc.xml").read_bytes()
AUTOMATIC = ROOT / "tests/fixtures/inmet_catalog.json"
CONVENTIONAL = ROOT / "tests/fixtures/inmet_conventional.json"


class TestCPTEC(unittest.TestCase):
    def test_forecast_observation_separation_and_temperature(self):
        result = parse_forecast(CPTEC, LOCATIONS[0], NOW)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["days"][1]["maximum_c"], 27)
        self.assertEqual(result["days"][0]["uv_index_max"], 11.5)
        self.assertNotIn("precipitation_observed_mm", str(result))

    def test_rejects_html_invalid_xml_and_dtd(self):
        for source in (b"<html>please enable JS</html>", b"broken", b"<!DOCTYPE city><cidade/>", b""):
            with self.subTest(source=source[:20]), self.assertRaises(CptecError):
                parse_forecast(source, LOCATIONS[0], NOW)

    def test_rejects_wrong_state(self):
        with self.assertRaisesRegex(CptecError, "another state"):
            parse_forecast(CPTEC.replace(b"<uf>SC</uf>", b"<uf>SP</uf>"), LOCATIONS[0], NOW)

    def test_stale_or_invalid_dates(self):
        stale = parse_forecast(CPTEC.replace(b"2026-11-05</atualizacao>", b"2026-11-01</atualizacao>"), LOCATIONS[0], NOW)
        self.assertEqual(stale["status"], "stale")
        with self.assertRaises(CptecError):
            parse_forecast(CPTEC.replace(b"2026-11-05</atualizacao>", b"2025-11-05</atualizacao>"), LOCATIONS[0], NOW)

    def test_impossible_temperature_or_no_forecast(self):
        with self.assertRaises(CptecError):
            parse_forecast(CPTEC.replace(b"<maxima>30</maxima>", b"<maxima>-90</maxima>").replace(b"<maxima>27</maxima>", b"<maxima>-90</maxima>"), LOCATIONS[0], NOW)

    def test_partial_feed_does_not_fabricate(self):
        with patch("observatorio.cptec.fetch_forecast", side_effect=CptecError("offline")):
            doc = collect_cptec(LOCATIONS[:2], STAMP)
        self.assertEqual(doc["status"], "unavailable")
        self.assertTrue(all(not x["days"] for x in doc["locations"]))
        self.assertIn("not_station_measurements", doc["kind"])


class TestDefesaCivil(unittest.TestCase):
    def test_official_rss_explicit_municipality_no_active_claim(self):
        posts = parse_rss(RSS, "alerta_publicado", LOCATIONS, NOW)
        self.assertEqual(len(posts), 1)
        self.assertIn("araquari", posts[0]["mentioned_location_ids"])
        self.assertIn("joinville", posts[0]["mentioned_location_ids"])
        self.assertEqual(posts[0]["validity_status"], "not_verified_from_publication_date")

    def test_wordpress_json_titles_and_xss_text(self):
        raw = json.dumps([{
            "link": "https://www.defesacivil.sc.gov.br/2026/11/05/boletim/",
            "date_gmt": "2026-11-05T21:00:00", "title": {"rendered": "Previsão para os próximos 5 dias (05/11)"},
            "excerpt": {"rendered": "<p>Previsão em São Francisco do Sul e Araquari.</p><script>bad()</script>"},
        }]).encode()
        result = parse_wp_json(raw, LOCATIONS, NOW)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["category"], "previsao_publicada")
        self.assertIn("sao-francisco-do-sul", result[0]["mentioned_location_ids"])
        self.assertIn("araquari", result[0]["mentioned_location_ids"])
        self.assertNotIn("<script>", result[0]["summary"])

    def test_malicious_links_are_discarded(self):
        altered = RSS.replace(b"https://www.defesacivil.sc.gov.br/2026/11/05/alerta-chuva-forte-araquari/", b"https://example.net/fake/")
        self.assertEqual(parse_rss(altered, "alerta_publicado", LOCATIONS, NOW), [])

    def test_outdated_post_does_not_look_current(self):
        altered = RSS.replace(b"Thu, 05 Nov 2026 20:20:00 -0300", b"Thu, 05 Nov 2020 20:20:00 -0300")
        self.assertEqual(parse_rss(altered, "alerta_publicado", LOCATIONS, NOW), [])

    def test_bad_feed_is_unusable(self):
        with self.assertRaises(CivilDefenseError):
            parse_rss(b"<!DOCTYPE html><html></html>", "alerta_publicado", LOCATIONS, NOW)

    def test_no_network_returns_explicit_unavailable(self):
        with patch("observatorio.defesa_civil_sc._download", side_effect=CivilDefenseError("offline")):
            data = collect_defesa(LOCATIONS, STAMP)
        self.assertEqual(data["status"], "unavailable")
        self.assertEqual(data["publications"], [])
        self.assertEqual(data["municipal_source"]["integration"], "official_contact_page_not_automatic_warning_feed")

    def test_fallback_rss_when_wp_unavailable(self):
        def fake_download(url):
            if url.endswith("/categoria/alerta/feed/"):
                return RSS
            raise CivilDefenseError("blocked")
        with patch("observatorio.defesa_civil_sc._download", side_effect=fake_download):
            data = collect_defesa(LOCATIONS, STAMP)
        self.assertEqual(data["status"], "partial")
        self.assertEqual(len(data["publications"]), 1)

    def test_fixture_returns_deterministic_entries(self):
        fixture = {"alerta_publicado": RSS.decode()}
        a = collect_defesa(LOCATIONS, STAMP, fixture=fixture)
        b = collect_defesa(LOCATIONS, STAMP, fixture=fixture)
        self.assertEqual(a, b)
        self.assertEqual(a["status"], "available")


class TestStationCatalogs(unittest.TestCase):
    def test_conventional_catalog_numeric_codes_and_nearest(self):
        conventional = normalize_catalog(json.loads(CONVENTIONAL.read_text()), network_type="convencional")
        automatic = normalize_catalog(json.loads(AUTOMATIC.read_text()))
        data = nearby_catalog(LOCATIONS[:1], automatic + conventional, STAMP)
        self.assertTrue(any(s["network_type"] == "convencional" for s in data["locations"][0]["stations"]))
        self.assertTrue(any(s["network_type"] == "automatica" for s in data["locations"][0]["stations"]))

    def test_bad_network_type_fails(self):
        with self.assertRaises(ValueError):
            normalize_catalog(json.loads(CONVENTIONAL.read_text()), network_type="secret")

    def test_automatic_can_work_when_conventional_down(self):
        with patch("build_site.fetch_catalog", side_effect=[normalize_catalog(json.loads(AUTOMATIC.read_text())), CatalogError("down")]):
            result = station_catalog_for_build(LOCATIONS, None, None)
        self.assertEqual(result["catalog_status"], "available")
        self.assertEqual(result["conventional_catalog_status"], "unavailable")

    def test_offline_fixture_full_build_includes_new_datasets(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dist"
            build(output, fixture=ROOT / "tests/fixtures/open_meteo.json")
            validate(output, fixture=True)
            a = json.loads((output / "data/cptec.json").read_text())
            b = json.loads((output / "data/defesa_civil_sc.json").read_text())
            c = json.loads((output / "data/stations.json").read_text())
            self.assertEqual(a["status"], "available")
            self.assertEqual(b["status"], "available")
            self.assertEqual(c["conventional_catalog_status"], "available")


if __name__ == "__main__":
    unittest.main()
