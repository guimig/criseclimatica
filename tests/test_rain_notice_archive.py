"""Regression tests for authenticated INMET observations and notice history."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from observatorio.config import load_locations
from observatorio.alerts import normalize_alerts, unavailable_alerts
from observatorio.inmet import normalize_catalog, nearby_catalog
from observatorio.inmet_rain import (
    RainSourceError, candidates, normalize_station_rows, collect_rain,
    fetch_station_rows,
)
from observatorio.notice_archive import merge_notice_archive
from build_site import build
from validate_site import validate

NOW = datetime(2026, 11, 5, 13, 0, tzinfo=timezone.utc)
STAMP = NOW.isoformat(timespec='seconds').replace('+00:00', 'Z')
LOCATIONS = load_locations(ROOT / 'config' / 'locations.json')
CATALOG = nearby_catalog(LOCATIONS,
    normalize_catalog(json.loads((ROOT / 'tests/fixtures/inmet_catalog.json').read_text())), STAMP)
WARNINGS = normalize_alerts(json.loads((ROOT / 'tests/fixtures/inmet_alerts.json').read_text()), LOCATIONS, STAMP)


def rain_data(code: str = 'A001', now: datetime = NOW) -> list[dict]:
    result = []
    for n in range(24):
        at = now - timedelta(hours=24 - n)
        result.append({'CD_ESTACAO': code, 'DT_MEDICAO': at.strftime('%Y-%m-%d'),
                       'HR_MEDICAO': at.strftime('%H%M'), 'CHUVA': '0.5'})
    return result


class TestRainStation(unittest.TestCase):
    def test_station_candidates_bounded_and_geographic(self):
        selected = candidates(CATALOG, LOCATIONS)
        self.assertTrue(selected)
        self.assertIn('A001', [station['code'] for station in selected])
        self.assertLessEqual(len(selected), 5)
        self.assertTrue(all(row['distance_km'] <= 90 for row in selected))
        self.assertEqual(candidates({'kind': 'wrong', 'locations': []}, LOCATIONS), [])

    def test_precipitation_complete_hours_are_not_model_estimates(self):
        measure = normalize_station_rows(rain_data(), 'A001', NOW)
        self.assertEqual(measure['rain_last_hour_mm'], 0.5)
        self.assertEqual(measure['rain_last_24_readings_mm'], 12.0)
        self.assertTrue(measure['rain_24h_complete'])
        self.assertEqual(measure['hourly_coverage_24'], 24)
        self.assertEqual(measure['observed_at'], '2026-11-05T12:00:00Z')
        self.assertIn('not_homogenized', measure['quality'])

    def test_missing_hour_never_implies_full_24h_rainfall(self):
        sample = rain_data()
        sample[2]['CHUVA'] = '9999'
        reading = normalize_station_rows(sample, 'A001', NOW)
        self.assertIsNone(reading['rain_last_24_readings_mm'])
        self.assertEqual(reading['hourly_coverage_24'], 23)
        self.assertFalse(reading['rain_24h_complete'])
        sample[-1]['CHUVA'] = None
        self.assertIsNone(normalize_station_rows(sample, 'A001', NOW)['rain_last_hour_mm'])

    def test_conflicting_duplicate_rejected_and_repeated_duplicate_accepted(self):
        sample = rain_data()
        self.assertEqual(len(sample), 24)
        self.assertEqual(normalize_station_rows(sample + [dict(sample[-1])], 'A001', NOW)['hourly_coverage_24'], 24)
        with self.assertRaisesRegex(RainSourceError, 'Conflicting'):
            normalize_station_rows(sample + [{**sample[-1], 'CHUVA': '3'}], 'A001', NOW)

    def test_stale_invalid_or_other_stations_never_fabricate_readings(self):
        self.assertIsNone(normalize_station_rows(rain_data(now=NOW - timedelta(days=1)), 'A001', NOW))
        self.assertIsNone(normalize_station_rows(rain_data(code='A333'), 'A001', NOW))
        with self.assertRaises(RainSourceError):
            normalize_station_rows('not-list', 'A001', NOW)
        self.assertIsNone(normalize_station_rows([], 'A001', NOW))

    def test_optional_token_and_station_errors(self):
        self.assertEqual(collect_rain(LOCATIONS, CATALOG, STAMP, token='', now=NOW)['status'], 'not_configured')
        def stub(code, token, now):
            if code == 'A001': return rain_data(code, now)
            raise RainSourceError('Station unavailable')
        feed = collect_rain(LOCATIONS, CATALOG, STAMP, token='secret', now=NOW, fetcher=stub)
        self.assertEqual(feed['kind'], 'inmet_automatic_station_hourly_observed_rain_unvalidated')
        self.assertEqual(feed['status'], 'available')
        self.assertEqual(len(feed['stations']), 1)
        place = next(x for x in feed['locations'] if x['location_id'] == 'araquari')
        self.assertEqual(place['stations'][0]['code'], 'A001')
        self.assertNotIn('secret', json.dumps(feed))
        offline = collect_rain(LOCATIONS, CATALOG, STAMP, token='secret', now=NOW,
                               fetcher=lambda *args: (_ for _ in ()).throw(RainSourceError('fail')))
        self.assertEqual(offline['status'], 'unavailable')
        self.assertEqual(offline['stations'], [])

    def test_authenticated_request_never_displays_secret_even_with_http_error(self):
        class Opener:
            def open(self, req, timeout):
                raise HTTPError(req.full_url, 401, 'unauthorized', {}, None)
        with patch('observatorio.inmet_rain.build_opener', return_value=Opener()):
            with self.assertRaises(RainSourceError) as ctx:
                fetch_station_rows('A001', 'TOPSECRET', NOW)
        self.assertNotIn('TOPSECRET', str(ctx.exception))
        with self.assertRaises(RainSourceError):
            fetch_station_rows('invalid', 'token', NOW)


class TestNoticeArchive(unittest.TestCase):
    def test_archives_official_notices_without_claiming_confirmed_disaster(self):
        archive = merge_notice_archive(None, WARNINGS, now=NOW)
        self.assertEqual(archive['kind'], 'archive_of_inmet_notices_not_confirmed_weather_events')
        self.assertEqual(len(archive['records']), 3)
        record = next(x for x in archive['records'] if x['id'] == '3100')
        self.assertIn('araquari', record['municipality_ids'])
        self.assertTrue(record['present_in_latest_successful_feed'])
        self.assertEqual(archive, merge_notice_archive(archive, WARNINGS, now=NOW))

    def test_missing_from_successful_feed_does_not_prove_cancelation(self):
        initial = merge_notice_archive(None, WARNINGS, now=NOW)
        future = NOW + timedelta(hours=2)
        empty = normalize_alerts({'hoje': [], 'futuro': []}, LOCATIONS, future.isoformat())
        merged = merge_notice_archive(initial, empty, now=future)
        self.assertEqual(len(merged['records']), len(initial['records']))
        self.assertFalse(all(row['present_in_latest_successful_feed'] for row in merged['records']))
        unavailable = merge_notice_archive(merged, unavailable_alerts(LOCATIONS, future.isoformat()), now=future)
        self.assertEqual(unavailable['records'], merged['records'])
        self.assertEqual(unavailable['feed_status'], 'unavailable')

    def test_new_revision_overwrites_metadata_but_retains_first_seen(self):
        first = merge_notice_archive(None, WARNINGS, now=NOW)
        revised = json.loads(json.dumps(WARNINGS))
        for place in revised['locations']:
            for a in place['alerts']:
                if a['id'] == '3100':
                    a['revision'] = 10
                    a['type'] = 'Chuva intensa revisada'
        new = merge_notice_archive(first, revised, now=NOW + timedelta(hours=1))
        row = next(x for x in new['records'] if x['id'] == '3100')
        self.assertEqual(row['revision'], 10)
        self.assertEqual(row['type'], 'Chuva intensa revisada')
        self.assertEqual(row['first_seen_at'], STAMP)

    def test_old_entries_retired_and_corrupt_prior_rejected(self):
        earlier = NOW - timedelta(days=400)
        prior = merge_notice_archive(None, WARNINGS, now=earlier)
        current = merge_notice_archive(prior, normalize_alerts({'hoje': [], 'futuro': []}, LOCATIONS, STAMP), now=NOW)
        self.assertEqual(current['records'], [])
        active = merge_notice_archive(None, WARNINGS, now=NOW)
        bad = {**active, 'records': active['records'] + [active['records'][0]]}
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            merge_notice_archive(bad, WARNINGS, now=NOW)
        with self.assertRaises(ValueError):
            merge_notice_archive({'kind': 'wrong'}, WARNINGS, now=NOW)

    def test_missing_archive_after_previous_publication_is_fatal(self):
        def previous(_base, path, **_kwargs):
            if path == 'data/latest.json':
                return {'schema_version': 1, 'notice_archive_published': True}
            return None
        with tempfile.TemporaryDirectory() as folder, patch('build_site.fetch_previous_json', side_effect=previous):
            with self.assertRaisesRegex(RuntimeError, 'refusing history loss'):
                build(Path(folder) / 'dist', previous_url='https://guimig.github.io/criseclimatica/')

    def test_fixture_build_and_validation_contain_new_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            dist = Path(folder) / 'dist'
            build(dist, fixture=ROOT / 'tests/fixtures/open_meteo.json')
            validate(dist, fixture=True)
            archive = json.loads((dist / 'data/notice_history.json').read_text())
            rain = json.loads((dist / 'data/rain_gauges.json').read_text())
            self.assertTrue(archive['records'])
            self.assertEqual(rain['status'], 'fixture_mode')
            with self.assertRaises(ValueError):
                validate(dist, fixture=False)


if __name__ == '__main__':
    unittest.main()

