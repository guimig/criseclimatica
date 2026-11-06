"""Offline regression tests for official delayed INMET ZIP and SC publications."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from observatorio.config import load_locations
from observatorio.inmet import nearby_catalog, normalize_catalog
from observatorio.inmet_archive import (
    InmetArchiveError, collect_archive, nearby_station_codes, parse_annual_zip,
    station_metadata_from_zip, unavailable_archive,
)
from observatorio.defesa_civil_sc import collect, parse_public_page, parse_wp_json
from build_site import build

LOCATIONS = load_locations(ROOT / "config" / "locations.json")
STATIONS = normalize_catalog(json.loads((ROOT / "tests/fixtures/inmet_catalog.json").read_text()))
NOW = datetime(2026, 11, 5, 14, tzinfo=timezone.utc)
STAMP = NOW.isoformat().replace("+00:00", "Z")
CATALOG = nearby_catalog(LOCATIONS, STATIONS, STAMP)


def archive_zip(*, missing: int | None = None, conflict: bool = False, different_year: bool = False) -> bytes:
    content = io.BytesIO()
    base = datetime(2026 if not different_year else 2025, 10, 31, tzinfo=timezone.utc)
    text = (
        "REGIAO:;S;\nUF:;SC;\nESTACAO:;ARAUQUARI;\nCODIGO (WMO):;A001;\nLATITUDE:;-26,37;\nLONGITUDE:;-48,72;\nALTITUDE:;10;\nDATA DE FUNDACAO:;2020-01-01;\n"
        "Data (YYYY-MM-DD);Hora (UTC);PRECIPITAÇÃO TOTAL, HORÁRIO (mm);TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);\n"
    )
    for i in range(24):
        val = "" if missing == i else "0,2" if i == 0 else "0"
        text += f"{base.date().isoformat()};{i:02d}00 UTC;{val};25,1;\n"
    if conflict:
        text += f"{base.date().isoformat()};0000 UTC;12;25,1;\n"
    with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("INMET_S_SC_A001_ARAUQUARI_01-01-2026_A_31-10-2026.CSV", text.encode("latin-1", errors="replace"))
        archive.writestr("INMET_N_GO_A999_OUTRA_01-01-2026_A_31-10-2026.CSV", b"irrelevant")
    return content.getvalue()


class InmetAnnualArchiveTests(unittest.TestCase):
    def test_selects_only_nearby_automatic_catalog_stations(self):
        selected = nearby_station_codes(CATALOG)
        self.assertIn("A001", selected)
        self.assertIn("A002", selected)
        self.assertNotIn("A003", selected)
        self.assertNotIn("83897", selected)

    def test_complete_measured_rain_not_realtime(self):
        rows = parse_annual_zip(archive_zip(), nearby_station_codes(CATALOG), NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "A001")
        self.assertEqual(rows[0]["days"][0]["rain_total_complete_mm"], 0.2)
        self.assertEqual(rows[0]["days"][0]["rain_measured_hours"], 24)
        result = collect_archive(LOCATIONS, CATALOG, STAMP, fixture_zip=archive_zip())
        self.assertEqual(result["status"], "available")
        self.assertIn("delayed", result["kind"])
        self.assertEqual(result["latest_observation_at"], "2026-10-31T23:00:00Z")
        self.assertTrue(result["locations"][0]["stations"])

    def test_hourly_gaps_are_not_turned_into_complete_total(self):
        rows = parse_annual_zip(archive_zip(missing=5), nearby_station_codes(CATALOG), NOW)
        day = rows[0]["days"][0]
        self.assertEqual(day["rain_measured_hours"], 23)
        self.assertIsNone(day["rain_total_complete_mm"])
        self.assertEqual(day["rain_sum_available_hours_mm"], 0.2)

    def test_conflicting_duplicate_rejected(self):
        with self.assertRaisesRegex(InmetArchiveError, "Conflicting"):
            parse_annual_zip(archive_zip(conflict=True), nearby_station_codes(CATALOG), NOW)

    def test_zip_traversal_is_not_extracted(self):
        raw = archive_zip()
        with tempfile.TemporaryDirectory() as folder:
            # Parser never writes to paths from ZIP entries.
            self.assertEqual(len(parse_annual_zip(raw, nearby_station_codes(CATALOG), NOW)), 1)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_invalid_and_wrong_year(self):
        with self.assertRaises(InmetArchiveError):
            parse_annual_zip(b"not zip", nearby_station_codes(CATALOG), NOW)
        self.assertFalse(parse_annual_zip(archive_zip(different_year=True), nearby_station_codes(CATALOG), NOW))

    def test_cached_publication_skips_network_and_preserves_original_timestamp(self):
        first = collect_archive(LOCATIONS, CATALOG, STAMP, fixture_zip=archive_zip())
        next_time = (NOW + timedelta(hours=3)).isoformat().replace("+00:00", "Z")
        with patch("observatorio.inmet_archive._download_year", side_effect=AssertionError("No network")):
            again = collect_archive(LOCATIONS, CATALOG, next_time, previous=first)
        self.assertEqual(again["status"], "cached")
        self.assertEqual(again["retrieved_at"], STAMP)
        self.assertEqual(again["latest_observation_at"], first["latest_observation_at"])

    def test_download_failure_preserves_dated_previous_and_rate_limits_retries(self):
        first = collect_archive(LOCATIONS, CATALOG, STAMP, fixture_zip=archive_zip())
        later = (NOW + timedelta(days=8)).isoformat().replace("+00:00", "Z")
        with patch("observatorio.inmet_archive._download_year", side_effect=InmetArchiveError("source unavailable")):
            stale = collect_archive(LOCATIONS, CATALOG, later, previous=first)
        self.assertEqual(stale["status"], "cached")
        self.assertEqual(stale["last_attempt_at"], later)
        next_time = (NOW + timedelta(days=8, hours=3)).isoformat().replace("+00:00", "Z")
        with patch("observatorio.inmet_archive._download_year", side_effect=AssertionError("Retry suppressed")):
            second = collect_archive(LOCATIONS, CATALOG, next_time, previous=stale)
        self.assertIn(second["status"], ("cached", "stale"))

    def test_no_catalog_recovers_station_metadata_from_zip(self):
        result = collect_archive(LOCATIONS, {"locations": []}, STAMP, fixture_zip=archive_zip())
        self.assertEqual(result["status"], "available")
        self.assertIn("A001", [station["code"] for station in result["stations"]])
        self.assertEqual(result["station_discovery_version"], 2)

    def test_legacy_cached_catalog_missing_network_type(self):
        old = nearby_catalog(LOCATIONS, STATIONS, STAMP)
        for row in old["locations"]:
            for station in row["stations"]:
                station.pop("network_type", None)
        self.assertIn("A001", nearby_station_codes(old))
        result = collect_archive(LOCATIONS, old, STAMP, fixture_zip=archive_zip())
        self.assertEqual(result["status"], "available")

    def test_zip_header_rejects_unsupported_or_mismatched_station(self):
        with zipfile.ZipFile(io.BytesIO(archive_zip()), "r") as archive:
            headers = station_metadata_from_zip(archive, LOCATIONS)
        self.assertEqual(list(headers), ["A001"])
        self.assertEqual(headers["A001"]["metadata_source"], "inmet_annual_csv_header")
        self.assertLess(headers["A001"]["distance_km"], 5)

    def test_inmet_archive_no_local_stations_is_not_no_rain(self):
        distant = [dict(LOCATIONS[0], latitude=0.0, longitude=0.0)]
        result = collect_archive(distant, {"locations": []}, STAMP, fixture_zip=archive_zip())
        self.assertEqual(result["status"], "no_nearby_stations")
        self.assertEqual(result["station_discovery_version"], 2)
        self.assertNotIn("rain_total_complete_mm", str(result))

    def test_retry_legacy_no_station_result_is_not_suppressed(self):
        old = unavailable_archive(STAMP, "no_nearby_stations")
        result = collect_archive(LOCATIONS, {"locations": []}, STAMP,
                                 previous=old, fixture_zip=archive_zip())
        self.assertEqual(result["status"], "available")

    def test_empty_unconfigured_archive_never_claims_zero_rainfall(self):
        result = unavailable_archive(STAMP)
        self.assertEqual(result["stations"], [])
        self.assertNotIn("rain_mm", result)


class CivilDefenseResilienceTests(unittest.TestCase):
    def test_wordpress_local_date_not_assumed_utc(self):
        post = [{"link": "https://www.defesacivil.sc.gov.br/2026/11/05/nota-meteorologica/",
                 "title": {"rendered": "Nota meteorológica SDC/SC 05/11"},
                 "excerpt": {"rendered": "Araquari e região"}, "date": "2026-11-05T08:30:00", "date_gmt": ""}]
        rows = parse_wp_json(json.dumps(post).encode(), LOCATIONS, NOW)
        self.assertEqual(rows[0]["published_at"], "2026-11-05T11:30:00Z")
        self.assertIn("araquari", rows[0]["mentioned_location_ids"])

    def test_public_html_fallback_is_not_exact_timestamp_or_active_alert(self):
        html = b'<html><h2><a href="https://www.defesacivil.sc.gov.br/2026/11/05/atencao-hidrometeorologica/">Atencao Hidrometeorologica - previsao de chuva</a></h2><h2><a href="https://evil.com/2026/11/05/risco">Alerta falso</a></h2></html>'
        rows = parse_public_page(html, LOCATIONS, NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["publication_precision"], "calendar_day_from_url_not_exact_time")
        self.assertEqual(rows[0]["validity_status"], "not_verified_from_publication_date")

    def test_previous_publications_stay_explicitly_stale_when_source_fails(self):
        rss = '<?xml version="1.0"?><rss><channel><item><title>ATENÇÃO - temporais em Araquari</title><link>https://www.defesacivil.sc.gov.br/2026/11/05/alerta/</link><description>Araquari</description><pubDate>Thu, 05 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>'
        previous = collect(LOCATIONS, STAMP, fixture={"alerta_publicado": rss})
        with patch("observatorio.defesa_civil_sc._download", side_effect=Exception("unexpected")):
            # Unexpected exceptions remain visible instead of being silently swallowed.
            with self.assertRaises(Exception):
                collect(LOCATIONS, STAMP, previous=previous)
        from observatorio.defesa_civil_sc import CivilDefenseError
        with patch("observatorio.defesa_civil_sc._download", side_effect=CivilDefenseError("Public bulletin unavailable: http_403")):
            result = collect(LOCATIONS, STAMP, previous=previous)
        self.assertEqual(result["status"], "stale")
        self.assertEqual(len(result["publications"]), 1)
        self.assertEqual(result["retrieval_method"], "previously_published_publications")
        self.assertTrue(result["source_diagnostics"])
        self.assertNotIn("active", result["status"])

    def test_unavailable_without_previous_is_not_no_alert(self):
        from observatorio.defesa_civil_sc import CivilDefenseError
        with patch("observatorio.defesa_civil_sc._download", side_effect=CivilDefenseError("Public bulletin unavailable: http_403")):
            result = collect(LOCATIONS, STAMP)
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["publications"])
        self.assertTrue(result["source_diagnostics"])

    def test_fixture_build_new_dataset_stays_synthetic(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "dist"
            build(out, fixture=ROOT / "tests/fixtures/open_meteo.json")
            archive = json.loads((out / "data/inmet_archive.json").read_text())
            self.assertEqual(archive["status"], "fixture_mode")


if __name__ == "__main__":
    unittest.main()
