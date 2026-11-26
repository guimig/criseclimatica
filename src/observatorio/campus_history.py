"""Bounded IFC instrumental history and contextual indicators, not risk thresholds."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from math import atan2, cos, degrees, hypot, log, radians, sin
from statistics import mean
from zoneinfo import ZoneInfo

from .analysis import iso, moment, valid_number
from .campus_station import METRICS

TZ = ZoneInfo("America/Sao_Paulo")
HOURS = 24
DAYS = 7
MAX_PER_METRIC = 600
BOUNDS = {k: v[2:4] for k, v in METRICS.items()}
BOUNDS["rain_1h"] = (0, 2000)


def bucket(t, minutes):
    return t.replace(minute=t.minute // minutes * minutes, second=0, microsecond=0)


def sample(t, value, minutes=5, count=1, minimum=None, maximum=None):
    return {"time": iso(t), "value": round(value, 4), "interval_minutes": minutes,
            "count": count, "minimum": round(value if minimum is None else minimum, 4),
            "maximum": round(value if maximum is None else maximum, 4)}


def circular(values):
    x, y = mean(cos(radians(v)) for v in values), mean(sin(radians(v)) for v in values)
    return degrees(atan2(y, x)) % 360 if hypot(x, y) > 1e-6 else None


def validate_history(history, stamp):
    if not isinstance(history, dict) or history.get("version") != 1 or not isinstance(history.get("series"), dict):
        raise ValueError("Invalid IFC instrumental history")
    now = moment(stamp)
    for key, rows in history["series"].items():
        if key not in BOUNDS or not isinstance(rows, list) or len(rows) > MAX_PER_METRIC:
            raise ValueError("Unbounded IFC instrumental history")
        last = None
        for row in rows:
            t = moment(row.get("time"))
            n, count = row.get("interval_minutes"), row.get("count")
            if (not t or not now-timedelta(days=DAYS) <= t <= now or (last and t <= last)
                    or n not in (5, 30) or t != bucket(t, 5)
                    or not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= n//5
                    or not all(valid_number(row.get(f), *BOUNDS[key]) for f in ("value", "minimum", "maximum"))
                    or not row["minimum"] <= row["value"] <= row["maximum"]):
                raise ValueError("Invalid IFC instrumental sample")
            last = t
    return history


def recent_bins(campus, now):
    """The provider reports five-minute aggregates; direction is sampled, not averaged."""
    if campus.get("status") not in ("available", "stale"):
        return {}
    metrics = campus.get("metrics", {})
    data = {}
    for key in METRICS:
        by_bin = defaultdict(list)
        for p in metrics.get(key, {}).get("series", []):
            t = moment(p.get("time"))
            if t and now-timedelta(hours=HOURS) <= t <= now and valid_number(p.get("value"), *BOUNDS[key]):
                by_bin[bucket(t, 5)].append((t, p["value"]))
        values = {}
        for t, pairs in by_bin.items():
            if key == "wind_direction_deg":
                latest = max(p[0] for p in pairs)
                unique = {v for at, v in pairs if at == latest}
            else:
                unique = {v for _, v in pairs}
            if len(unique) == 1:
                values[t] = sample(t, unique.pop())
        data[key] = values
    # Existing known sensor fault must not contaminate history or derived indices.
    for t in set(data.get("temperature", {})) & set(data.get("humidity", {})):
        if data["temperature"][t]["value"] == data["humidity"][t]["value"] == 0:
            del data["temperature"][t]
            del data["humidity"][t]
    return data


def rolling_hour(counter, now):
    """Same-day, contiguous counter differences only. Five-minute approximation."""
    result = {}
    for end in sorted(counter):
        start = end-timedelta(hours=1)
        if not now-timedelta(hours=HOURS) <= end <= now or start.astimezone(TZ).date() != end.astimezone(TZ).date():
            continue
        times = [start+timedelta(minutes=5*i) for i in range(13)]
        if not all(t in counter for t in times):
            continue
        values = [counter[t]["value"] for t in times]
        if any(b < a for a, b in zip(values, values[1:])):
            continue
        result[end] = sample(end, round(values[-1]-values[0], 4))
    return result


def aggregate(key, rows, start):
    values = [r["value"] for r in rows]
    if key == "wind_direction_deg":
        value = circular(values)
        if value is None:
            return None
        return sample(start+timedelta(minutes=25), value, 30, len(rows), 0, 360)
    # Rolling accumulations are sampled at their last available termination,
    # never summed or averaged. Other MAX fields retain their observed peak.
    if key == "rain_1h":
        return sample(moment(rows[-1]["time"]), values[-1], 30, len(rows), min(values), max(values))
    value = max(values) if METRICS[key][4] == "MAX" else mean(values)
    return sample(start+timedelta(minutes=25), value, 30, len(rows), min(values), max(values))


def merge(previous, campus, stamp):
    now = moment(stamp)
    previous = previous or {"version": 1, "series": {}}
    # Previous product was already validated at its own publication; reject
    # malformed shape before combining it. Allow old samples to expire normally.
    if previous.get("version") != 1 or not isinstance(previous.get("series"), dict):
        raise ValueError("Invalid previous IFC instrumental history")
    if previous.get("generated_at"):
        validate_history(previous, previous["generated_at"])
    recent = recent_bins(campus, now)
    cutoff = bucket(now-timedelta(hours=HOURS), 30)
    earliest = now-timedelta(days=DAYS)
    old_series = previous["series"]
    counter = {moment(r["time"]): r for r in old_series.get("rain_daily", [])
               if r.get("interval_minutes") == 5 and moment(r["time"]) >= cutoff-timedelta(hours=1)}
    counter.update(recent.get("rain_daily", {}))
    recent["rain_1h"] = rolling_hour(counter, now)
    series = {}
    for key in BOUNDS:
        fine = {}
        coarse = {}
        for row in old_series.get(key, []):
            t = moment(row.get("time"))
            if not t or not earliest <= t <= now:
                continue
            if row["interval_minutes"] == 5:
                fine[t] = row
            else:
                coarse[bucket(t, 30)] = row
        # The latest successful bounded query is authoritative for those
        # buckets it actually returned. No missing reading becomes zero.
        fine.update(recent.get(key, {}))
        groups = defaultdict(list)
        for t, row in sorted(fine.items()):
            if t < cutoff:
                groups[bucket(t, 30)].append(row)
        for start, rows in groups.items():
            if start not in coarse:
                row = aggregate(key, rows, start)
                if row and moment(row["time"]) >= earliest:
                    coarse[start] = row
        rows = [r for r in coarse.values() if earliest <= moment(r["time"]) < cutoff]
        rows.extend(r for t, r in fine.items() if cutoff <= t <= now)
        series[key] = sorted(rows, key=lambda r: r["time"])[-MAX_PER_METRIC:]
    result = {"version": 1, "generated_at": stamp, "retention_days": DAYS,
              "fine_hours": HOURS, "series": series}
    return validate_history(result, stamp)


def pressure_change(rows):
    if not rows:
        return None
    last = rows[-1]
    target = moment(last["time"])-timedelta(hours=3)
    older = min(rows, key=lambda r: abs((moment(r["time"])-target).total_seconds()))
    if abs((moment(older["time"])-target).total_seconds()) > 600:
        return None
    return round(last["value"]-older["value"], 2)


def rain_context(counter, now):
    """Observed same-day increments; never claim a complete cross-reset total."""
    if not counter:
        return []
    end = max(counter)
    if now-end > timedelta(minutes=90):
        return []
    result = []
    for hours in (1, 3, 6, 12, 24):
        start = end-timedelta(hours=hours)
        times = sorted(t for t in counter if start <= t <= end)
        valid = [(a, b) for a, b in zip(times, times[1:])
                 if b-a == timedelta(minutes=5) and a.astimezone(TZ).date() == b.astimezone(TZ).date()
                 and counter[b]["value"] >= counter[a]["value"]]
        if not valid:
            continue
        amount = sum(counter[b]["value"]-counter[a]["value"] for a, b in valid)
        complete = len(valid) == hours*12 and times[0] == start and times[-1] == end
        result.append({"hours": hours, "value": round(amount, 3), "covered_minutes": len(valid)*5,
                       "expected_minutes": hours*60, "complete": complete,
                       "method": "same_day_counter_differences_5min_approximation",
                       "start_at": iso(start), "end_at": iso(end), "threshold_eligible": False})
    return result


def contextual(campus, stamp):
    now = moment(stamp)
    bins = recent_bins(campus, now)
    def rows(key):
        return sorted(bins.get(key, {}).values(), key=lambda r: r["time"])
    result = {"generated_at": stamp, "coverage": {}, "rain_windows": rain_context(bins.get("rain_daily", {}), now),
              "temperature": None, "pressure_change_3h": None, "dew_point_c": None, "heat_index_c": None,
              "thermohygrometric_at": None, "gust_peak_24h": None, "wind_sectors": None}
    for key in METRICS:
        points = rows(key)
        result["coverage"][key] = {"bins": len(points), "expected_bins": 288,
                                  "latest_at": points[-1]["time"] if points else None}
    temperatures = rows("temperature")
    if temperatures:
        result["temperature"] = {"minimum_5min_mean": min(r["value"] for r in temperatures),
                                 "maximum_5min_mean": max(r["value"] for r in temperatures)}
    gusts = rows("wind_gust")
    if gusts:
        result["gust_peak_24h"] = max(gusts, key=lambda r: r["value"])
    pressure = rows("pressure")
    if pressure and now-moment(pressure[-1]["time"]) <= timedelta(minutes=90):
        result["pressure_change_3h"] = pressure_change(pressure)
    paired = set(bins.get("temperature", {})) & set(bins.get("humidity", {}))
    if paired:
        t = max(paired)
        temperature, humidity = bins["temperature"][t]["value"], bins["humidity"][t]["value"]
        if now-t <= timedelta(minutes=90) and humidity > 0:
            alpha = log(humidity/100)+17.62*temperature/(243.12+temperature)
            result["dew_point_c"] = round(243.12*alpha/(17.62-alpha), 1)
            result["thermohygrometric_at"] = iso(t)
            f = temperature*1.8+32
            if f >= 80 and humidity >= 40:
                h = humidity
                hi = (-42.379+2.04901523*f+10.14333127*h-.22475541*f*h-.00683783*f*f
                      -.05481717*h*h+.00122874*f*f*h+.00085282*f*h*h-.00000199*f*f*h*h)
                result["heat_index_c"] = round((hi-32)/1.8, 1)
    paired = set(bins.get("wind_direction_deg", {})) & set(bins.get("wind_avg", {}))
    counts = [0]*8
    for t in paired:
        if bins["wind_avg"][t]["value"] > 0:
            counts[int((bins["wind_direction_deg"][t]["value"]+22.5)//45)%8] += 1
    if sum(counts):
        result["wind_sectors"] = {"labels": ["N","NE","L","SE","S","SO","O","NO"], "counts": counts,
                                  "sample_count": sum(counts), "method": "direction_samples_with_nonzero_paired_wind"}
    return result


def recent_wind_peaks(campus, stamp):
    """Retrieve positive extrema between collection cycles; do not verify sensor interval."""
    now = moment(stamp)
    if campus.get("status") != "available":
        return []
    rows = recent_bins(campus, now)
    peaks = []
    for key in ("wind_avg", "wind_gust"):
        points = [r for t, r in rows.get(key, {}).items() if now-t <= timedelta(hours=1)]
        if points:
            peaks.append((key, max(points, key=lambda r: (r["value"], r["time"]))))
    return peaks
