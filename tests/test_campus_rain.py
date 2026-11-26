"""Live-shaped fixtures for the cross-checked counter; no network."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from observatorio.campus_rain import (STEP, WINDOW_HOURS, summarize, reconstruct, quality_flags,
                                     apply_quality, validate_rain, METHOD, merge_rain, preserve_quality)
from observatorio.analysis import iso
from observatorio.multisource import build

NOW=datetime(2026,11,26,15,tzinfo=timezone.utc)
END=int(NOW.timestamp()*1000)
START=END-WINDOW_HOURS*3600000

def fixture(wet=True):
    groups={a:{} for a in ("MAX","MIN","SUM","COUNT")}
    total,daily=100.,0.
    lastday=None
    for i,t in enumerate(range(START,END,STEP)):
        local=(datetime.fromtimestamp(t/1000,timezone.utc)-timedelta(hours=3)).date()
        if local!=lastday:daily=0.;lastday=local
        amount=.2 if wet and i%60==1 else 0.
        before=total;total+=amount;daily+=amount
        fields={"MAX":{"rain_total":total,"rain_daily":daily,"rain_suspects_total":0},
                "MIN":{"rain_total":before,"rain_suspects_total":0},
                "SUM":{"rain_increment":amount},
                "COUNT":{"rain_total":5,"rain_increment":5,"rain_suspects_total":5}}
        for agg,values in fields.items():
            for key,value in values.items():
                groups[agg].setdefault(key,[]).append({"ts":t+STEP//2,"value":str(value)})
    return groups

class RainTests(unittest.TestCase):
    def test_complete_windows_cross_midnight_and_72h(self):
        r=summarize(fixture(),START,END,NOW)
        validate_rain(r,iso(NOW))
        self.assertEqual(r["status"],"available")
        self.assertTrue(all(w["complete"] for w in r["windows"]))
        self.assertEqual(r["windows"][-1]["hours"],72)
        self.assertGreater(r["windows"][-1]["value"],0)
        self.assertFalse(r["windows"][-1]["threshold_eligible"])
        self.assertLessEqual(len(r["series"]["rain_24h"]),600)
    def test_dry_documented_counter_requires_continuity_and_suspect_flags(self):
        g=fixture(False);g["SUM"]["rain_increment"]=[];g["COUNT"]["rain_increment"]=[]
        r=summarize(g,START,END,NOW)
        self.assertEqual(r["status"],"available")
        self.assertTrue(r["windows"][0]["complete"])
        self.assertEqual(r["windows"][0]["value"],0)
        g["MAX"]["rain_suspects_total"]=[]
        r=summarize(g,START,END,NOW)
        self.assertEqual(r["status"],"unavailable")
        self.assertEqual(r["windows"],[])
    def test_gap_reset_increment_mismatch_and_suspect_block_complete(self):
        for mutation in ("gap","reset","mismatch","suspect","count"):
            g=fixture()
            if mutation=="gap":g["MAX"]["rain_total"].pop(-2)
            if mutation=="reset":g["MIN"]["rain_total"][-2]["value"]="0"
            if mutation=="mismatch":g["SUM"]["rain_increment"][-2]["value"]="10"
            if mutation=="suspect":g["MAX"]["rain_suspects_total"][-2]["value"]="1"
            if mutation=="count":g["COUNT"]["rain_total"][-2]["value"]="1"
            r=summarize(g,START,END,NOW)
            self.assertFalse(r["windows"][0]["complete"],mutation)
            self.assertLess(r["windows"][0]["covered_minutes"],60)
            self.assertTrue(r["diagnostics"]["rejected"],mutation)
    def test_current_partial_and_future_not_used(self):
        g=fixture()
        g["MAX"]["rain_total"].append({"ts":END+STEP,"value":"999999"})
        r=summarize(g,START,END,NOW)
        self.assertTrue(r["windows"][0]["complete"])
        g["COUNT"]["rain_total"].pop()
        r=summarize(g,START,END,NOW)
        self.assertFalse(r["windows"][0]["complete"])
        self.assertEqual(r["windows"][0]["end_at"],iso(NOW))
    def test_flags_only_matching_bin_reject_affected_fields(self):
        time=iso(NOW-timedelta(minutes=5));old=iso(NOW-timedelta(minutes=15))
        def metric():
            return {"series":[{"time":old,"value":20},{"time":time,"value":20}],
                    "latest":{"time":time,"value":20},"fresh_at_collection":True}
        raw={"humidity_valid":[{"ts":END-STEP,"value":"false"}],
             "bme_stale":[{"ts":END-STEP,"value":"0"}],"bme_cal_ok":[{"ts":END-STEP,"value":"true"}]}
        metrics={k:metric() for k in ("temperature","humidity","pressure","wind_gust")}
        q=apply_quality(metrics,quality_flags(raw,START,END,1500))
        self.assertIsNone(metrics["humidity"]["latest"])
        self.assertEqual(len(metrics["humidity"]["series"]),1)
        self.assertEqual(q["unknown"]["humidity"],1)
        self.assertIsNotNone(metrics["temperature"]["latest"])
        self.assertIsNotNone(metrics["wind_gust"]["latest"])
        raw["bme_stale"][0]["value"]="true"
        q=apply_quality(metrics,quality_flags(raw,START,END,1500))
        self.assertIsNone(metrics["pressure"]["latest"])
        self.assertIsNotNone(metrics["wind_gust"]["latest"])
    def test_archive_merges_short_queries_without_fabricating_coverage(self):
        g=fixture()
        first=summarize(g,START,END,NOW)
        product,archive=merge_rain({},first,iso(NOW))
        self.assertTrue(product["windows"][-1]["complete"])
        later=NOW+timedelta(minutes=30)
        product,new=merge_rain(archive,{},iso(later))
        self.assertEqual(product["windows"][-1]["end_at"],iso(NOW))
        self.assertEqual(new,archive)
        product,new=merge_rain(archive,{},iso(NOW+timedelta(days=4)))
        self.assertFalse(new["intervals"])
        self.assertEqual(product["windows"],[])
    def test_persisted_invalid_bins_cannot_reappear_after_flags_age_out(self):
        t=iso(NOW-timedelta(minutes=5))
        c={"status":"available","quality":{"rejected_bins":{"temperature":[t]}},"metrics":{"temperature":{"series":[],"latest":None,"fresh_at_collection":False}}}
        known=preserve_quality(c,{},iso(NOW))
        c={"status":"available","quality":{},"metrics":{"temperature":{"series":[{"time":t,"value":20}],"latest":{"time":t,"value":20},"fresh_at_collection":True}}}
        preserve_quality(c,known,iso(NOW))
        self.assertFalse(c["metrics"])
        self.assertEqual(c["status"],"no_recent_data")
    def test_synthesis_one_station_complete_24h_and_longer_context(self):
        rain=summarize(fixture(),START,END,NOW)
        c={"status":"available","checked_at":iso(NOW),"metrics":{},"rain_reconstruction":rain}
        d,_,_=build({"assessment":{}},{},c,{},{"records":[]},{},{},iso(NOW))
        self.assertEqual(d["statistics"]["rain_24h_mm"]["station_count"],1)
        r=d["statistics"]["rain_24h_mm"]["members"][0]
        self.assertEqual(r["method"],METHOD)
        self.assertFalse(r["threshold_eligible"])
        self.assertTrue(any(w["hours"]==72 for w in d["antecedent_rain"]["windows"]))
        self.assertFalse(any(s["variable"]=="rain_24h_mm" and s["source"]=="ifc" for s in d["signals"]))

if __name__=="__main__":unittest.main()
