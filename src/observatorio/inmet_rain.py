"""Optional observed hourly rainfall from token-authenticated INMET stations.

A station measures its own location, not all municipalities nearby.  Raw INMET
measurements are not validated by INMET.  This provider is disabled unless an
INMET_API_TOKEN is configured.  Never include token-bearing URLs in logs.
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .inmet import haversine_km

SOURCE = "https://portal.inmet.gov.br/servicos/esta%C3%A7%C3%B5es-autom%C3%A1ticas"
API_ROOT = "https://apitempo.inmet.gov.br/token/estacao"
KIND = "inmet_automatic_station_hourly_observed_rain_unvalidated"
CODE = re.compile(r"A\d{3,4}")
MAX_STATIONS = 5
MAX_DISTANCE_KM = 90.0
MAX_AGE_HOURS = 6
MAX_ROWS = 250


class RainSourceError(RuntimeError):
    """Provider failure with a controlled public diagnostic; never expose URL/token."""
    def __init__(self, message: str, reason: str = "unavailable"):
        super().__init__(message)
        self.reason = reason


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None  # Protect path-based provider credentials from redirected hosts.


def candidates(catalog: dict[str, Any], locations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pick a bounded number of geographically nearby registered INMET stations."""
    if (not isinstance(catalog, dict) or catalog.get("kind") != "station_catalog_metadata_not_measurements"
            or not isinstance(catalog.get("locations"), list)):
        return []
    by_code: dict[str, dict[str, Any]] = {}
    for item in catalog["locations"]:
        if not isinstance(item, dict) or not isinstance(item.get("stations"), list):
            continue
        for station in item["stations"]:
            if not isinstance(station, dict) or not isinstance(station.get("code"), str):
                continue
            code = station["code"]
            if not CODE.fullmatch(code):
                continue
            try:
                lat, lon = float(station["latitude"]), float(station["longitude"])
                distance = min(haversine_km(lat, lon, loc["latitude"], loc["longitude"]) for loc in locations)
            except (KeyError, TypeError, ValueError):
                continue
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180
                    and math.isfinite(distance) and distance <= MAX_DISTANCE_KM):
                continue
            previous = by_code.get(code)
            if previous is None or distance < previous["distance_km"]:
                by_code[code] = {"code": code, "name": str(station.get("name") or code)[:100],
                                 "latitude": lat, "longitude": lon, "distance_km": round(distance, 1)}
    return sorted(by_code.values(), key=lambda x: (x["distance_km"], x["code"]))[:MAX_STATIONS]


def _rain(value: Any) -> float | None:
    """Handle INMET numeric strings and documented missing-value sentinels."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value.replace(",", ".")) if isinstance(value, str) else float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return round(number, 2) if math.isfinite(number) and 0 <= number <= 500 else None


def _moment(row: dict[str, Any]) -> datetime | None:
    day, hour = row.get("DT_MEDICAO"), row.get("HR_MEDICAO")
    if not isinstance(day, str) or not isinstance(hour, (str, int)):
        return None
    hour = str(hour).zfill(4)
    if not re.fullmatch(r"\d{4}", hour):
        return None
    try:
        return datetime.strptime(day + " " + hour, "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def normalize_station_rows(raw: Any, code: str, now: datetime) -> dict[str, Any] | None:
    """Return recent station measurement with 24h total only for complete hourly coverage."""
    if not isinstance(raw, list) or len(raw) > MAX_ROWS:
        raise RainSourceError("Invalid INMET hourly observation structure")
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    now = now.astimezone(timezone.utc)
    hourly: dict[datetime, float | None] = {}
    for row in raw:
        if not isinstance(row, dict) or str(row.get("CD_ESTACAO", "")).strip().upper() != code:
            continue
        moment = _moment(row)
        if moment is None or moment > now + timedelta(minutes=10) or moment < now - timedelta(days=3):
            continue
        rain = _rain(row.get("CHUVA"))
        if moment in hourly and hourly[moment] != rain:
            # Conflicting values for one station/hour are not safe to consolidate.
            raise RainSourceError("Conflicting duplicate INMET hourly observation")
        hourly[moment] = rain
    if not hourly:
        return None
    most_recent = max(hourly)
    if now - most_recent > timedelta(hours=MAX_AGE_HOURS):
        return None
    first = most_recent - timedelta(hours=23)
    points = [hourly.get(first + timedelta(hours=i)) for i in range(24)]
    valid = sum(p is not None for p in points)
    complete = valid == 24
    return {
        "observed_at": most_recent.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "rain_last_hour_mm": hourly[most_recent],
        "rain_last_24_readings_mm": round(sum(points), 2) if complete else None,
        "hourly_coverage_24": valid,
        "hourly_expected_24": 24,
        "rain_24h_complete": complete,
        "quality": "raw_station_data_not_homogenized_or_validated",
    }


def fetch_station_rows(code: str, token: str, now: datetime, *, timeout: int = 14) -> list[Any]:
    """Server-side only.  Path-token API: do not log the request URL or response errors."""
    if not CODE.fullmatch(code) or not token or len(token) > 2048 or any(c.isspace() for c in token):
        raise RainSourceError("Invalid station code or provider authentication")
    end = now.astimezone(timezone.utc).date()
    start = end - timedelta(days=2)
    url = f"{API_ROOT}/{start.isoformat()}/{end.isoformat()}/{code}/{quote(token, safe='')}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "criseclimatica/0.4"})
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status == 204:
                raise RainSourceError("INMET supplied no observation payload", "no_recent_data")
            if response.status != 200:
                raise RainSourceError("INMET observation endpoint did not return HTTP 200", "endpoint_unavailable")
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise RainSourceError("INMET observation response exceeded safe limit")
        data = json.loads(body.decode("utf-8"))
        if not isinstance(data, list):
            raise RainSourceError("Invalid INMET observation response structure")
        return data
    except HTTPError as exc:
        # HTTPS HTTPError carries the full token-bearing URL. Never stringify it.
        reason = ("access_restricted" if exc.code in (401, 403) else
                  "no_recent_data" if exc.code == 204 else
                  "rate_limited" if exc.code == 429 else
                  "endpoint_unavailable" if exc.code in (404, 405, 410) else "unavailable")
        raise RainSourceError("INMET observation endpoint refused request", reason) from None
    except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RainSourceError(f"INMET observation fetch failed ({type(exc).__name__})") from None


def unavailable(locations: list[dict[str, Any]], stamp: str, status: str) -> dict[str, Any]:
    return {
        "schema_version": 1, "kind": KIND, "status": status,
        "checked_at": stamp, "source": {"id": "inmet", "url": SOURCE},
        "stations": [], "locations": [{"location_id": loc["id"], "stations": []} for loc in locations],
        "diagnostic": "token_not_configured" if status == "not_configured" else status,
        "failure_reasons": {},
    }


def collect_rain(locations: list[dict[str, Any]], catalog: dict[str, Any], stamp: str,
                 *, token: str | None = None, now: datetime | None = None,
                 fetcher=fetch_station_rows) -> dict[str, Any]:
    """Bounded optional collection; failure of one station never fabricates zero rainfall."""
    token = token if token is not None else os.environ.get("INMET_API_TOKEN", "")
    if not token:
        return unavailable(locations, stamp, "not_configured")
    selected = candidates(catalog, locations)
    if not selected:
        return unavailable(locations, stamp, "no_nearby_catalog_stations")
    now = now or datetime.now(timezone.utc)
    usable = []
    failures = 0
    reasons: dict[str, int] = {}
    for station in selected:
        try:
            rows = fetcher(station["code"], token, now)
            parsed = normalize_station_rows(rows, station["code"], now)
            if parsed is not None:
                usable.append({**station, **parsed})
            else:
                failures += 1
                reasons["no_recent_data"] = reasons.get("no_recent_data", 0) + 1
        except (RainSourceError, ValueError, TypeError) as exc:
            failures += 1
            reason = exc.reason if isinstance(exc, RainSourceError) else "invalid_data"
            if reason not in {"access_restricted", "rate_limited", "endpoint_unavailable", "no_recent_data", "invalid_data", "unavailable"}:
                reason = "unavailable"
            reasons[reason] = reasons.get(reason, 0) + 1
    region = []
    for place in locations:
        near = sorted(({"code": st["code"], "distance_km": round(haversine_km(place["latitude"], place["longitude"], st["latitude"], st["longitude"]), 1)}
                       for st in usable if haversine_km(place["latitude"], place["longitude"], st["latitude"], st["longitude"]) <= MAX_DISTANCE_KM),
                      key=lambda x: (x["distance_km"], x["code"]))
        region.append({"location_id": place["id"], "stations": near})
    if usable:
        status = "available"
    elif reasons.get("access_restricted") == len(selected):
        status = "access_restricted"
    elif reasons.get("no_recent_data") == len(selected):
        status = "no_recent_data"
    else:
        status = "unavailable"
    return {
        "schema_version": 1, "kind": KIND,
        "status": status,
        "checked_at": stamp,
        "source": {"id": "inmet", "url": SOURCE},
        "selection": "up to 5 nearest stations within 90 km, geographical distance not municipal representativeness",
        "stations_checked": len(selected), "stations_unavailable": failures,
        "diagnostic": "partial" if usable and failures else (status if not usable else "ok"),
        "failure_reasons": reasons,
        "stations": usable, "locations": region,
    }
