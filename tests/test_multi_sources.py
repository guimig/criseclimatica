"""Strict offline coverage for independent NASA and authenticated Cemaden feeds."""
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
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from observatorio.config import load_locations
from observatorio.cemaden import collect as cemaden_collect, normalize as cemaden_normalize, fetch as cemaden_fetch, CemadenError
from observatorio.inmet_rain import collect_rain, RainSourceError, fetch_station_rows
from observatorio.inmet import normalize_catalog, nearby_catalog
from observatorio.nasa_power import collect as nasa_collect, normalize as nasa_normalize, unavailable as nasa_unavailable, NasaSourceError, fetch as nasa_fetch
from build_site import build
from validate_site import validate

NOW = datetime(2026, 11, 5, 13, 10, tzinfo=timezone.utc)
STAMP = NOW.isoformat(timespec="seconds").replace("+00:00", "Z")
PLACES = load_locations(ROOT / "config/locations.json")
POINT = PLACES[0]


def nasa_raw():
    return {"header": {"fill_value": -999}, "properties": {"parameter": {
        "PRECTOTCORR": {"20261031": 0.0, "20261101": 14.3, "20261102": -999.0, "20261103": 2.5},
        "T2M": {"20261031": 24.0, "20261101": 21.2, "20261102": 22.1, "20261103": -999.0},
    }}}


class NasaTests(unittest.TestCase):
    def test_independent_grid_estimates_are_not_gauges(self):
        dataset = nasa_normalize(nasa_raw(), POINT, STAMP, now=NOW)
        self.assertIn("not_station_observation", dataset["kind"])
        self.assertEqual(dataset["status"], "available")
        self.assertEqual(dataset["point"]["location_id"], "araquari")
        self.assertEqual(dataset["daily"][0]["rain_estimated_mm_day"], 0)
        self.assertIsNone(dataset["daily"][2]["rain_estimated_mm_day"])
        self.assertEqual(dataset["latest_data_day_utc"], "2026-11-03")
        self.assertEqual(dataset["days_since_latest"], 2)

    def test_invalid_payload_and_missing_values(self):
        for response in ({}, [], {"properties": {"parameter": {"T2M": {}}}},
                         {"properties": {"parameter": {"T2M": {"20261101": -999}, "PRECTOTCORR": {"20261101": -999}}}}):
            with self.subTest(response=response), self.assertRaises(NasaSourceError):
                nasa_normalize(response, POINT, STAMP, now=NOW)

    def test_cache_prevents_multiple_fetches_under_24_hours(self):
        first = nasa_collect(POINT, STAMP, now=NOW, fetcher=lambda p,n:nasa_raw())
        again = nasa_collect(POINT, STAMP, first, now=NOW + timedelta(hours=2),
                             fetcher=lambda p,n: (_ for _ in ()).throw(AssertionError("Unneeded request")))
        self.assertEqual(again["status"], "cached")
        self.assertEqual(again["daily"], first["daily"])

    def test_outage_preserves_only_recently_retrieved_data(self):
        initial = nasa_collect(POINT, STAMP, now=NOW, fetcher=lambda p,n:nasa_raw())
        down = lambda p,n: (_ for _ in ()).throw(NasaSourceError("offline"))
        stale = nasa_collect(POINT, STAMP, initial, now=NOW+timedelta(hours=26), fetcher=down)
        self.assertEqual(stale["status"], "stale")
        self.assertEqual(stale["retrieved_at"], initial["retrieved_at"])
        expired = nasa_collect(POINT, STAMP, initial, now=NOW+timedelta(hours=77), fetcher=down)
        self.assertEqual(expired["status"], "unavailable")
        self.assertEqual(expired["daily"], [])

    def test_previous_other_location_not_reused(self):
        old = nasa_collect(POINT, STAMP, now=NOW, fetcher=lambda p,n:nasa_raw())
        other = {**POINT, "id": "other", "longitude": -50}
        fresh = nasa_collect(other, STAMP, old, now=NOW+timedelta(hours=2), fetcher=lambda p,n:nasa_raw())
        self.assertEqual(fresh["point"]["location_id"], "other")
        self.assertEqual(fresh["status"], "available")

    def test_nasa_url_has_one_point_and_explicit_utc(self):
        class Reply:
            status = 200
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,n): return json.dumps(nasa_raw()).encode()
        def stub(req,timeout):
            self.assertIn("time-standard=UTC",req.full_url)
            self.assertIn("latitude=-26.3750",req.full_url)
            self.assertIn("community=AG",req.full_url)
            return Reply()
        with patch('observatorio.nasa_power.urlopen',side_effect=stub):
            self.assertIn('properties', nasa_fetch(POINT,NOW))


class CemadenTests(unittest.TestCase):
    def test_exact_ibge_and_fresh_utc_only(self):
        data = [{"codibge":4201307,"codestacao":"420130701A","datahora":"2026-11-05T12:55:00.0000","acc1hr":0.0,"acc24hr":35.6},
                {"codibge":4209102,"codestacao":"420910204A","datahora":"2026-11-05T13:00:00","acc1hr":17,"acc24hr":38},
                {"codibge":4201307,"codestacao":"420130702A","datahora":"2026-11-04T03:00:00","acc1hr":44,"acc24hr":99}]
        results = cemaden_normalize(data,"4201307",NOW)
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]["rain_1h_mm"],0)
        self.assertEqual(results[0]["rain_24h_mm"],35.6)
        self.assertEqual(results[0]["observed_at"],"2026-11-05T12:55:00Z")

    def test_missing_values_not_interpreted_as_zero(self):
        x=[{"codibge":4201307,"codestacao":"420130701A","datahora":"2026-11-05T13:00:00","acc1hr":-999,"acc24hr":None}]
        self.assertEqual(cemaden_normalize(x,"4201307",NOW),[])
        with self.assertRaises(CemadenError): cemaden_normalize({},"4201307",NOW)

    def test_not_configured_is_explicit(self):
        result=cemaden_collect(PLACES,STAMP,token="",now=NOW)
        self.assertEqual(result["status"],"not_configured")
        self.assertEqual(result["municipalities_checked"],0)
        self.assertFalse(any(loc["stations"] for loc in result["locations"]))

    def test_success_and_empty_municipalities(self):
        def fetcher(ibge,token):
            return [{"codibge":int(ibge),"codestacao":ibge+"A","datahora":"2026-11-05T12:00:00","acc1hr":2,"acc24hr":3}] if ibge=="4201307" else []
        result=cemaden_collect(PLACES,STAMP,token="test-jwt",now=NOW,fetcher=fetcher)
        self.assertEqual(result["status"],"available")
        self.assertEqual(len(result["locations"][0]["stations"]),1)
        self.assertEqual(result["municipalities_checked"],7)
        self.assertNotIn("test-jwt",json.dumps(result))

    def test_all_access_denied_is_not_absence_of_rain(self):
        def deny(ibge,token): raise CemadenError("Auth blocked","access_restricted")
        result=cemaden_collect(PLACES,STAMP,token="bad",now=NOW,fetcher=deny)
        self.assertEqual(result["status"],"access_restricted")
        self.assertEqual(result["municipalities_failed"],7)

    def test_valid_empty_query_no_recent_data(self):
        result=cemaden_collect(PLACES,STAMP,token="valid",now=NOW,fetcher=lambda *_:[])
        self.assertEqual(result["status"],"no_recent_data")

    def test_jwt_is_header_and_4xx_url_is_not_disclosed(self):
        class Opener:
            def open(self,request,timeout):
                self.url=request.full_url
                self.assertion = request.headers.get('Token')
                raise HTTPError(request.full_url,403,'Forbidden',{},None)
        opener=Opener()
        with patch('observatorio.cemaden.build_opener',return_value=opener):
            with self.assertRaises(CemadenError) as context:
                cemaden_fetch('4201307','PRIVATE_JWT')
        self.assertIn('codibge=4201307',opener.url)
        self.assertNotIn('PRIVATE_JWT',opener.url)
        self.assertEqual(opener.assertion,'PRIVATE_JWT')
        self.assertNotIn('PRIVATE_JWT',str(context.exception))
        self.assertEqual(context.exception.reason,'access_restricted')


class InmetDiagnosticsTests(unittest.TestCase):
    def test_no_token_is_distinct_from_invalid_token(self):
        from observatorio.inmet_rain import unavailable
        self.assertEqual(unavailable(PLACES, STAMP, 'not_configured')['diagnostic'],'token_not_configured')
        stations=nearby_catalog(PLACES,normalize_catalog(json.loads((ROOT/'tests/fixtures/inmet_catalog.json').read_text())),STAMP)
        all_denied=lambda *_: (_ for _ in ()).throw(RainSourceError('blocked','access_restricted'))
        outcome=collect_rain(PLACES,stations,STAMP,token='SECRET',now=NOW,fetcher=all_denied)
        self.assertEqual(outcome['status'],'access_restricted')
        self.assertEqual(outcome['failure_reasons']['access_restricted'],outcome['stations_checked'])
        self.assertNotIn('SECRET',json.dumps(outcome))

    def test_no_recent_data_not_zero_rainfall(self):
        stations=nearby_catalog(PLACES,normalize_catalog(json.loads((ROOT/'tests/fixtures/inmet_catalog.json').read_text())),STAMP)
        outcome=collect_rain(PLACES,stations,STAMP,token='SECRET',now=NOW,fetcher=lambda *_:[])
        self.assertEqual(outcome['status'],'no_recent_data')
        self.assertFalse(outcome['stations'])

    def test_http_204_classified_without_secret(self):
        class Reply:
            status=204
            def __enter__(self): return self
            def __exit__(self,*args): pass
        class Opener:
            def open(self,req,timeout): return Reply()
        with patch('observatorio.inmet_rain.build_opener',return_value=Opener()):
            with self.assertRaises(RainSourceError) as ctx:
                fetch_station_rows('A001','PRIVATE_TOKEN',NOW)
        self.assertEqual(ctx.exception.reason,'no_recent_data')
        self.assertNotIn('PRIVATE_TOKEN',str(ctx.exception))


class IntegrationTests(unittest.TestCase):
    def test_fixture_build_contains_new_feeds_without_synthetic_public_observations(self):
        with tempfile.TemporaryDirectory() as folder:
            dist=Path(folder)/'dist'
            build(dist,fixture=ROOT/'tests/fixtures/open_meteo.json')
            validate(dist,fixture=True)
            nasa=json.loads((dist/'data/nasa_power.json').read_text())
            cemaden=json.loads((dist/'data/cemaden.json').read_text())
            self.assertEqual(nasa['status'],'fixture_mode')
            self.assertEqual(cemaden['status'],'fixture_mode')
            with self.assertRaises(ValueError):validate(dist,fixture=False)


if __name__=='__main__': unittest.main()
