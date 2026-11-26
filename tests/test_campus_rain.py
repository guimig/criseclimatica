"""Live-shaped fixtures for the cross-checked counter; no network."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from observatorio.campus_rain import (STEP, WINDOW_HOURS, summarize, reconstruct, quality_flags,
                                     apply_quality, validate_rain, METHOD, merge_rain, preserve_quality, raw_rain,
                                     collect_rain, RAW_QUALITY, AGG_QUALITY, reconcile)
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
                "COUNT":{"rain_total":60,"rain_increment":60,"rain_suspects_total":60}}
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
    def test_raw_actual_cadence_no_increment_and_midnight(self):
        end=int(datetime(2026,11,26,3,30,tzinfo=timezone.utc).timestamp()*1000)
        start=end-3600000
        now=datetime.fromtimestamp(end/1000,timezone.utc)
        raw={k:[] for k in ("rain_total","rain_daily","rain_suspects_total")}
        total=10
        for i,t in enumerate(range(start,end+1,5000)):
            if i%120==5:total+=.28
            values={"rain_total":total,"rain_daily":total if t<end-1800000 else total-10,
                    "rain_suspects_total":0}
            for key,v in values.items():raw[key].append({"ts":t,"value":str(v)})
        p=raw_rain(raw,start,end,now)
        self.assertEqual(p["status"],"available")
        self.assertTrue(p["windows"][0]["complete"])
        self.assertAlmostEqual(p["windows"][0]["value"],1.68)
        self.assertEqual(p["diagnostics"]["increment_samples"],0)
        validate_rain(p,iso(now))
        raw["rain_total"]=[r for r in raw["rain_total"] if not end-600000<r["ts"]<end-540000]
        p=raw_rain(raw,start,end,now)
        self.assertFalse(p["windows"][0]["complete"])
        self.assertGreater(p["diagnostics"]["rejected"]["raw_gap"],0)

    def test_raw_suspect_and_reset_never_become_valid(self):
        end=END;start=end-3600000
        raw={k:[] for k in ("rain_total","rain_daily","rain_suspects_total")}
        for t in range(start,end+1,5000):
            for k,v in (("rain_total",10 if t<end-600000 else 0),("rain_daily",0),("rain_suspects_total",0 if t<end-300000 else 1)):
                raw[k].append({"ts":t,"value":str(v)})
        p=raw_rain(raw,start,end,NOW)
        self.assertFalse(p["windows"][0]["complete"])
        self.assertTrue(p["diagnostics"]["rejected"])

    def test_archive_merges_short_queries_without_fabricating_coverage(self):
        g=fixture()
        first=summarize(g,START,END,NOW)
        product,archive=merge_rain({},first,iso(NOW))
        self.assertTrue(product["windows"][-1]["complete"])
        later=NOW+timedelta(minutes=30)
        product,new=merge_rain(archive,{},iso(later))
        self.assertEqual(product["windows"][-1]["end_at"],iso(NOW))
        cutoff=iso(later-timedelta(hours=73))
        self.assertEqual(new["intervals"],[r for r in archive["intervals"] if r["time"]>=cutoff])
        self.assertEqual(new["anchor_at"],archive["anchor_at"])
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
        self.assertEqual(d["statistics"]["rain_24h_mm"]["station_count"],0)
        self.assertEqual(d["campus_context"]["rain_reconstruction"]["windows"][4]["quality"],"estimated")
        self.assertTrue(any(w["hours"]==72 for w in d["antecedent_rain"]["windows"]))
        self.assertFalse(any(s["variable"]=="rain_24h_mm" and s["source"]=="ifc" for s in d["signals"]))

    def test_hybrid_estimates_do_not_overwrite_raw_or_hard_rejection(self):
        t=iso(NOW);before=iso(NOW-timedelta(minutes=5))
        raw={"intervals":[{"time":t,"value":.28,"quality":RAW_QUALITY}],
             "rejected_intervals":[{"time":before,"reason":"raw_gap"}]}
        aggregate={"intervals":[{"time":t,"value":.28,"quality":AGG_QUALITY},{"time":before,"value":0,"quality":AGG_QUALITY}]}
        records,blocked={},{}
        reconcile(records,blocked,raw,END);reconcile(records,blocked,aggregate,END)
        self.assertEqual(records[END],(.28,RAW_QUALITY))
        self.assertNotIn(END-STEP,records)
        reconcile(records,blocked,{"intervals":[{"time":before,"value":0,"quality":RAW_QUALITY}]},END)
        self.assertIn(END-STEP,records)
        reconcile(records,blocked,{"intervals":[{"time":t,"value":2,"quality":AGG_QUALITY}]},END)
        self.assertEqual(blocked[END],"source_conflict")
        self.assertNotIn(END,records)

    def test_complete_estimate_is_not_validated_coverage(self):
        r=summarize(fixture(),START,END,NOW);w=r["windows"][0]
        self.assertTrue(w["complete"]);self.assertFalse(w["validated_complete"])
        self.assertEqual(w["quality"],"estimated");self.assertEqual(w["estimated_minutes"],60)
        self.assertEqual(w["validated_minutes"],0)
        self.assertEqual(r["series"]["rain_24h"][-1]["quality"],"estimated")

    def test_archive_keeps_validated_reading_on_missing_requery(self):
        t=iso(NOW)
        previous={"intervals":[{"time":t,"value":.28,"quality":RAW_QUALITY}],"anchor_at":t}
        current={"status":"available","query_start_at":iso(NOW-timedelta(hours=1)),"query_end_at":t,"anchor_at":t,"intervals":[]}
        _,archive=merge_rain(previous,current,t)
        self.assertEqual(archive["intervals"],previous["intervals"])
        current["rejected_intervals"]=[{"time":t,"reason":"suspect_counter_changed"}]
        _,archive=merge_rain(previous,current,t)
        self.assertFalse(archive["intervals"])
        current["rejected_intervals"]=[];current["intervals"]=previous["intervals"]
        _,again=merge_rain(archive,current,t)
        self.assertFalse(again["intervals"])

    def test_raw_gap_can_only_be_repaired_with_recovered_raw_readings(self):
        from urllib.parse import parse_qs,urlsplit
        target=END-2*3600000
        prev={"anchor_at":iso(NOW-timedelta(hours=2)),
              "rejected_intervals":[{"time":iso(NOW-timedelta(hours=2)),"reason":"raw_gap"}]}
        calls=[]
        def source(path,**kwargs):
            q=parse_qs(urlsplit(path).query);a=int(q["startTs"][0]);b=int(q["endTs"][0]);agg=q["agg"][0]
            calls.append((agg,a,b))
            if agg!="NONE" or b-a>20*60000:return {}
            return {k:[{"ts":ts,"value":"10" if k=="rain_total" else "0"} for ts in range(a,b+1,5000)]
                    for k in ("rain_total","rain_daily","rain_suspects_total")}
        product=collect_rain(source,"public","/telemetry",NOW,prev,budget_seconds=45)
        self.assertEqual(product["diagnostics"]["raw_gap_repairs_attempted"],1)
        self.assertTrue(any(r["time"]==iso(NOW-timedelta(hours=2)) and r["quality"]==RAW_QUALITY for r in product["intervals"]))
        _,archive=merge_rain(prev,product,iso(NOW))
        self.assertFalse(any(r["time"]==iso(NOW-timedelta(hours=2)) for r in archive["rejected_intervals"]))

    def test_prioritizes_24h_holes_and_keeps_hard_vetoes(self):
        from urllib.parse import parse_qs,urlsplit
        gap=END-12*3600000;missing=gap-STEP;hard=gap-2*STEP
        def ts(t):return iso(datetime.fromtimestamp(t/1000,timezone.utc))
        prev={"anchor_at":ts(END),"intervals":[{"time":ts(t),"value":0,"quality":AGG_QUALITY}
              for t in range(END-24*3600000+STEP,END+1,STEP) if t not in (gap,missing,hard)],
              "rejected_intervals":[{"time":ts(gap),"reason":"raw_gap"},{"time":ts(hard),"reason":"source_conflict"}]}
        calls=[]
        def source(path,**kwargs):
            q=parse_qs(urlsplit(path).query);a=int(q["startTs"][0]);b=int(q["endTs"][0]);agg=q["agg"][0]
            calls.append((agg,a,b))
            if agg!="NONE" or b-a>20*60000:return {}
            return {k:[{"ts":t,"value":"10" if k=="rain_total" else "0"} for t in range(a,b+1,5000)]
                    for k in ("rain_total","rain_daily","rain_suspects_total")}
        result=collect_rain(source,"public","/telemetry",NOW,prev,budget_seconds=45)
        self.assertEqual(result["diagnostics"]["raw_gap_repairs_attempted"],1)
        self.assertEqual(result["diagnostics"]["raw_missing_repairs_attempted"],1)
        recovered={r["time"]:r["quality"] for r in result["intervals"]}
        self.assertEqual(recovered[ts(gap)],RAW_QUALITY)
        self.assertEqual(recovered[ts(missing)],RAW_QUALITY)
        self.assertNotIn(ts(hard),recovered)
        self.assertFalse(next(w for w in result["windows"] if w["hours"]==24)["complete"])
        validate_rain(result,iso(NOW))

    def test_graph_only_bridge_uses_paired_counter_endpoints(self):
        end=END;start=end-3600000;gap=end-2*STEP
        raw={k:[] for k in ("rain_total","rain_daily","rain_suspects_total")}
        for t in range(start,end+1,5000):
            if gap-STEP+30000<t<gap-30000:continue
            value=10 if t<gap-60000 else 10.28
            for k,v in (("rain_total",value),("rain_daily",value-10),("rain_suspects_total",0)):
                raw[k].append({"ts":t,"value":str(v)})
        product=raw_rain(raw,start,end,NOW)
        validate_rain(product,iso(NOW))
        self.assertFalse(product["windows"][0]["complete"])
        self.assertEqual(len(product["counter_bridges"]),1)
        self.assertAlmostEqual(product["counter_bridges"][0]["value"],.28)
        view,archive=merge_rain({},product,iso(NOW))
        validate_rain(view,iso(NOW))
        self.assertFalse(view["windows"][0]["complete"])
        graph=view["graph_windows"][0]
        self.assertTrue(graph["complete"])
        self.assertEqual(graph["bridge_minutes"],5)
        self.assertFalse(graph["threshold_eligible"])
        self.assertAlmostEqual(graph["value"],.28)
        self.assertEqual(view["graph_series"]["rain_1h"][-1]["quality"],"estimated")
        self.assertFalse(any(r["time"]==iso(datetime.fromtimestamp(gap/1000,timezone.utc)) for r in archive["intervals"]))
        # The graph estimate survives a temporary source outage, but a hard veto removes it.
        retained,_=merge_rain(archive,{},iso(NOW))
        self.assertEqual(retained["graph_windows"][0]["bridge_minutes"],5)
        t=product["counter_bridges"][0]["time"]
        denied,_=merge_rain(archive,{"rejected_intervals":[{"time":t,"reason":"counter_reset_or_decrease"}]},iso(NOW))
        self.assertEqual(denied["graph_windows"][0]["bridge_minutes"],0)
        raw["rain_daily"]=[]
        rejected=raw_rain(raw,start,end,NOW)
        self.assertEqual(rejected["counter_bridges"],[])
        raw["rain_daily"]=[{"ts":r["ts"],"value":"0"} for r in raw["rain_total"]]
        self.assertFalse(raw_rain(raw,start,end,NOW)["counter_bridges"])

    def test_graph_partial_24h_has_real_sum_without_complete_series(self):
        groups=fixture()
        groups["COUNT"]["rain_total"].pop(-3)
        raw=summarize(groups,START,END,NOW)
        product,_=merge_rain({},raw,iso(NOW))
        validate_rain(product,iso(NOW))
        strict=next(r for r in product["windows"] if r["hours"]==24)
        graph=product["graph_series"]["rain_24h"][-1]
        self.assertFalse(strict["complete"])
        self.assertEqual(graph["quality"],"partial")
        self.assertEqual(graph["value"],strict["value"])
        self.assertEqual(graph["covered_minutes"],strict["covered_minutes"])
        self.assertNotIn(graph["time"],[r["time"] for r in product["series"]["rain_24h"]])

    def test_backfill_chunk_limits_and_resume(self):
        from urllib.parse import parse_qs,urlsplit
        g=fixture();queries=[]
        def source(path,**kwargs):
            q=parse_qs(urlsplit(path).query);a=int(q["startTs"][0]);b=int(q["endTs"][0]);agg=q["agg"][0]
            queries.append((agg,a,b))
            if agg=="NONE":return {}
            return {key:[r for r in g.get(agg,{}).get(key,[]) if a<=r["ts"]<b] for key in q["keys"][0].split(",")}
        r=collect_rain(source,"public","/telemetry",NOW,budget_seconds=45)
        validate_rain(r,iso(NOW))
        self.assertGreater(r["diagnostics"]["historical_chunks_attempted"],0)
        self.assertLessEqual(r["diagnostics"]["historical_chunks_attempted"],14)
        self.assertTrue(all(b-a<=6*3600000 for agg,a,b in queries if agg!="NONE"))
        product,archive=merge_rain({},r,iso(NOW))
        self.assertTrue(product["windows"][-1]["complete"])
        self.assertFalse(product["windows"][-1]["validated_complete"])
        queries.clear()
        new=collect_rain(source,"public","/telemetry",NOW,archive,budget_seconds=45)
        self.assertLessEqual(new["diagnostics"]["historical_chunks_attempted"],2)

if __name__=="__main__":unittest.main()
