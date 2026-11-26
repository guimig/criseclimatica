"""Bounded independent checks for IFC rain counters and instrument validity.

No rain total is accepted solely on a key name, nor is an unavailable
interval interpreted as zero. The reconstructed interval remains approximate;
it is not a confirmed institutional threshold observation.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import isfinite
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .analysis import iso, moment, valid_number

STEP = 300_000
WINDOW_HOURS = 73
LIMIT = WINDOW_HOURS * 12 + 2
QUERY_HOURS = 6
MIN_SAMPLES_PER_BIN = 2
# Public dashboard 421b5150, device 948e1e60, verified 26/11/2026:
# rain_total widget: Chuva Total, units mm. This is provider metadata,
# not metrological certification or proof of uninterrupted transmission.
TOTAL_UNIT = 'mm'
WINDOWS = (1, 3, 6, 12, 24, 48, 72)
TZ = ZoneInfo("America/Sao_Paulo")
QUALITY_KEYS = ("humidity_valid", "bme_stale", "bme_cal_ok", "bme_consec_fails")
FLAGS = {"humidity_valid": True, "bme_stale": False, "bme_cal_ok": True, "bme_consec_fails": False}
AFFECTED = {"temperature": ("bme_stale", "bme_cal_ok", "bme_consec_fails"),
            "humidity": QUALITY_KEYS, "pressure": ("bme_stale", "bme_cal_ok", "bme_consec_fails")}
METHOD = "crosschecked_total_counter_5min_approximation"


def parse_number(value):
    if isinstance(value, bool):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return v if isfinite(v) else None


def flag_value(value):
    if value is True or value is False:
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        value = value.strip().lower()
        if value in ("true", "1", "1.0"):
            return True
        if value in ("false", "0", "0.0"):
            return False
    return None


def query(requester, token, telemetry, keys, start, end, agg, limit):
    data = requester(telemetry+"?"+urlencode({"keys": ",".join(keys), "startTs": start,
                    "endTs": end, "agg": agg, "interval": STEP, "limit": limit, "orderBy": "DESC"}), token=token)
    if not isinstance(data, dict):
        raise ValueError("Invalid IFC telemetry shape")
    return data


def bucket_series(raw, start, end, limit, *, count=False):
    """ThingsBoard aggregation timestamps lie within their five-minute bin."""
    if not isinstance(raw, list) or len(raw) > limit:
        return {}
    values, conflicts = {}, set()
    for row in raw:
        if not isinstance(row, dict):
            continue
        ts, value = row.get("ts"), parse_number(row.get("value"))
        if (not isinstance(ts, int) or isinstance(ts, bool) or not start <= ts < end
                or value is None or value < 0 or (count and (value != int(value) or value < 1))):
            continue
        t = ts//STEP*STEP
        if t in values and values[t] != value:
            conflicts.add(t)
        values[t] = value
    return {t:v for t,v in values.items() if t not in conflicts}


def close(a, b):
    # A small allowance for sensor/report rounding, not a rainfall threshold.
    return abs(a-b) <= max(.025, .005*max(abs(a), abs(b)))


def unit_evidence(total, daily):
    """Check positive changes in the total against the known mm daily counter.

    A dry series alone cannot demonstrate units. Match only contiguous,
    same-local-day, positive increments in both counters.
    """
    matches, mismatches = 0, 0
    for t in sorted(set(total) & set(daily)):
        p=t-STEP
        if p not in total or p not in daily:
            continue
        if datetime.fromtimestamp(p/1000,timezone.utc).astimezone(TZ).date() != datetime.fromtimestamp(t/1000,timezone.utc).astimezone(TZ).date():
            continue
        a,b=total[t]-total[p],daily[t]-daily[p]
        if a < 0 or b < 0 or max(a,b) < .05:
            continue
        if close(a,b) and min(a,b) > 0:
            matches += 1
        else:
            mismatches += 1
    return {"matching_positive_bins":matches, "mismatching_positive_bins":mismatches,
            "status":"empirically_consistent_mm" if matches >= 2 and not mismatches else "unverified"}


def reconstruct(groups, start, end):
    def points(agg, key, count=False):
        return bucket_series(groups.get(agg,{}).get(key,[]),start,end,LIMIT,count=count)
    maximum=points("MAX","rain_total"); minimum=points("MIN","rain_total")
    daily=points("MAX","rain_daily")
    inc=points("SUM","rain_increment")
    suspect_hi=points("MAX","rain_suspects_total"); suspect_lo=points("MIN","rain_suspects_total")
    ct=points("COUNT","rain_total",True); ci=points("COUNT","rain_increment",True)
    cs=points("COUNT","rain_suspects_total",True)
    units=unit_evidence(maximum,daily)
    units["documented_unit"]=TOTAL_UNIT
    units["status"]="documented_mm"
    diagnostics={"unit_evidence":units,"total_bins":len(maximum),"increment_bins":len(inc),
                 "suspect_bins":len(suspect_hi),"accepted_bins":0,"increment_checked_bins":0,
                 "rejected":{}}
    accepted={}
    def reject(reason):
        diagnostics["rejected"][reason]=diagnostics["rejected"].get(reason,0)+1
    for t in sorted(maximum):
        p=t-STEP
        if p not in maximum or t not in minimum or t not in ct or p not in ct:
            reject("missing_counter_or_count");continue
        if min(ct[p],ct[t])<MIN_SAMPLES_PER_BIN:
            reject("insufficient_counter_samples");continue
        if not all(k in series for k,series in ((p,suspect_hi),(t,suspect_hi),(t,suspect_lo),(t,cs),(p,cs))) or cs[t]!=ct[t] or cs[p]!=ct[p]:
            reject("suspect_counter_unverified");continue
        if not close(suspect_hi[p],suspect_lo[t]) or not close(suspect_lo[t],suspect_hi[t]):
            reject("suspect_counter_changed");continue
        delta=maximum[t]-maximum[p]
        if minimum[t]>maximum[t] or minimum[t]<maximum[p] or delta<0:
            reject("counter_reset_or_decrease");continue
        if not valid_number(delta,0,500):
            reject("invalid_counter_difference");continue
        # The daily counter independently confirms same-day differences when
        # it is available. A mismatch is not silently accepted.
        if p in daily and t in daily and datetime.fromtimestamp(p/1000,timezone.utc).astimezone(TZ).date()==datetime.fromtimestamp(t/1000,timezone.utc).astimezone(TZ).date():
            if daily[t]>=daily[p] and not close(delta,daily[t]-daily[p]):
                reject("daily_counter_mismatch");continue
        # rain_increment has no recent samples in the live probe. If a
        # complete coincident stream appears, require its sum to agree.
        if t in inc and t in ci and ci[t]==ct[t]:
            if not close(delta,inc[t]):
                reject("counter_increment_mismatch");continue
            diagnostics["increment_checked_bins"]+=1
        elif t in inc and inc[t]>delta+.025:
            reject("partial_increment_exceeds_counter");continue
        accepted[t+STEP]=round(delta,5)
    diagnostics["accepted_bins"]=len(accepted)
    return accepted, diagnostics


def empty_rain(status="unavailable"):
    return {"status":status,"method":METHOD,"threshold_eligible":False,
            "windows":[],"series":{},"diagnostics":{},"intervals":[]}


def build_windows(accepted, anchor, now):
    result={"windows":[],"series":{}}
    if not anchor or not 0<=now.timestamp()*1000-anchor<=90*60_000:
        return result
    def window(t, hours):
        n=hours*12
        values=[accepted.get(t-i*STEP) for i in range(n)]
        present=[v for v in values if v is not None]
        return {"hours":hours,"value":round(sum(present),3) if present else None,
                "covered_minutes":len(present)*5,"expected_minutes":hours*60,
                "complete":len(present)==n,"method":METHOD,"threshold_eligible":False,
                "start_at":iso(datetime.fromtimestamp((t-hours*3600000)/1000,timezone.utc)),
                "end_at":iso(datetime.fromtimestamp(t/1000,timezone.utc))}
    result["windows"]=[window(anchor,h) for h in WINDOWS]
    for h in (1,24):
        rows=[]
        start=max(anchor-72*3600000,min(accepted,default=anchor))
        for t in range(start+(h*12-1)*STEP,anchor+1,STEP):
            if anchor-t>24*3600000 and t%(6*STEP):
                continue
            row=window(t,h)
            if row["complete"]:
                rows.append({"time":row["end_at"],"value":row["value"],
                             "interval_minutes":5 if anchor-t<=24*3600000 else 30,
                             "count":1 if anchor-t<=24*3600000 else 6})
        result["series"][f"rain_{h}h"]=rows[-600:]
    return result


def summarize(groups, start, end, now):
    accepted, diagnostics=reconstruct(groups,start,end)
    totals=bucket_series(groups.get("MAX",{}).get("rain_total",[]),start,end,LIMIT)
    result=empty_rain("no_valid_intervals")
    result["diagnostics"]=diagnostics
    if not totals or not diagnostics["suspect_bins"]:
        result["status"]="unavailable";return result
    result["query_start_at"]=iso(datetime.fromtimestamp(start/1000,timezone.utc))
    result["query_end_at"]=iso(datetime.fromtimestamp(end/1000,timezone.utc))
    anchor=max(totals)+STEP
    result["anchor_at"]=iso(datetime.fromtimestamp(anchor/1000,timezone.utc))
    result["intervals"]=[{"time":iso(datetime.fromtimestamp(t/1000,timezone.utc)),"value":v} for t,v in sorted(accepted.items())]
    result["status"]="available" if accepted else "no_valid_intervals"
    if not 0<=now.timestamp()*1000-anchor<=90*60_000:
        result["status"]="stale";return result
    result.update(build_windows(accepted,anchor,now))
    return result


def merge_rain(previous, current, stamp):
    """Retain only validated 5-min increments for 73h, replacing queried bins.

    Old measurements preserve their timestamps. No need for a large 72h
    request to the provider on every collection cycle.
    """
    now=moment(stamp)
    now_ms=int(now.timestamp()*1000)
    oldest=now_ms-WINDOW_HOURS*3600000
    previous=previous or {}
    current=current or empty_rain()
    def collect_rows(rows):
        result={}
        if not isinstance(rows,list) or len(rows)>LIMIT:return result
        for r in rows:
            if not isinstance(r,dict):continue
            t=moment(r.get("time"));v=r.get("value")
            if not t or not valid_number(v,0,500):continue
            ms=int(t.timestamp()*1000)
            if oldest<=ms<=now_ms and ms%STEP==0:result[ms]=v
        return result
    accepted=collect_rows(previous.get("intervals",[]))
    start=moment(current.get("query_start_at"));end=moment(current.get("query_end_at"))
    if start and end and current.get("status")!="unavailable":
        a,b=int(start.timestamp()*1000),int(end.timestamp()*1000)
        # First bucket has no preceding counter in this query: preserve
        # the earlier validated delta at that boundary if present.
        accepted={t:v for t,v in accepted.items() if not a+STEP<t<=b}
        accepted.update(collect_rows(current.get("intervals",[])))
    anchor=moment(current.get("anchor_at")) or moment(previous.get("anchor_at"))
    archive={"intervals":[{"time":iso(datetime.fromtimestamp(t/1000,timezone.utc)),"value":v}
                         for t,v in sorted(accepted.items())][-LIMIT:],
             "anchor_at":iso(anchor) if anchor and oldest<=anchor.timestamp()*1000<=now_ms else None}
    product=empty_rain(current.get("status","unavailable"))
    product["diagnostics"]=current.get("diagnostics",{})
    product["diagnostics"]={**product["diagnostics"],"retained_valid_bins":len(accepted),
                            "query_status":current.get("status","unavailable")}
    if anchor and 0<=now_ms-anchor.timestamp()*1000<=90*60_000:
        product["status"]="available" if accepted else "no_valid_intervals"
        product.update(build_windows(accepted,int(anchor.timestamp()*1000),now))
    elif anchor:
        product["status"]="stale"
    return product,archive


def quality_flags(raw, start, end, limit):
    """Exact bucket match only; unknown flags never imply a valid sensor."""
    by_key={}
    for key in QUALITY_KEYS:
        values=defaultdict(set)
        rows=raw.get(key,[])
        if not isinstance(rows,list) or len(rows)>limit:
            by_key[key]={};continue
        for row in rows:
            if not isinstance(row,dict):continue
            t=row.get("ts"); v=flag_value(row.get("value"))
            if key=="bme_consec_fails":
                n=parse_number(row.get("value")); v=(n>0) if n is not None and n>=0 else None
            if isinstance(t,int) and not isinstance(t,bool) and start<=t<=end and v is not None:
                values[t//STEP*STEP].add(v)
        by_key[key]={t:FLAGS[key] if s=={FLAGS[key]} else not FLAGS[key] for t,s in values.items()}
    return by_key


def apply_quality(metrics, flags):
    summary={"status":"available" if any(flags.values()) else "unavailable",
             "flags":{},"rejected":{},"unknown":{},"rejected_bins":{}}
    for key,rows in flags.items():
        t=max(rows,default=None)
        summary["flags"][key]={"bins":len(rows),"latest":rows[t] if t is not None else None,
                              "time":iso(datetime.fromtimestamp(t/1000,timezone.utc)) if t is not None else None}
    for key,requirements in AFFECTED.items():
        if key not in metrics:continue
        rejected, unknown=0,0
        blocked=set()
        def usable(p):
            nonlocal rejected,unknown
            if not p:return False
            t=moment(p.get("time"))
            if not t:return False
            t=int(t.timestamp()*1000)//STEP*STEP
            values=[flags.get(f,{}).get(t) for f in requirements]
            if any(v is not None and v!=FLAGS[f] for f,v in zip(requirements,values)):
                rejected+=1;blocked.add(t);return False
            if any(v is None for v in values):unknown+=1
            return True
        m=metrics[key]
        m["series"]=[p for p in m.get("series",[]) if usable(p)]
        if m.get("latest") and not usable(m["latest"]):
            m["latest"]=None;m["fresh_at_collection"]=False
        summary["rejected"][key]=rejected;summary["unknown"][key]=unknown
        summary["rejected_bins"][key]=[iso(datetime.fromtimestamp(t/1000,timezone.utc)) for t in sorted(blocked)]
    return summary


def collect_rain(requester,token,telemetry,now):
    """Three short grouped counter queries, plus optional increment check."""
    from .campus_station import SourceError
    end=int(now.timestamp()*1000)//STEP*STEP
    start=end-QUERY_HOURS*3600000
    groups={}
    requests={"MAX":("rain_total","rain_daily","rain_suspects_total"),
              "MIN":("rain_total","rain_suspects_total"),
              "COUNT":("rain_total","rain_increment","rain_suspects_total")}
    try:
        for agg,keys in requests.items():
            groups[agg]=query(requester,token,telemetry,keys,start,end,agg,QUERY_HOURS*12+2)
        if groups["COUNT"].get("rain_increment"):
            try:groups["SUM"]=query(requester,token,telemetry,("rain_increment",),start,end,"SUM",QUERY_HOURS*12+2)
            except (SourceError,OSError,ValueError,TypeError,KeyError):groups["SUM"]={}
        return summarize(groups,start,end,now)
    except (SourceError,OSError,ValueError,TypeError,KeyError):
        return empty_rain()


def collect_quality(requester,token,telemetry,now,metrics):
    from .campus_station import SourceError
    end=int(now.timestamp()*1000)//STEP*STEP
    start=end-24*3600000
    try:
        raw=query(requester,token,telemetry,QUALITY_KEYS,start,end,"NONE",1500)
    except (SourceError,OSError,ValueError,TypeError,KeyError):
        raw={}
    return apply_quality(metrics,quality_flags(raw,start,end,1500))


def preserve_quality(campus, previous, stamp):
    """Do not resurrect explicitly rejected samples on a later 24h requery."""
    now=moment(stamp)
    quality=campus.get("quality",{})
    known={}
    for key in AFFECTED:
        times=set((previous or {}).get(key,[]))|set(quality.get("rejected_bins",{}).get(key,[]))
        known[key]=sorted(t for t in times if moment(t) and now-timedelta(hours=25)<=moment(t)<=now)
        blocked=set(known[key])
        def good(p):
            t=moment((p or {}).get("time"))
            if not t:return False
            ms=int(t.timestamp()*1000)//STEP*STEP
            return iso(datetime.fromtimestamp(ms/1000,timezone.utc)) not in blocked
        metric=campus.get("metrics",{}).get(key)
        if metric:
            metric["series"]=[p for p in metric.get("series",[]) if good(p)]
            if metric.get("latest") and not good(metric["latest"]):
                metric["latest"]=None;metric["fresh_at_collection"]=False
    if campus.get("status") in ("available","stale") and "quality" in campus:
        metrics=campus.get("metrics",{})
        campus["status"]="available" if any(m.get("fresh_at_collection") for m in metrics.values()) else "stale" if any(m.get("latest") or m.get("series") for m in metrics.values()) else "no_recent_data"
        if campus["status"]=="no_recent_data":campus["metrics"]={}
    return known


def validate_rain(product, stamp):
    if (not isinstance(product,dict) or product.get("method")!=METHOD
            or product.get("threshold_eligible") is not False
            or product.get("status") not in ("unavailable","unverified","available","no_valid_intervals","stale")
            or not isinstance(product.get("windows"),list) or not isinstance(product.get("series"),dict)):
        raise ValueError("Invalid IFC rain reconstruction")
    now=moment(stamp)
    if len(product["windows"])>len(WINDOWS) or set(product["series"])-{"rain_1h","rain_24h"} or len(product.get("intervals",[]))>LIMIT:
        raise ValueError("Unbounded IFC rain reconstruction")
    seen=set()
    for r in product["windows"]:
        h=r.get("hours");a=moment(r.get("start_at"));b=moment(r.get("end_at"));n=r.get("covered_minutes")
        if (h not in WINDOWS or h in seen or not a or not b or not a<b<=now or b-a!=timedelta(hours=h)
                or r.get("expected_minutes")!=h*60 or not isinstance(n,int) or isinstance(n,bool) or n%5 or not 0<=n<=h*60
                or r.get("complete") is not (n==h*60) or r.get("threshold_eligible") is not False
                or r.get("method")!=METHOD or (n>0 and not valid_number(r.get("value"),0,500*n/5))
                or (n==0 and r.get("value") is not None)):
            raise ValueError("Invalid IFC rain window")
        seen.add(h)
    for key,rows in product["series"].items():
        if not isinstance(rows,list) or len(rows)>600:raise ValueError("Unbounded IFC rain series")
        last=None
        for r in rows:
            t=moment(r.get("time"))
            if (not t or not now-timedelta(hours=73)<=t<=now or (last and t<=last)
                    or not valid_number(r.get("value"),0,144000)
                    or r.get("interval_minutes") not in (5,30)):
                raise ValueError("Invalid IFC rain series")
            last=t
    if product["status"]!="available" and any(r["complete"] for r in product["windows"]):
        raise ValueError("Unavailable IFC rain cannot be complete")
    return product
