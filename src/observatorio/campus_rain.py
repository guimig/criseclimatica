"""Bounded independent checks for IFC rain counters and instrument validity.

No rain total is accepted solely on a key name, nor is an unavailable
interval interpreted as zero. The reconstructed interval remains approximate;
it is not a confirmed institutional threshold observation.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import isfinite
from time import monotonic
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .analysis import iso, moment, valid_number

STEP = 300_000
WINDOW_HOURS = 73
LIMIT = WINDOW_HOURS * 12 + 2
QUERY_HOURS = 6
RAW_HOURS = 1
RAW_LIMIT = 1000
RAW_MAX_GAP_MS = 30_000
MIN_SAMPLES_PER_BIN = 40  # observed 5 s cadence; counts do not prove continuity
RAW_QUALITY = 'raw_validated'
AGG_QUALITY = 'aggregate_estimated'
LEGACY_QUALITY = 'legacy_unverified'
QUALITIES = (RAW_QUALITY, AGG_QUALITY, LEGACY_QUALITY)
HARD_REASONS = frozenset(('suspect_counter_changed','suspect_counter_changed_or_missing','counter_reset_or_decrease',
                          'invalid_counter_difference','daily_counter_mismatch','counter_increment_mismatch',
                          'partial_increment_exceeds_counter','raw_conflict','source_conflict'))
RECOVERY_BUDGET_SECONDS = 45
RETRY_MS = 3*3600000
CHUNK_MS = (QUERY_HOURS*12-1)*STEP
MAX_INITIAL_CHUNKS = 14
MAX_REPAIR_CHUNKS = 2
RAW_REPAIR_HOURS = 24
MAX_RAW_REPAIRS = 2
MAX_RECOVERY_ATTEMPTS = 48
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
                 "rejected":{}, "rejected_intervals":[]}
    accepted={}
    def reject(reason):
        diagnostics["rejected"][reason]=diagnostics["rejected"].get(reason,0)+1
        diagnostics["rejected_intervals"].append({"time":iso(datetime.fromtimestamp((t+STEP)/1000,timezone.utc)),"reason":reason})
    for t in sorted(maximum):
        p=t-STEP
        if p not in maximum or t not in minimum or t not in ct or p not in ct:
            reject("missing_counter_or_count");continue
        if min(ct[p],ct[t])<MIN_SAMPLES_PER_BIN:
            reject("insufficient_counter_samples");continue
        if not all(k in series for k,series in ((p,suspect_hi),(t,suspect_hi),(t,suspect_lo),(t,cs),(p,cs))) or cs[t]!=ct[t] or cs[p]!=ct[p]:
            reject("suspect_counter_unverified");continue
        if suspect_hi[p]!=suspect_lo[t] or suspect_lo[t]!=suspect_hi[t]:
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


def build_windows(accepted, anchor, now, qualities=None, *, graph=False, bridge_times=()):
    qualities=qualities or {}
    bridge_times=set(bridge_times)
    result={"windows":[],"series":{}}
    if not anchor or not 0<=now.timestamp()*1000-anchor<=90*60_000:
        return result
    def window(t, hours):
        n=hours*12
        values=[accepted.get(t-i*STEP) for i in range(n)]
        present=[v for v in values if v is not None]
        validated=sum(1 for i,v in enumerate(values) if v is not None and qualities.get(t-i*STEP)==RAW_QUALITY)
        estimated=len(present)-validated
        extra={"bridge_minutes":sum(t-i*STEP in bridge_times for i in range(n))*5} if graph else {}
        return {**extra,"hours":hours,"value":round(sum(present),3) if present else None,
                "covered_minutes":len(present)*5,"expected_minutes":hours*60,
                "complete":len(present)==n,"validated_complete":validated==n,
                "validated_minutes":validated*5,"estimated_minutes":estimated*5,
                "quality":"partial" if len(present)<n else "validated" if validated==n else "estimated",
                "method":METHOD,"threshold_eligible":False,
                "start_at":iso(datetime.fromtimestamp((t-hours*3600000)/1000,timezone.utc)),
                "end_at":iso(datetime.fromtimestamp(t/1000,timezone.utc))}
    result["windows"]=[window(anchor,h) for h in WINDOWS]
    for h in (1,24):
        rows=[]
        start=max(anchor-72*3600000,min(accepted,default=anchor))
        first=start+(h*12-1)*STEP
        if graph:first=min(first,anchor)
        for t in range(first,anchor+1,STEP):
            if anchor-t>24*3600000 and t%(6*STEP):
                continue
            row=window(t,h)
            if row["complete"] or (graph and row["covered_minutes"] and (t==anchor or t%(6*STEP)==0)):
                extra={"covered_minutes":row["covered_minutes"],"expected_minutes":h*60,"bridge_minutes":row["bridge_minutes"]} if graph else {}
                rows.append({**extra,"time":row["end_at"],"value":row["value"],
                             "interval_minutes":5 if anchor-t<=24*3600000 else 30,
                             "count":1 if anchor-t<=24*3600000 else 6,
                             "quality":row["quality"],"validated_minutes":row["validated_minutes"],
                             "estimated_minutes":row["estimated_minutes"]})
        result["series"][f"rain_{h}h"]=rows[-600:]
    return result


def summarize(groups, start, end, now):
    accepted, diagnostics=reconstruct(groups,start,end)
    totals=bucket_series(groups.get("MAX",{}).get("rain_total",[]),start,end,LIMIT)
    result=empty_rain("no_valid_intervals")
    result["diagnostics"]=diagnostics
    result["rejected_intervals"]=diagnostics.pop("rejected_intervals",[])
    if not totals or not diagnostics["suspect_bins"]:
        result["status"]="unavailable";return result
    result["query_start_at"]=iso(datetime.fromtimestamp(start/1000,timezone.utc))
    result["query_end_at"]=iso(datetime.fromtimestamp(end/1000,timezone.utc))
    anchor=max(totals)+STEP
    result["anchor_at"]=iso(datetime.fromtimestamp(anchor/1000,timezone.utc))
    result["intervals"]=[{"time":iso(datetime.fromtimestamp(t/1000,timezone.utc)),"value":v,"quality":AGG_QUALITY} for t,v in sorted(accepted.items())]
    result["status"]="available" if accepted else "no_valid_intervals"
    if not 0<=now.timestamp()*1000-anchor<=90*60_000:
        result["status"]="stale";return result
    result.update(build_windows(accepted,anchor,now,{t:AGG_QUALITY for t in accepted}))
    return result


def parse_intervals(rows, now_ms):
    """Old archives lack provenance and remain contextual estimates."""
    result={}
    if not isinstance(rows,list) or len(rows)>LIMIT:return result
    for row in rows:
        if not isinstance(row,dict):continue
        t=moment(row.get("time"));v=row.get("value")
        if not t or not valid_number(v,0,500):continue
        ms=int(t.timestamp()*1000);quality=row.get("quality",LEGACY_QUALITY)
        if now_ms-WINDOW_HOURS*3600000<=ms<=now_ms and ms%STEP==0 and quality in QUALITIES:
            result[ms]=(v,quality)
    return result


def parse_bridges(rows, now_ms):
    """Only display estimates from close, paired endpoints in one 5-minute bin."""
    out={}
    if not isinstance(rows,list) or len(rows)>LIMIT:return out
    for row in rows:
        if not isinstance(row,dict):continue
        times=[moment(row.get(k)) for k in ("time","first_at","last_at")]
        if not all(times):continue
        t,a,b=[int(v.timestamp()*1000) for v in times]
        values=[row.get(k) for k in ("value","total_first","total_last","daily_first","daily_last","suspects")]
        if (not now_ms-WINDOW_HOURS*3600000<=t<=now_ms or t%STEP
                or not 0<=t-STEP-a<=RAW_MAX_GAP_MS or not 0<t-b<=RAW_MAX_GAP_MS
                or not a<b or times[1].astimezone(TZ).date()!=times[2].astimezone(TZ).date()
                or not all(valid_number(v,0,1e12) for v in values)):continue
        value,first,last,daily_first,daily_last,_=values
        if (not valid_number(value,0,500) or last<first or daily_last<daily_first
                or not close(value,last-first) or not close(value,daily_last-daily_first)):continue
        out[t]=row
    return out


def merge_bridges(previous, current, records, blocked, now_ms):
    old=parse_bridges(previous,now_ms)
    new=parse_bridges(current,now_ms)
    for t,row in new.items():
        if t in old and not close(old[t]["value"],row["value"]):
            old.pop(t,None)
        else:old[t]=row
    return [row for t,row in sorted(old.items()) if t not in records and blocked.get(t) not in HARD_REASONS][-LIMIT:]


def add_graph(product, records, bridges, anchor, now):
    """Graph-only data; never writes a bridge to strict records/windows."""
    if not anchor:return
    recovered=parse_bridges(bridges,int(now.timestamp()*1000))
    values={t:v for t,(v,_) in records.items()}
    quality={t:q for t,(_,q) in records.items()}
    for t,row in recovered.items():
        if t not in values:
            values[t]=row["value"];quality[t]=AGG_QUALITY
    graph=build_windows(values,anchor,now,quality,graph=True,bridge_times=set(recovered)-set(records))
    product["graph_windows"]=[r for r in graph["windows"] if r["hours"] in (1,24)]
    product["graph_series"]=graph["series"]


def rejected_intervals(rows, now_ms):
    result={}
    if not isinstance(rows,list) or len(rows)>LIMIT:return result
    for r in rows:
        if not isinstance(r,dict):continue
        t=moment(r.get("time"));reason=r.get("reason")
        if t and reason in HARD_REASONS|{"raw_gap"}:
            ms=int(t.timestamp()*1000)
            if now_ms-WINDOW_HOURS*3600000<=ms<=now_ms and ms%STEP==0:result[ms]=reason
    return result


def serialize_intervals(records):
    return [{"time":iso(datetime.fromtimestamp(t/1000,timezone.utc)),"value":v,"quality":q}
            for t,(v,q) in sorted(records.items())][-LIMIT:]


def serialize_rejected(blocked):
    return [{"time":iso(datetime.fromtimestamp(t/1000,timezone.utc)),"reason":r}
            for t,r in sorted(blocked.items())][-LIMIT:]


def reconcile(records, blocked, product, now_ms):
    """Strong raw evidence outranks estimates; actual conflicts never vanish."""
    incoming=parse_intervals(product.get("intervals",[]),now_ms)
    for t,reason in rejected_intervals(product.get("rejected_intervals",[]),now_ms).items():
        if blocked.get(t) not in HARD_REASONS:blocked[t]=reason
        records.pop(t,None)
    for t,(v,q) in incoming.items():
        reason=blocked.get(t)
        if reason in HARD_REASONS or (reason=="raw_gap" and q!=RAW_QUALITY):continue
        if reason=="raw_gap":blocked.pop(t,None)
        old=records.get(t)
        if old:
            oldv,oldq=old
            if oldq==LEGACY_QUALITY:records[t]=(v,q);continue
            if not close(oldv,v):
                blocked[t]="source_conflict";records.pop(t,None);continue
            if oldq==RAW_QUALITY and q!=RAW_QUALITY:continue
        records[t]=(v,q)


def clean_attempts(attempts, now_ms):
    out={}
    if not isinstance(attempts,dict):return out
    for key,value in attempts.items():
        try:t=int(key);at=int(value)
        except (TypeError,ValueError):continue
        if t%STEP==0 and now_ms-WINDOW_HOURS*3600000<=t<=now_ms and now_ms-WINDOW_HOURS*3600000<=at<=now_ms:
            out[str(t)]=at
    return dict(sorted(out.items(),key=lambda item:int(item[0]))[-MAX_RECOVERY_ATTEMPTS:])


def merge_rain(previous, current, stamp):
    """Bounded provenance-aware archive; missing responses do not erase it."""
    now=moment(stamp);now_ms=int(now.timestamp()*1000)
    previous=previous or {};current=current or empty_rain()
    records=parse_intervals(previous.get("intervals",[]),now_ms)
    blocked=rejected_intervals(previous.get("rejected_intervals",[]),now_ms)
    reconcile(records,blocked,current,now_ms)
    for t in blocked:records.pop(t,None)
    anchors=[t for t in (moment(current.get("anchor_at")),moment(previous.get("anchor_at"))) if t and t<=now and now-t<=timedelta(hours=WINDOW_HOURS)]
    anchor=max(anchors,default=None)
    attempts=clean_attempts({**previous.get("attempts",{}),**current.get("attempts",{})},now_ms)
    archive={"intervals":serialize_intervals(records),"rejected_intervals":serialize_rejected(blocked),
             "anchor_at":iso(anchor) if anchor else None}
    if attempts:archive["attempts"]=attempts
    bridges=merge_bridges(previous.get("counter_bridges",[]),current.get("counter_bridges",[]),records,blocked,now_ms)
    if bridges:archive["counter_bridges"]=bridges
    product=empty_rain(current.get("status","unavailable"))
    quality_counts={q:sum(1 for _,kind in records.values() if kind==q) for q in QUALITIES}
    product["diagnostics"]={**current.get("diagnostics",{}),"retained_valid_bins":len(records),
                            "retained_by_quality":quality_counts,"blocked_bins":len(blocked),
                            "query_status":current.get("status","unavailable")}
    bounds=list(records)+list(blocked)
    product["authoritative_from"]=iso(datetime.fromtimestamp(min(bounds)/1000,timezone.utc)) if bounds else current.get("query_start_at")
    if anchor and 0<=now_ms-anchor.timestamp()*1000<=90*60_000:
        product["status"]="available" if records else "no_valid_intervals"
        product.update(build_windows({t:v for t,(v,_) in records.items()},int(anchor.timestamp()*1000),now,
                                     {t:q for t,(_,q) in records.items()}))
        add_graph(product,records,bridges,int(anchor.timestamp()*1000),now)
        product["diagnostics"]["graph_bridge_bins"]=len(bridges)
    elif anchor:product["status"]="stale"
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
             "flags":{},"rejected":{},"unknown":{},"confirmed":{},"rejected_bins":{}}
    for key,rows in flags.items():
        t=max(rows,default=None)
        summary["flags"][key]={"bins":len(rows),"latest":rows[t] if t is not None else None,
                              "time":iso(datetime.fromtimestamp(t/1000,timezone.utc)) if t is not None else None}
    for key,requirements in AFFECTED.items():
        if key not in metrics:continue
        rejected, unknown, confirmed=0,0,0
        blocked=set()
        def usable(p):
            nonlocal rejected,unknown,confirmed
            if not p:return False
            t=moment(p.get("time"))
            if not t:return False
            t=int(t.timestamp()*1000)//STEP*STEP
            values=[flags.get(f,{}).get(t) for f in requirements]
            if any(v is not None and v!=FLAGS[f] for f,v in zip(requirements,values)):
                rejected+=1;blocked.add(t);return False
            if any(v is None for v in values):unknown+=1
            else:confirmed+=1
            return True
        m=metrics[key]
        m["series"]=[p for p in m.get("series",[]) if usable(p)]
        if m.get("latest") and not usable(m["latest"]):
            m["latest"]=None;m["fresh_at_collection"]=False
        summary["rejected"][key]=rejected;summary["unknown"][key]=unknown;summary["confirmed"][key]=confirmed
        summary["rejected_bins"][key]=[iso(datetime.fromtimestamp(t/1000,timezone.utc)) for t in sorted(blocked)]
    return summary


def raw_rain(raw, start, end, now):
    """Pair original readings and require continuity at both boundaries."""
    from bisect import bisect_left
    conflicts_by_key={}
    def points(key):
        rows=raw.get(key,[])
        if not isinstance(rows,list) or len(rows)>RAW_LIMIT:return {}
        out,conflicts={},set()
        for r in rows:
            if not isinstance(r,dict):continue
            t,v=r.get("ts"),parse_number(r.get("value"))
            if not isinstance(t,int) or isinstance(t,bool) or not start<=t<=end or v is None or v<0:continue
            if t in out and out[t]!=v:conflicts.add(t)
            out[t]=v
        conflicts_by_key[key]=conflicts
        return {t:v for t,v in out.items() if t not in conflicts}
    total,suspects,daily,increment=(points(k) for k in ("rain_total","rain_suspects_total","rain_daily","rain_increment"))
    result=empty_rain()
    d={"retrieval_method":"bounded_raw_pairs","total_samples":len(total),"suspect_samples":len(suspects),
       "increment_samples":len(increment),"unit_evidence":{"documented_unit":TOTAL_UNIT,"status":"documented_mm"},
       "accepted_bins":0,"increment_checked_bins":0,"rejected":{}}
    result["diagnostics"]=d
    result["rejected_intervals"]=[]
    result["counter_bridges"]=[]
    if not total or not suspects:return result
    times=sorted(total);anchor=(times[-1]//STEP)*STEP
    if end-times[-1]<=RAW_MAX_GAP_MS:anchor=end
    result["query_start_at"]=iso(datetime.fromtimestamp(start/1000,timezone.utc))
    result["query_end_at"]=iso(datetime.fromtimestamp(end/1000,timezone.utc))
    result["observed_start_at"]=iso(datetime.fromtimestamp(times[0]/1000,timezone.utc))
    result["anchor_at"]=iso(datetime.fromtimestamp(anchor/1000,timezone.utc))
    accepted={}
    def reject(reason):
        d["rejected"][reason]=d["rejected"].get(reason,0)+1
        result["rejected_intervals"].append({"time":iso(datetime.fromtimestamp(t/1000,timezone.utc)),"reason":reason})
    for t in range(start+STEP,anchor+1,STEP):
        # Match MAX bins: last sample strictly before each boundary.
        a=bisect_left(times,t-STEP)-1;b=bisect_left(times,t)-1
        if a<0 and times[0]==t-STEP:a=0
        if a<0 or b<=a or t-STEP-times[a]>RAW_MAX_GAP_MS or t-times[b]>RAW_MAX_GAP_MS:
            reject("missing_boundary");continue
        sub=times[a:b+1]
        if any(sub[0]<=x<=sub[-1] for k in ("rain_total","rain_suspects_total","rain_daily","rain_increment") for x in conflicts_by_key.get(k,set())):
            reject("raw_conflict");continue
        gap=any(y-x>RAW_MAX_GAP_MS for x,y in zip(sub,sub[1:]))
        if any(x not in suspects for x in sub) or any(suspects[x]!=suspects[sub[0]] for x in sub):
            reject("suspect_counter_changed_or_missing");continue
        if any(total[y]<total[x] for x,y in zip(sub,sub[1:])):
            reject("counter_reset_or_decrease");continue
        delta=total[sub[-1]]-total[sub[0]]
        if not valid_number(delta,0,500):
            reject("invalid_counter_difference");continue
        first,last=sub[0],sub[-1]
        if first in daily and last in daily and datetime.fromtimestamp(first/1000,timezone.utc).astimezone(TZ).date()==datetime.fromtimestamp(last/1000,timezone.utc).astimezone(TZ).date() and daily[last]>=daily[first] and not close(delta,daily[last]-daily[first]):
            reject("daily_counter_mismatch");continue
        if all(x in increment for x in sub[1:]):
            if not close(delta,sum(increment[x] for x in sub[1:])):
                reject("counter_increment_mismatch");continue
            d["increment_checked_bins"]+=1
        elif sum(increment[x] for x in sub[1:] if x in increment)>delta+.025:
            reject("partial_increment_exceeds_counter");continue
        if gap:
            # Same-day independent daily counter corroboration is mandatory;
            # the strict raw gap veto is retained. No bridging midnight/reset.
            if (first in daily and last in daily and
                    datetime.fromtimestamp(first/1000,timezone.utc).astimezone(TZ).date()==datetime.fromtimestamp(last/1000,timezone.utc).astimezone(TZ).date()
                    and daily[last]>=daily[first] and close(delta,daily[last]-daily[first])):
                result["counter_bridges"].append({"time":iso(datetime.fromtimestamp(t/1000,timezone.utc)),
                    "first_at":iso(datetime.fromtimestamp(first/1000,timezone.utc)),
                    "last_at":iso(datetime.fromtimestamp(last/1000,timezone.utc)),
                    "value":round(delta,5),"total_first":total[first],"total_last":total[last],
                    "daily_first":daily[first],"daily_last":daily[last],"suspects":suspects[first]})
            reject("raw_gap");continue
        accepted[t]=round(delta,5)
    d["accepted_bins"]=len(accepted)
    result["intervals"]=[{"time":iso(datetime.fromtimestamp(t/1000,timezone.utc)),"value":v,"quality":RAW_QUALITY} for t,v in sorted(accepted.items())]
    result["status"]="available" if accepted else "no_valid_intervals"
    if not 0<=now.timestamp()*1000-anchor<=90*60_000:
        result["status"]="stale";return result
    result.update(build_windows(accepted,anchor,now,{t:RAW_QUALITY for t in accepted}))
    return result


def aggregate_query(requester,token,telemetry,start,end,now):
    from .campus_station import SourceError
    groups={}
    requests={"MAX":("rain_total","rain_daily","rain_suspects_total"),
              "MIN":("rain_total","rain_suspects_total"),
              "COUNT":("rain_total","rain_increment","rain_suspects_total")}
    try:
        for agg,keys in requests.items():
            groups[agg]=query(requester,token,telemetry,keys,start,end,agg,QUERY_HOURS*12+2)
            if agg=="MAX" and not groups[agg].get("rain_total"):return empty_rain()
        if groups["COUNT"].get("rain_increment"):
            try:groups["SUM"]=query(requester,token,telemetry,("rain_increment",),start,end,"SUM",QUERY_HOURS*12+2)
            except (SourceError,OSError,ValueError,TypeError,KeyError):groups["SUM"]={}
        return summarize(groups,start,end,now)
    except (SourceError,OSError,ValueError,TypeError,KeyError):
        return empty_rain()


def collect_rain(requester,token,telemetry,now,previous=None,*,budget_seconds=RECOVERY_BUDGET_SECONDS):
    """Raw + short aggregates, then bounded, resumable historical recovery."""
    from .campus_station import SourceError
    started=monotonic();now_ms=int(now.timestamp()*1000);end=now_ms//STEP*STEP
    previous=previous or {}
    records=parse_intervals(previous.get("intervals",[]),now_ms)
    blocked=rejected_intervals(previous.get("rejected_intervals",[]),now_ms)
    attempts=clean_attempts(previous.get("attempts",{}),now_ms)
    raw=empty_rain()
    raw_start=end-(RAW_HOURS*12+1)*STEP
    try:
        data=query(requester,token,telemetry,("rain_total","rain_daily","rain_suspects_total","rain_increment"),
                   raw_start,end,"NONE",RAW_LIMIT)
        raw=raw_rain(data,raw_start,end,now)
    except (SourceError,OSError,ValueError,TypeError,KeyError):
        pass
    reconcile(records,blocked,raw,now_ms)
    bridges=merge_bridges(previous.get("counter_bridges",[]),raw.get("counter_bridges",[]),records,blocked,now_ms)
    initial=not attempts
    # Repair holes within the known recent history before spending the budget
    # on older aggregate chunks. Raw gaps require original evidence; hard vetoes
    # remain permanent. Bound each repair to a small query and the shared budget.
    raw_repairs=missing_repairs=0
    def repair_recent():
        nonlocal raw_repairs,missing_repairs,bridges
        if raw_repairs+missing_repairs>=MAX_RAW_REPAIRS or monotonic()-started>=budget_seconds:
            return
        floor=max(end-RAW_REPAIR_HOURS*3600000,min(list(records)+list(blocked),default=end))
        ceiling=raw_start  # the primary raw query already covers newer intervals
        candidates=[t for t in range(floor,ceiling+1,STEP)
                    if t not in records and blocked.get(t) not in HARD_REASONS
                    and now_ms-attempts.get(str(t),0)>=RETRY_MS]
        if not candidates:return
        t=max(candidates,key=lambda t:(blocked.get(t)=="raw_gap",t))
        if blocked.get(t)=="raw_gap":raw_repairs+=1
        else:missing_repairs+=1
        attempts[str(t)]=now_ms
        try:
            data=query(requester,token,telemetry,("rain_total","rain_daily","rain_suspects_total","rain_increment"),
                       t-2*STEP,min(end,t+STEP),"NONE",RAW_LIMIT)
            repair=raw_rain(data,t-2*STEP,min(end,t+STEP),now)
            # The surrounding readings only establish boundaries. Reconcile the
            # requested gap, not unrelated archived intervals.
            target=iso(datetime.fromtimestamp(t/1000,timezone.utc))
            repair["intervals"]=[r for r in repair.get("intervals",[]) if r["time"]==target]
            repair["rejected_intervals"]=[r for r in repair.get("rejected_intervals",[]) if r["time"]==target]
            reconcile(records,blocked,repair,now_ms)
            bridges=merge_bridges(bridges,[r for r in repair.get("counter_bridges",[]) if r["time"]==target],records,blocked,now_ms)
        except (SourceError,OSError,ValueError,TypeError,KeyError):
            pass
    repair_recent()
    recent_start=end-QUERY_HOURS*3600000
    missing_recent=any(t not in records for t in range(recent_start+2*STEP,end+1,STEP))
    raw_full=any(w["hours"]==1 and w.get("validated_complete") for w in raw["windows"])
    recent=empty_rain()
    if (missing_recent or not raw_full) and monotonic()-started<budget_seconds:
        recent=aggregate_query(requester,token,telemetry,recent_start,end,now)
        reconcile(records,blocked,recent,now_ms)
    repair_recent()
    limit=MAX_INITIAL_CHUNKS if initial else MAX_REPAIR_CHUNKS
    recovered=available=0
    oldest=end-WINDOW_HOURS*3600000
    anchors=[moment(r.get("anchor_at")) for r in (raw,recent,previous)]
    if raw["status"]!="unavailable" or recent["status"]!="unavailable":
        chunk_end=(end//CHUNK_MS)*CHUNK_MS
        while chunk_end>oldest and recovered<limit and monotonic()-started<budget_seconds:
            chunk_start=max(oldest,chunk_end-CHUNK_MS)
            key=str(chunk_end)
            if chunk_end>recent_start and chunk_start>=recent_start+STEP:
                chunk_end-=CHUNK_MS;continue
            if all(t in records or blocked.get(t) in HARD_REASONS for t in range(chunk_start+STEP,chunk_end+1,STEP)):
                chunk_end-=CHUNK_MS;continue
            if now_ms-attempts.get(key,0)<RETRY_MS:
                chunk_end-=CHUNK_MS;continue
            product=aggregate_query(requester,token,telemetry,chunk_start-STEP,chunk_end,now)
            attempts[key]=now_ms;recovered+=1;available+=product["status"]!="unavailable"
            anchors.append(moment(product.get("anchor_at")))
            reconcile(records,blocked,product,now_ms)
            chunk_end-=CHUNK_MS
    for t in blocked:records.pop(t,None)
    result=empty_rain()
    anchor=max((t for t in anchors if t and t<=now and now-t<=timedelta(hours=WINDOW_HOURS)),default=None)
    result["anchor_at"]=iso(anchor) if anchor else None
    result["intervals"]=serialize_intervals(records)
    result["rejected_intervals"]=serialize_rejected(blocked)
    result["attempts"]=clean_attempts(attempts,now_ms)
    result["counter_bridges"]=merge_bridges(bridges,[],records,blocked,now_ms)
    result["diagnostics"]={"retrieval_method":"hybrid_raw_and_aggregated","raw":raw["diagnostics"],
                           "recent_aggregate":recent["diagnostics"],
                           "historical_chunks_attempted":recovered,"historical_chunks_available":available,
                           "raw_gap_repairs_attempted":raw_repairs,"raw_missing_repairs_attempted":missing_repairs,
                           "raw_bins":sum(q==RAW_QUALITY for _,q in records.values()),
                           "aggregate_bins":sum(q==AGG_QUALITY for _,q in records.values()),
                           "rejected_bins":len(blocked),"query_budget_seconds":budget_seconds}
    if anchor:
        result["status"]="available" if records else "no_valid_intervals"
        if now-anchor>timedelta(minutes=90):result["status"]="stale"
        else:result.update(build_windows({t:v for t,(v,_) in records.items()},int(anchor.timestamp()*1000),now,{t:q for t,(_,q) in records.items()}))
    return result


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
    previous_time=None
    for row in product.get("intervals",[]):
        t=moment(row.get("time")) if isinstance(row,dict) else None
        if (not t or not now-timedelta(hours=WINDOW_HOURS)<=t<=now or int(t.timestamp()*1000)%STEP
                or (previous_time and t<=previous_time) or row.get("quality",LEGACY_QUALITY) not in QUALITIES
                or not valid_number(row.get("value"),0,500)):
            raise ValueError("Invalid IFC interval provenance")
        previous_time=t
    if len(product.get("rejected_intervals",[]))>LIMIT or len(product.get("attempts",{}))>MAX_RECOVERY_ATTEMPTS:
        raise ValueError("Unbounded IFC recovery metadata")
    seen=set()
    for r in product["windows"]:
        h=r.get("hours");a=moment(r.get("start_at"));b=moment(r.get("end_at"));n=r.get("covered_minutes")
        if (h not in WINDOWS or h in seen or not a or not b or not a<b<=now or b-a!=timedelta(hours=h)
                or r.get("expected_minutes")!=h*60 or not isinstance(n,int) or isinstance(n,bool) or n%5 or not 0<=n<=h*60
                or r.get("complete") is not (n==h*60) or r.get("threshold_eligible") is not False
                or r.get("method")!=METHOD or (n>0 and not valid_number(r.get("value"),0,500*n/5))
                or (n==0 and r.get("value") is not None)):
            raise ValueError("Invalid IFC rain window")
        if "quality" in r:
            v,e=r.get("validated_minutes"),r.get("estimated_minutes")
            if (not isinstance(v,int) or not isinstance(e,int) or min(v,e)<0 or v%5 or e%5 or v+e!=n
                    or r.get("validated_complete") is not (v==h*60)
                    or r["quality"]!=("partial" if n<h*60 else "validated" if v==n else "estimated")):
                raise ValueError("Invalid IFC rain coverage provenance")
        seen.add(h)
    for key,rows in product["series"].items():
        if not isinstance(rows,list) or len(rows)>600:raise ValueError("Unbounded IFC rain series")
        last=None
        for r in rows:
            t=moment(r.get("time"))
            if (not t or not now-timedelta(hours=73)<=t<=now or (last and t<=last)
                    or not valid_number(r.get("value"),0,144000)
                    or r.get("interval_minutes") not in (5,30)
                    or r.get("quality","estimated") not in ("validated","estimated")):
                raise ValueError("Invalid IFC rain series")
            last=t
    bridges=product.get("counter_bridges",[])
    if not isinstance(bridges,list) or len(parse_bridges(bridges,int(now.timestamp()*1000)))!=len(bridges):
        raise ValueError("Invalid IFC graph counter bridge")
    graph_windows=product.get("graph_windows",[])
    graph_series=product.get("graph_series",{})
    if not isinstance(graph_windows,list) or len(graph_windows)>2 or not isinstance(graph_series,dict) or set(graph_series)-{"rain_1h","rain_24h"}:
        raise ValueError("Unbounded IFC graph rain")
    def check_graph(row,h):
        n,v,e,b=(row.get(k) for k in ("covered_minutes","validated_minutes","estimated_minutes","bridge_minutes"))
        if (h not in (1,24) or row.get("expected_minutes")!=h*60 or
                not all(isinstance(x,int) and not isinstance(x,bool) and x>=0 and x%5==0 for x in (n,v,e,b)) or
                n!=v+e or b>e or n>h*60 or row.get("quality")!=("partial" if n<h*60 else "validated" if v==n else "estimated") or
                (n>0 and not valid_number(row.get("value"),0,500*n/5)) or (n==0 and row.get("value") is not None)):
            raise ValueError("Invalid IFC graph rain provenance")
    for r in graph_windows:
        check_graph(r,r.get("hours"))
        if r.get("threshold_eligible") is not False or r.get("complete") is not (r["covered_minutes"]==r["hours"]*60):
            raise ValueError("Invalid IFC graph-only window")
    for key,rows in graph_series.items():
        if not isinstance(rows,list) or len(rows)>600:raise ValueError("Unbounded IFC graph series")
        previous=None
        for row in rows:
            check_graph(row,1 if key=="rain_1h" else 24)
            t=moment(row.get("time"))
            if not t or not now-timedelta(hours=73)<=t<=now or (previous and t<=previous) or row["covered_minutes"]==0 or row.get("interval_minutes") not in (5,30):
                raise ValueError("Invalid IFC graph sample")
            previous=t
    if product["status"]!="available" and any(r["complete"] for r in product["windows"]):
        raise ValueError("Unavailable IFC rain cannot be complete")
    return product
