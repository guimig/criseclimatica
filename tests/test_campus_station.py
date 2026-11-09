"""Regression cases from the IFC station: future latest, NaN and counters."""
import json
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from observatorio.campus_station import collect, clean_points, empty, METRICS, SourceError, validate_product

NOW = datetime(2026, 11, 9, 22, 30, tzinfo=timezone.utc)
STAMP = "2026-11-09T22:30:00Z"
def row(value, when=NOW):
    return {"ts": int(when.timestamp()*1000), "value": value}


class CampusTests(unittest.TestCase):
    def source(self, path, *, body=None, token=None):
        if body is not None:
            self.assertEqual(set(body), {"publicId"})
            return {"token": "illustrative-public-session-not-a-secret"}
        query = parse_qs(urlparse(path).query)
        self.assertEqual(token, "illustrative-public-session-not-a-secret")
        self.assertIn("startTs", query); self.assertIn("endTs", query)
        self.assertNotIn("battery", query["keys"][0])
        values = {"temperature": 17.96, "humidity": 88.4, "pressure": 1002.09,
                  "rain_daily": 31.0134, "rain_intensity": 0, "wind_avg": 0, "wind_gust": 0, "wind_direction_deg": 337}
        return {key: [row(values[key])] for key in query["keys"][0].split(",")}

    def test_bounded_public_collection_preserves_daily_counter_and_zero_wind(self):
        feed = collect(STAMP, now=NOW, requester=self.source)
        validate_product(feed)
        self.assertEqual(feed["status"], "available")
        self.assertEqual(feed["metrics"]["rain_daily"]["latest"]["value"], 31.0134)
        self.assertEqual(feed["metrics"]["wind_gust"]["latest"]["value"], 0)
        self.assertEqual(feed["metrics"]["wind_gust"]["aggregation"], "MAX")
        self.assertEqual(feed["metrics"]["temperature"]["aggregation"], "AVG")
        self.assertNotIn("24h_mm", json.dumps(feed))
        self.assertNotIn("illustrative-public-session", json.dumps(feed))
        self.assertEqual(feed, collect(STAMP, now=NOW, requester=self.source))

    def test_future_nan_invalid_and_conflicting_points_are_removed(self):
        raw = [row("nan"), row("inf"), row(True), row(-999), row(18, NOW+timedelta(days=25500)),
               row(19, NOW-timedelta(days=2)), row(17.96, NOW-timedelta(minutes=10)), row(2, NOW-timedelta(minutes=2)), row(3, NOW-timedelta(minutes=2))]
        points, bad, conflicts = clean_points(raw, "temperature", NOW-timedelta(days=1), NOW)
        self.assertEqual(len(points), 1); self.assertEqual(points[0]["value"], 17.96)
        self.assertEqual(bad, 6); self.assertEqual(conflicts, 1)

    def test_missing_sensor_is_not_zero_and_old_sensor_is_not_current(self):
        def source(path, **kwargs):
            data = self.source(path, **kwargs)
            if "keys=" in path:
                data.pop("humidity", None)
                if "pressure" in data: data["pressure"] = [row(1000, NOW-timedelta(hours=3))]
            return data
        feed = collect(STAMP, now=NOW, requester=source)
        self.assertIsNone(feed["metrics"]["humidity"]["latest"])
        self.assertFalse(feed["metrics"]["pressure"]["fresh_at_collection"])
        validate_product(feed)

    def test_failure_empty_and_fixture_are_distinct(self):
        def fail(*args, **kwargs): raise SourceError("offline")
        self.assertEqual(collect(STAMP, now=NOW, requester=fail)["status"], "unavailable")
        def no_data(path, **kwargs): return {"token":"public"} if kwargs.get("body") else {}
        feed = collect(STAMP, now=NOW, requester=no_data)
        self.assertEqual(feed["status"], "no_recent_data"); validate_product(feed)
        validate_product(empty(STAMP, "fixture_mode"), fixture=True)
        with self.assertRaises(ValueError): validate_product(empty(STAMP, "fixture_mode"))

    def test_validator_rejects_classification_flag_wrong_units_and_future_data(self):
        feed = collect(STAMP, now=NOW, requester=self.source)
        for mutate in [lambda d:d.update(risk_criteria=True),
                       lambda d:d["metrics"]["rain_daily"].update(unit="mm/h"),
                       lambda d:d["metrics"]["temperature"]["latest"].update(time="2096-09-09T18:13:34Z")]:
            broken=deepcopy(feed); mutate(broken)
            with self.assertRaises(ValueError): validate_product(broken)

if __name__ == "__main__": unittest.main()
