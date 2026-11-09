"""Read-only public IFC station telemetry; never an input to risk classification."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

BASE = "https://mytb.fabricadesoftware.ifc.edu.br"
PUBLIC_ID = "f2146870-34a4-11f0-ac33-dfcfe81f8a64"
DEVICE_ID = "948e1e60-5611-11f0-ac33-dfcfe81f8a64"
SOURCE = BASE + "/dashboard/6c46c4f0-5613-11f0-ac33-dfcfe81f8a64?publicId=" + PUBLIC_ID
TELEMETRY = "/api/plugins/telemetry/DEVICE/" + DEVICE_ID + "/values/timeseries"
KIND = "ifc_araquari_campus_observations_not_risk_criteria"
MAX_AGE_MINUTES = 90
MAX_POINTS = 300
# Ranges reject malformed/sentinel values, not establish risk thresholds.
METRICS = {
    "temperature": ("Temperatura", "°C", -50, 65, "AVG"),
    "humidity": ("Umidade relativa", "%", 0, 100, "AVG"),
    "pressure": ("Pressão atmosférica", "hPa", 800, 1100, "AVG"),
    "rain_daily": ("Chuva acumulada no dia", "mm", 0, 2000, "MAX"),
    "rain_intensity": ("Intensidade da chuva", "mm/h", 0, 2000, "MAX"),
    "wind_avg": ("Vento médio informado", "km/h", 0, 400, "AVG"),
    "wind_gust": ("Rajada informada", "km/h", 0, 400, "MAX"),
    "wind_direction_deg": ("Direção do vento", "°", 0, 360, None),
}


class SourceError(RuntimeError):
    pass


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(path: str, *, body: dict | None = None, token: str | None = None) -> Any:
    if path.split("?")[0] not in ("/api/auth/login/public", TELEMETRY):
        raise SourceError("invalid_request")
    headers = {"Accept": "application/json", "User-Agent": "criseclimatica/1.1"}
    if token:
        headers["X-Authorization"] = "Bearer " + token
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    try:
        with build_opener(_NoRedirect()).open(req, timeout=12) as response:
            raw = response.read(600_001)
            if len(raw) > 600_000:
                raise SourceError("response_too_large")
        return json.loads(raw)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        # Never include request headers, token or the authentication response.
        raise SourceError("source_unavailable") from exc


def empty(stamp: str, status: str = "unavailable") -> dict:
    return {"schema_version": 1, "kind": KIND, "location_id": "araquari",
            "station_name": "IFC Araquari", "source_url": SOURCE,
            "device_id": DEVICE_ID, "checked_at": stamp, "status": status,
            "risk_criteria": False, "max_age_minutes": MAX_AGE_MINUTES,
            "window_hours": 24, "interval_minutes": 5, "metrics": {},
            "diagnostics": {"rejected_readings": 0, "conflicting_timestamps": 0}}


def clean_points(raw: Any, key: str, start: datetime, end: datetime) -> tuple[list[dict], int, int]:
    if not isinstance(raw, list) or len(raw) > MAX_POINTS:
        raise SourceError("invalid_telemetry_shape")
    values: dict[int, float] = {}
    conflicts: set[int] = set()
    rejected = 0
    minimum, maximum = METRICS[key][2:4]
    for row in raw:
        if not isinstance(row, dict):
            rejected += 1
            continue
        ts, value = row.get("ts"), row.get("value")
        if isinstance(ts, bool) or not isinstance(ts, int) or not start.timestamp()*1000 <= ts <= end.timestamp()*1000:
            rejected += 1
            continue
        if isinstance(value, bool):
            rejected += 1
            continue
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            rejected += 1
            continue
        if not math.isfinite(number) or not minimum <= number <= maximum:
            rejected += 1
            continue
        if ts in values and values[ts] != number:
            conflicts.add(ts)
        values[ts] = number
    points = [{"time": iso(datetime.fromtimestamp(ts/1000, timezone.utc)), "value": value}
              for ts, value in sorted(values.items()) if ts not in conflicts]
    return points, rejected, len(conflicts)


def collect(stamp: str, *, now: datetime | None = None,
            requester: Callable = request_json) -> dict:
    now = now or datetime.now(timezone.utc)
    result = empty(iso(now))
    start = now - timedelta(hours=24)
    result.update(window_start=iso(start), window_end=iso(now))
    try:
        auth = requester("/api/auth/login/public", body={"publicId": PUBLIC_ID})
        token = auth.get("token") if isinstance(auth, dict) else None
        if not isinstance(token, str) or not 1 <= len(token) <= 8192 or any(c.isspace() for c in token):
            raise SourceError("invalid_public_session")
        common = {"startTs": int(start.timestamp()*1000), "endTs": int(now.timestamp()*1000), "orderBy": "DESC"}
        # Never use the unbounded latest endpoint: future-dated values exist in
        # the source and win that query even when current history is healthy.
        latest = requester(TELEMETRY + "?" + urlencode({**common, "keys": ",".join(METRICS), "agg": "NONE", "limit": 20}), token=token)
        history = {}
        for aggregation in ("AVG", "MAX"):
            keys = [key for key, config in METRICS.items() if config[4] == aggregation]
            group = requester(TELEMETRY + "?" + urlencode({**common, "keys": ",".join(keys), "agg": aggregation,
                                                        "interval": 300_000, "limit": MAX_POINTS}), token=token)
            if not isinstance(group, dict):
                raise SourceError("invalid_telemetry_shape")
            history.update(group)
        if not isinstance(latest, dict):
            raise SourceError("invalid_telemetry_shape")
        for key, (label, unit, _, _, aggregation) in METRICS.items():
            recent, bad, conflicts = clean_points(latest.get(key, []), key, start, now)
            points, history_bad, history_conflicts = clean_points(history.get(key, []), key, start, now)
            last = recent[-1] if recent else None
            fresh = bool(last and datetime.fromisoformat(last["time"].replace("Z", "+00:00")) >= now-timedelta(minutes=MAX_AGE_MINUTES))
            result["metrics"][key] = {"label": label, "unit": unit, "latest": last, "fresh_at_collection": fresh,
                                      "aggregation": aggregation, "series": points}
            result["diagnostics"]["rejected_readings"] += bad + history_bad
            result["diagnostics"]["conflicting_timestamps"] += conflicts + history_conflicts
        result["status"] = ("available" if any(row["fresh_at_collection"] for row in result["metrics"].values())
                            else "stale" if any(row["latest"] or row["series"] for row in result["metrics"].values())
                            else "no_recent_data")
        if result["status"] == "no_recent_data":
            result["metrics"] = {}
    except (SourceError, HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError):
        result = empty(iso(now))
        result["diagnostic"] = "public_station_query_failed"
    return result


def validate_product(feed: dict, *, fixture: bool = False) -> None:
    if (feed.get("schema_version") != 1 or feed.get("kind") != KIND or feed.get("risk_criteria") is not False
            or feed.get("location_id") != "araquari" or feed.get("device_id") != DEVICE_ID
            or feed.get("source_url") != SOURCE or feed.get("max_age_minutes") != MAX_AGE_MINUTES
            or feed.get("status") not in ("available", "stale", "no_recent_data", "unavailable", "fixture_mode")
            or (feed.get("status") == "fixture_mode" and not fixture)
            or not isinstance(feed.get("metrics"), dict) or not set(feed["metrics"]).issubset(METRICS)):
        raise ValueError("Invalid campus station product")
    now = datetime.fromisoformat(feed["checked_at"].replace("Z", "+00:00"))
    if now.tzinfo is None:
        raise ValueError("Campus station time must include timezone")
    if feed["status"] in ("unavailable", "no_recent_data", "fixture_mode") and feed["metrics"]:
        raise ValueError("Unavailable campus station cannot contain readings")
    if feed["status"] in ("available", "stale"):
        start = datetime.fromisoformat(feed["window_start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(feed["window_end"].replace("Z", "+00:00"))
        if end != now or end-start != timedelta(hours=24):
            raise ValueError("Invalid campus history window")
        any_fresh = False
        for key, metric in feed["metrics"].items():
            if metric.get("unit") != METRICS[key][1] or metric.get("aggregation") != METRICS[key][4]:
                raise ValueError("Invalid campus metric unit or aggregation")
            points = metric.get("series")
            if not isinstance(points, list) or len(points) > MAX_POINTS:
                raise ValueError("Unbounded campus series")
            records = points + ([metric["latest"]] if metric.get("latest") else [])
            for group in (points, [metric["latest"]] if metric.get("latest") else []):
                raw = [{"ts": int(datetime.fromisoformat(p["time"].replace("Z", "+00:00")).timestamp()*1000), "value": p["value"]} for p in group]
                clean, bad, conflicts = clean_points(raw, key, start, end)
                if (bad or conflicts or len(clean) != len(group)
                        or any(not isinstance(p["value"], (int, float)) or isinstance(p["value"], bool) for p in group)
                        or [p["time"] for p in group] != sorted(p["time"] for p in group)):
                    raise ValueError("Invalid campus reading")
            last = metric.get("latest")
            fresh = bool(last and datetime.fromisoformat(last["time"].replace("Z", "+00:00")) >= now-timedelta(minutes=MAX_AGE_MINUTES))
            if metric.get("fresh_at_collection") is not fresh:
                raise ValueError("Invalid campus freshness")
            any_fresh |= fresh
        if (feed["status"] == "available") is not any_fresh:
            raise ValueError("Invalid campus availability")
