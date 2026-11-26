"""Regression tests for bounded IFC history, safe windows and consultative peaks."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from observatorio.analysis import iso
from observatorio.campus_history import (merge, contextual, recent_bins, rolling_hour,
                                         recent_wind_peaks, validate_history, circular)
from observatorio.multisource import build
from observatorio.risk_classification import classify

NOW = datetime(2026, 11, 26, 15, tzinfo=timezone.utc)
STAMP = iso(NOW)

def row(t, value):
    return {"time": iso(t), "value": value}

def feed(now=NOW, metrics=None):
    return {"status":"available", "checked_at":iso(now),
            "window_start":iso(now-timedelta(days=1)), "window_end":iso(now),
            "diagnostics":{"failed_history_groups":[]},
            "metrics":{k:{"series":rows,"latest":rows[-1] if rows else None}
                       for k, rows in (metrics or {}).items()}}

def counter(end=NOW):
    return [row(end-timedelta(minutes=60-5*i), i) for i in range(13)]

class CampusHistoryTest(unittest.TestCase):
    def test_rolling_rain_and_partial_coverage_never_sum_counters(self):
        c = feed(metrics={"rain_daily":counter()})
        bins = recent_bins(c,NOW)["rain_daily"]
        self.assertEqual(rolling_hour(bins,NOW)[NOW]["value"],12)
        r = contextual(c,STAMP)["rain_windows"]
        self.assertTrue(r[0]["complete"]); self.assertEqual(r[0]["value"],12)
        self.assertFalse(r[-1]["complete"])
        c["metrics"]["rain_daily"]["series"].pop(6)
        self.assertEqual(rolling_hour(recent_bins(c,NOW)["rain_daily"],NOW),{})
        self.assertFalse(contextual(c,STAMP)["rain_windows"][0]["complete"])

    def test_midnight_and_reset_are_not_complete_rolling_windows(self):
        end = datetime(2026,11,26,3,30,tzinfo=timezone.utc)
        c = feed(end,{"rain_daily":counter(end)})
        self.assertEqual(rolling_hour(recent_bins(c,end)["rain_daily"],end),{})
        self.assertFalse(contextual(c,iso(end))["rain_windows"][0]["complete"])
        points=counter();points[6]["value"]=0
        c=feed(metrics={"rain_daily":points})
        self.assertEqual(rolling_hour(recent_bins(c,NOW)["rain_daily"],NOW),{})

    def test_retention_compaction_preserves_gust_max_and_actual_coverage(self):
        points=[row(NOW-timedelta(minutes=5*i), 92 if i==287 else 8) for i in reversed(range(289))]
        c=feed(metrics={"wind_gust":points})
        first=merge(None,c,STAMP)
        later=NOW+timedelta(minutes=30)
        second=merge(first,{"status":"unavailable"},iso(later))
        old=[p for p in second["series"]["wind_gust"] if p["interval_minutes"]==30]
        self.assertTrue(old);self.assertEqual(max(p["value"] for p in old),92)
        self.assertTrue(all(1<=p["count"]<=6 for p in old))
        self.assertEqual(merge(second,{"status":"unavailable"},iso(later)),second)
        expired=merge(second,{"status":"unavailable"},iso(NOW+timedelta(days=8)))
        self.assertEqual(expired["series"]["wind_gust"],[])

    def test_gaps_and_suspect_zero_are_not_restored_from_previous_history(self):
        c=feed(metrics={"temperature":[row(NOW,23)],"humidity":[row(NOW,70)]})
        first=merge(None,c,STAMP)
        bad=feed(metrics={"temperature":[row(NOW,0)],"humidity":[row(NOW,0)]})
        self.assertEqual(merge(first,bad,STAMP)["series"]["temperature"],[])
        missing=feed(metrics={"temperature":[]})
        self.assertEqual(merge(first,missing,STAMP)["series"]["temperature"],[])
        missing["diagnostics"]["failed_history_groups"]=["AVG"]
        self.assertEqual(merge(first,missing,STAMP)["series"]["temperature"][0]["value"],23)
        self.assertIsNone(contextual(bad,STAMP)["dew_point_c"])

    def test_excluded_counter_conflict_cannot_create_a_window(self):
        c=feed(metrics={"rain_daily":counter()})
        first=merge(None,c,STAMP)
        t=NOW-timedelta(minutes=30)
        second=merge(first,c,STAMP,{t})
        self.assertFalse(any(p["time"]==iso(t) for p in second["series"]["rain_daily"]))
        self.assertFalse(second["series"]["rain_1h"])
        self.assertFalse(contextual(c,STAMP,{t})["rain_windows"][0]["complete"])

    def test_dew_point_and_circular_direction(self):
        c=feed(metrics={"temperature":[row(NOW,32)],"humidity":[row(NOW,70)],
                        "wind_avg":[row(NOW,10)],"wind_direction_deg":[row(NOW,359)]})
        r=contextual(c,STAMP)
        self.assertTrue(25<r["dew_point_c"]<27)
        self.assertGreater(r["heat_index_c"],32)
        self.assertEqual(r["wind_sectors"]["counts"][0],1)
        self.assertAlmostEqual(circular([359,1]),0)
        self.assertIsNone(circular([0,180]))

    def test_recent_gust_peak_supports_attention_not_orange(self):
        past=NOW-timedelta(minutes=25)
        c=feed(metrics={"wind_gust":[row(past,85),row(NOW,10)]})
        dashboard={"assessment":{}}
        synth,_,detail=build(dashboard,{},c,{},{"records":[]},{},{},STAMP)
        peaks=[p for p in synth["signals"] if p.get("support")=="five_minute_peak"]
        self.assertEqual(len(peaks),1);self.assertEqual(peaks[0]["value"],85)
        self.assertEqual(peaks[0]["end_at"],iso(past))
        self.assertEqual(peaks[0]["method"],"reported_interval_unverified")
        self.assertEqual(synth["statistics"]["gust_kmh"]["station_count"],1)
        self.assertEqual(synth["statistics"]["gust_kmh"]["maximum"],10)
        dashboard["synthesis"]=synth
        self.assertEqual(classify(dashboard,detail,STAMP)["level"],"amarelo")
        self.assertEqual(recent_wind_peaks(c,iso(NOW+timedelta(hours=2))),[])

if __name__=="__main__":unittest.main()
