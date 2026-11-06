"""Coverage expansion without attributing distant stations to local weather."""
import io
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
from observatorio.metar import STATIONS, fetch_metars, normalize_metars
from observatorio.cemaden_sensors import normalize_recent
from observatorio.cemaden import collect as collect_rain
from test_cemaden_sensors_regional import make_row, NOW, STAMP

PLACE = {"id":"araquari", "ibge_code":"4201307", "latitude":-26.375, "longitude":-48.721}


def metar(code, lat, lon, age=0):
    return {"icaoId":code, "lat":lat, "lon":lon, "obsTime":int((NOW-timedelta(hours=age)).timestamp()),
            "temp":25, "wspd":10, "wgst":20, "name":code}


class StationExpansionTests(unittest.TestCase):
    def test_twenty_four_cemaden_stations_are_selected_in_distance_order(self):
        raw = [make_row(code=f"4201307{i:03d}A", latitude=PLACE["latitude"]+i*.001) for i in range(30)]
        data = normalize_recent(raw, {60:"Temperatura"}, [PLACE], STAMP, now=NOW)
        local = data["locations"][0]
        self.assertEqual(len(local["stations"]), 24)
        self.assertEqual(local["eligible_station_count"], 30)
        distances = [r["distance_km"] for r in local["stations"]]
        self.assertEqual(distances, sorted(distances))

    def test_station_beyond_old_radius_is_included_but_outside_new_radius_is_not(self):
        raw = [make_row(code="inside123", latitude=-25.45), make_row(code="outside123", latitude=-24)]
        data = normalize_recent(raw, {}, [PLACE], STAMP, now=NOW)
        self.assertEqual([r["code"] for r in data["stations"]], ["inside123"])
        self.assertGreater(data["locations"][0]["stations"][0]["distance_km"],85)

    def test_old_station_readings_are_still_excluded_in_larger_area(self):
        data = normalize_recent([make_row(latitude=-25.45,hours_ago=7)], {}, [PLACE], STAMP, now=NOW)
        self.assertEqual(data["status"],"no_recent_data")

    def test_all_municipal_rain_gauges_are_kept(self):
        rows = [{"codibge":"4201307","codestacao":f"4201307{i:03d}A","datahora":STAMP,"acc24hr":i} for i in range(25)]
        result = collect_rain([PLACE],STAMP,token="test-only",now=NOW,fetcher=lambda *_:rows)
        self.assertEqual(result["stations_with_readings"],25)
        self.assertEqual(len(result["locations"][0]["stations"]),25)

    def test_all_six_metar_codes_are_queried_once(self):
        self.assertEqual(STATIONS, {"SBJV","SBNF","SSBL","SBFL","SBCT","SBBI"})
        class Response(io.BytesIO):
            status=200
        with patch("observatorio.metar.urlopen",return_value=Response(b"[]")) as opener:
            fetch_metars()
        self.assertEqual(opener.call_count,1)
        params=parse_qs(urlparse(opener.call_args.args[0].full_url).query)
        self.assertEqual(set(params["ids"][0].split(",")),STATIONS)
        self.assertEqual(params["hours"],["6"])

    def test_all_nearby_reports_and_distinct_regional_context_are_kept(self):
        raw=[metar("SBJV",-26.22,-48.8),metar("SBNF",-26.88,-48.65),
             metar("SBCT",-25.53,-49.17),metar("SBBI",-25.4,-49.23),
             metar("SSBL",-26.83,-49.1),metar("SBFL",-27.67,-48.55)]
        data=normalize_metars(raw,[PLACE],STAMP,now=NOW)
        self.assertEqual(len(data["stations"]),6)
        local=data["locations"][0]
        self.assertEqual(local["observation"]["icao"],"SBJV")
        self.assertEqual(len(local["stations"]),6)
        self.assertTrue(any(r["scope"]=="regional_context_only" for r in local["stations"]))
        self.assertEqual(len(data["queried_stations"]),6)

    def test_only_regional_report_does_not_become_primary_observation(self):
        data=normalize_metars([metar("SBFL",-27.67,-48.55)],[PLACE],STAMP,now=NOW)
        local=data["locations"][0]
        self.assertIsNone(local["observation"])
        self.assertEqual(local["status"],"no_recent_report")
        self.assertEqual(local["stations"][0]["scope"],"regional_context_only")

    def test_missing_expired_and_far_away_metars_do_not_create_local_reports(self):
        data=normalize_metars([metar("SSBL",-26.83,-49.1,age=9),metar("SBFL",-30,-48)], [PLACE], STAMP, now=NOW)
        self.assertFalse(data["locations"][0]["stations"])
        queries={r["icao"]:r["status"] for r in data["queried_stations"]}
        self.assertEqual(queries["SSBL"],"no_recent_report")
        self.assertEqual(queries["SBJV"],"no_recent_report")


if __name__ == "__main__":
    unittest.main()
