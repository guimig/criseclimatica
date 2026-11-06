"""Epagri/Ciram editorial forecasts, distinct from alerts and point models."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from observatorio.epagri_bulletins import (KIND, BulletinError, _safe, collect, parse_feed, unavailable)

STAMP='2026-11-06T12:00:00Z'
RAW=(ROOT/'tests/fixtures/epagri_bulletins.xml').read_bytes()


class EpagriEditorialTests(unittest.TestCase):
    def test_distinguishes_editorial_forecast_and_utc_publication(self):
        out=collect(STAMP,fixture=RAW)
        self.assertEqual(out['status'],'available')
        self.assertEqual(out['kind'],KIND)
        self.assertEqual(len(out['bulletins']),2)
        self.assertEqual(out['bulletins'][0]['bulletin_kind'],'ten_day_tendency')
        self.assertEqual(out['bulletins'][0]['published_at'],'2026-11-05T14:00:00Z')
        self.assertNotIn('<p>',str(out['bulletins']))
        self.assertTrue(all('not_station_observation_or_civil_defense_alert' in b['data_kind'] for b in out['bulletins']))

    def test_bogus_xml_doctype_and_non_official_links_rejected(self):
        for payload in (b'broken',b'<!DOCTYPE rss><rss/>',b'<!ENTITY foo "bar"><rss/>'):
            with self.subTest(payload=payload),self.assertRaises(BulletinError):
                parse_feed(payload,STAMP)
        self.assertFalse(_safe('https://ciram.epagri.sc.gov.br.attacker.org/x'))
        self.assertFalse(_safe('http://ciram.epagri.sc.gov.br/index.php/x'))

    def test_empty_feed_not_mistaken_for_no_risk(self):
        result=collect(STAMP,fixture=b'<rss version="2.0"><channel></channel></rss>')
        self.assertEqual(result['status'],'no_recent_bulletins')
        self.assertIn('nao e alerta',result['note'])

    def test_short_cache_and_failure_fallback(self):
        first=collect(STAMP,fixture=RAW)
        newer='2026-11-06T13:30:00Z'
        with patch('observatorio.epagri_bulletins._fetch',side_effect=AssertionError('not necessary')):
            cached=collect(newer,previous=first)
        self.assertEqual(cached['status'],'cached')
        with patch('observatorio.epagri_bulletins._fetch',side_effect=BulletinError('down')):
            stale=collect('2026-11-07T00:00:00Z',previous=first)
        self.assertEqual(stale['status'],'stale')
        self.assertEqual(stale['retrieved_at'],first['retrieved_at'])
        with patch('observatorio.epagri_bulletins._fetch',side_effect=BulletinError('down')):
            gone=collect('2026-11-08T12:00:00Z',previous=first)
        self.assertEqual(gone['status'],'unavailable')

    def test_fixture_repeated_is_idempotent(self):
        self.assertEqual(collect(STAMP,fixture=RAW),collect(STAMP,fixture=RAW))

    def test_future_rss_items_never_claim_current_forecast(self):
        raw=RAW.replace(b'2026',b'2030')
        self.assertFalse(parse_feed(raw,STAMP))


if __name__=='__main__':unittest.main()
