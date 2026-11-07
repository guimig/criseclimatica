"""Offline validation for the regional Cemaden multi-sensor integration."""
from __future__ import annotations

import json
import math
import os
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
from observatorio.cemaden_auth import SgaaSession
from observatorio.cemaden_sensors import (
    KIND, MAX_RECORDS, SensorSourceError, collect, fetch_recent, fetch_sensor_types,
    normalize_recent, normalize_types, unavailable,
)
from observatorio.cemaden_rate import PedRateLimiter
from observatorio.cemaden import collect as collect_rain
from build_site import build
from validate_site import validate

NOW = datetime(2026, 11, 6, 16, 0, tzinfo=timezone.utc)
STAMP = "2026-11-06T16:00:00Z"
LOCATIONS = load_locations(ROOT / "config/locations.json")
TOKEN = "header.payload.signature_illustrative_only"
TYPES = [{"tipoestacao": 1, "tipoestacaodescricao": "Pluviométrica",
          "sensor": [{"sensor": 10, "sensordescricao": "Chuva"},
                     {"sensor": 240, "sensordescricao": "Intensidade da precipitação"}]},
         {"tipoestacao": 5, "tipoestacaodescricao": "Meteorológica",
          "sensor": [{"sensor": 60, "sensordescricao": "Temperatura do ar"},
                     {"sensor": 30, "sensordescricao": "Vazão"}]}]


def make_row(sensor=60, val=22.1, code="420130701A", hours_ago=0.5, **override):
    row = {"codestacao": code, "nome": "Parque Municipal", "cidade": "ARAQUARI",
           "uf": "SC", "latitude": -26.375, "longitude": -48.721,
           "id_sensor": sensor, "valor": val,
           "datahora": (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M"),
           "qualificacao": "0000"}
    row.update(override)
    return row


class RateLimitTests(unittest.TestCase):
    def test_rolling_window_never_exceeds_nine_calls(self):
        timestamp = [0.0]
        delays = []
        limiter = PedRateLimiter(limit=9, window=61,
                                 clock=lambda: timestamp[0],
                                 sleep=lambda seconds: (delays.append(seconds), timestamp.__setitem__(0, timestamp[0] + seconds)))
        for _ in range(9): limiter.acquire()
        self.assertEqual(delays, [])
        limiter.acquire()
        self.assertEqual(len(delays), 1)
        self.assertGreaterEqual(delays[0], 61)
        self.assertEqual(timestamp[0], 61)

    def test_invalid_limit_rejected(self):
        with self.assertRaises(ValueError): PedRateLimiter(limit=12)


class SensorFeedTests(unittest.TestCase):
    def test_requested_twenty_municipalities_with_official_ibge_codes(self):
        self.assertEqual(len(LOCATIONS), 20)
        index = {loc["id"]:loc["ibge_code"] for loc in LOCATIONS}
        self.assertEqual(index["araquari"], "4201307")
        self.assertEqual(index["blumenau"], "4202404")
        self.assertEqual(index["itajai"], "4208203")
        self.assertEqual(index["jaragua-do-sul"], "4208906")
        self.assertEqual(len(set(index.values())), len(index))

    def test_catalog_descriptions_are_dynamic_not_assumed(self):
        self.assertEqual(normalize_types(TYPES)[60], "Temperatura do ar")
        self.assertEqual(normalize_types(TYPES)[240], "Intensidade da precipitação")
        with self.assertRaises(SensorSourceError): normalize_types({"bad":"shape"})

    def test_sensor_values_and_nearby_station_origin(self):
        raw = [make_row(60, -3.2), make_row(30, 3.25), make_row(240, 12.8), make_row(2222, 8.4)]
        data = normalize_recent(raw, normalize_types(TYPES), LOCATIONS, STAMP, now=NOW)
        self.assertEqual(data["status"], "available")
        self.assertEqual(data["kind"], KIND)
        station = data["stations"][0]
        self.assertEqual(len(station["readings"]), 4)
        readings = {row["sensor_id"]:row for row in station["readings"]}
        self.assertEqual(readings[60]["unit"], "°C")
        self.assertEqual(readings[30]["unit"], "m³/s")
        self.assertIsNone(readings[2222]["unit"])
        self.assertEqual(readings[60]["value"], -3.2)
        near = next(loc for loc in data["locations"] if loc["location_id"] == "araquari")
        self.assertEqual(near["stations"][0]["distance_km"], 0.0)
        self.assertIn("not_model_forecast", data["kind"])

    def test_cross_municipal_station_displays_explicit_distance(self):
        raw = [make_row(code="420820301A", latitude=-26.9101, longitude=-48.6705, cidade="ITAJAI")]
        data = normalize_recent(raw, {60:"Temperatura do ar"}, LOCATIONS, STAMP, now=NOW)
        by_city={row["location_id"]:row["stations"] for row in data["locations"]}
        self.assertTrue(by_city["itajai"])
        self.assertTrue(by_city["araquari"])
        self.assertGreater(by_city["araquari"][0]["distance_km"], 50)
        self.assertLess(by_city["araquari"][0]["distance_km"], 85)

    def test_stale_future_foreign_and_invalid_values_never_published(self):
        raw = [make_row(hours_ago=4), make_row(hours_ago=-1),
               make_row(val=-999), make_row(val=9999), make_row(val=float("nan")),
               make_row(uf="RS"), make_row(latitude=-10, longitude=-65)]
        result = normalize_recent(raw, {}, LOCATIONS, STAMP, now=NOW)
        self.assertEqual(result["status"], "no_recent_data")
        self.assertFalse(result["stations"])

    def test_incomplete_or_malformed_payload_is_error_not_zero(self):
        for data in (None, {}, [42] * (MAX_RECORDS + 1)):
            with self.subTest(data=type(data).__name__), self.assertRaises(SensorSourceError):
                normalize_recent(data, {}, LOCATIONS, STAMP, now=NOW)

    def test_conflicting_duplicates_at_same_timestamp_discard_sensor(self):
        rows=[make_row(sensor=60,val=23),make_row(sensor=60,val=27)]
        result=normalize_recent(rows, {60:"Temperatura do ar"}, LOCATIONS, STAMP, now=NOW)
        self.assertEqual(result["status"], "no_recent_data")

    def test_latest_nonconflicting_value_wins(self):
        rows=[make_row(sensor=60,val=23,hours_ago=2),make_row(sensor=60,val=27,hours_ago=.5)]
        result=normalize_recent(rows, {60:"Temperatura do ar"}, LOCATIONS, STAMP, now=NOW)
        self.assertEqual(result["stations"][0]["readings"][0]["value"],27)

    def test_bulk_query_uses_official_network_and_header_not_url(self):
        requests=[]
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,count):return b"[]"
        class Opener:
            def open(self,request,timeout):
                requests.append(request)
                return Response()
        with patch('observatorio.cemaden_sensors.build_opener',return_value=Opener()):
            fetch_recent('SAFE_TEST_JWT')
            fetch_sensor_types('SAFE_TEST_JWT')
        self.assertIn('rede=11',requests[0].full_url)
        self.assertIn('uf=SC',requests[0].full_url)
        self.assertIn('formato=JSON',requests[0].full_url)
        self.assertNotIn('SAFE_TEST_JWT',requests[0].full_url)
        self.assertEqual(requests[0].get_header('Token'),'SAFE_TEST_JWT')
        self.assertIn('pcds-tipo-estacao/sensores',requests[1].full_url)

    def test_http_error_does_not_include_token(self):
        class Opener:
            def open(self,request,timeout):
                raise HTTPError(request.full_url, 401, 'wrong JWT', {}, None)
        with patch('observatorio.cemaden_sensors.build_opener',return_value=Opener()):
            with self.assertRaises(SensorSourceError) as cm:
                fetch_recent('SECRET_ABC')
        self.assertEqual(cm.exception.reason,'token_expired')
        self.assertNotIn('SECRET_ABC',str(cm.exception))

    def test_invalid_catalog_does_not_block_actual_readings(self):
        session=SgaaSession('fake@example.org','fake',token_requester=lambda *_:TOKEN)
        data=collect(LOCATIONS, STAMP, now=NOW, session=session,
                     recent_fetcher=lambda _: [make_row()],
                     sensor_fetcher=lambda _: (_ for _ in ()).throw(SensorSourceError('unavailable')))
        self.assertEqual(data['status'],'available')
        self.assertEqual(data['catalog_status'],'unavailable')
        self.assertIn('descrição indisponível',data['stations'][0]['readings'][0]['sensor_name'])

    def test_jwt_refresh_only_on_401(self):
        seen=[]
        def requester(*_):
            return TOKEN if not seen else 'SECOND.TOKEN.EXAMPLE'
        session=SgaaSession('fake@example.org','fake',token_requester=requester)
        def fetcher(token):
            if token==TOKEN:
                seen.append(token)
                raise SensorSourceError('token_expired')
            return [make_row()]
        data=collect(LOCATIONS, STAMP,now=NOW,session=session,recent_fetcher=fetcher,
                     sensor_fetcher=lambda _: TYPES)
        self.assertEqual(data['status'],'available')
        self.assertEqual(len(seen),1)
        self.assertNotIn('SECOND.TOKEN.EXAMPLE',json.dumps(data))

    def test_no_authorization_or_fixture_does_not_trigger_http(self):
        with patch.dict(os.environ, {'CEMADEN_PED_EMAIL':'', 'CEMADEN_PED_PASSWORD':'', 'CEMADEN_PED_TOKEN':''}):
            data=collect(LOCATIONS,STAMP, recent_fetcher=lambda _:self.fail('Unwanted network call'))
        self.assertEqual(data['status'],'not_configured')
        self.assertEqual(unavailable(LOCATIONS,STAMP,'fixture_mode')['status'],'fixture_mode')

    def test_rain_collector_respects_shared_request_hook(self):
        seen=[]
        result=collect_rain(LOCATIONS,STAMP,token='FAKE',now=NOW,
                            on_request=lambda:seen.append('request'),fetcher=lambda *_:[])
        self.assertEqual(len(seen),20)
        self.assertEqual(result['municipalities_checked'],20)

    def test_build_renders_and_validates_synthetic_sensor_block(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'site'
            build(target,fixture=ROOT/'tests/fixtures/open_meteo.json')
            validate(target,fixture=True)
            data=json.loads((target/'data/cemaden_sensors.json').read_text())
            self.assertEqual(data['status'],'fixture_mode')
            self.assertEqual(len(data['locations']),20)
            self.assertFalse(data['stations'])
            with self.assertRaises(ValueError):validate(target,fixture=False)

    def test_html_js_contract_for_multi_sensor_panel(self):
        html=(ROOT/'web/dados.html').read_text()
        js=(ROOT/'web/app.js').read_text()
        self.assertIn('id="cemaden-sensors-data"',html)
        self.assertIn('renderCemadenSensors();',js)
        self.assertIn('data/cemaden_sensors.json',js)
        self.assertIn('renderSourceHealth();',js)


if __name__=='__main__':unittest.main()

class ArchiveCoverageTests(unittest.TestCase):
    def test_caching_reindexes_archive_for_new_municipalities_without_download(self):
        from observatorio.inmet_archive import collect_archive, KIND as ARCHIVE_KIND
        previous = {
            "schema_version": 1, "kind": ARCHIVE_KIND, "archive_year": 2026,
            "retrieved_at": "2026-11-06T15:00:00Z", "last_attempt_at": "2026-11-06T15:00:00Z",
            "latest_observation_at": "2026-10-31T23:00:00Z",
            "source": {"id": "inmet-annual"},
            "stations": [{"code":"A868", "latitude":-26.9101,"longitude":-48.6705,
                          "days": [{"day_utc":"2026-10-31", "rain_measured_hours":24,
                                    "rain_total_complete_mm":5.0}]}],
            "locations": [{"location_id":"araquari","stations":[]}],
        }
        with patch('observatorio.inmet_archive._download_year',
                   side_effect=AssertionError('Annual ZIP must not be downloaded for cache reindexing')):
            out=collect_archive(LOCATIONS, {}, STAMP, previous=previous)
        self.assertEqual(out['status'],'cached')
        self.assertEqual(len(out['locations']), 20)
        cities={row['location_id']:row['stations'] for row in out['locations']}
        self.assertTrue(cities['itajai'])
        self.assertEqual(cities['itajai'][0]['distance_km'], 0.0)

