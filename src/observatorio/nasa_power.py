"""NASA POWER daily gridded estimates for a single regional reference point.

This is a *separate model/reanalysis product*, NEVER a pluviometer reading.
We deliberately fetch a single point once per day: requesting seven nearby
coordinates can duplicate the same NASA grid cell and waste provider resources.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
DOCS = "https://power.larc.nasa.gov/docs/services/api/temporal/daily/"
KIND = "nasa_power_daily_gridded_estimate_not_station_observation"
CACHE_HOURS = 24
STALE_HOURS = 72


class NasaSourceError(RuntimeError):
    """NASA POWER could not be retrieved or safely understood."""


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Invalid NASA timestamp")
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("NASA timestamp requires timezone")
    return moment.astimezone(timezone.utc)


def _value(value: Any, *, minimum: float, maximum: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        return None
    if value == -999 or not minimum <= value <= maximum:
        return None
    return round(float(value), 2)


def normalize(raw: Any, point: dict[str, Any], collected_at: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Normalize only actual days present in NASA's daily POWER result."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not isinstance(raw, dict):
        raise NasaSourceError("Invalid NASA JSON root")
    parameters = raw.get("properties", {}).get("parameter") if isinstance(raw.get("properties"), dict) else None
    if not isinstance(parameters, dict):
        raise NasaSourceError("NASA POWER is missing parameter data")
    precipitation = parameters.get("PRECTOTCORR")
    temperature = parameters.get("T2M")
    if not isinstance(precipitation, dict) or not isinstance(temperature, dict):
        raise NasaSourceError("NASA POWER parameter data missing")
    if len(precipitation) > 70 or len(temperature) > 70:
        raise NasaSourceError("NASA POWER result exceeds bounded daily range")
    rows: list[dict[str, Any]] = []
    for day in sorted(precipitation):
        try:
            parsed = datetime.strptime(day, "%Y%m%d").date()
        except (TypeError, ValueError) as exc:
            raise NasaSourceError("Invalid NASA daily date") from exc
        if parsed > now.date() or parsed < now.date() - timedelta(days=31):
            continue
        rain = _value(precipitation[day], minimum=0, maximum=2000)
        temp = _value(temperature.get(day), minimum=-80, maximum=65)
        if rain is None and temp is None:
            continue
        rows.append({"date_utc": parsed.isoformat(), "rain_estimated_mm_day": rain,
                     "temperature_estimated_c": temp})
    if not rows:
        raise NasaSourceError("NASA POWER has no valid recent daily estimates")
    return {
        "schema_version": 1, "kind": KIND, "status": "available",
        "checked_at": collected_at, "retrieved_at": collected_at,
        "source": {"id": "nasa-power", "name": "NASA POWER", "url": DOCS},
        "point": {"location_id": point["id"], "name": point["name"],
                  "latitude": point["latitude"], "longitude": point["longitude"]},
        "reference": "UTC calendar days; approximate grid estimates, not gauge measurements",
        "latest_data_day_utc": rows[-1]["date_utc"],
        "days_since_latest": (now.date() - date.fromisoformat(rows[-1]["date_utc"])).days,
        "daily": rows[-14:],
    }


def fetch(point: dict[str, Any], now: datetime, *, timeout: int = 25) -> dict[str, Any]:
    end = now.astimezone(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=20)
    params = {
        "parameters": "PRECTOTCORR,T2M", "community": "AG",
        "latitude": f"{point['latitude']:.4f}", "longitude": f"{point['longitude']:.4f}",
        "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
        "format": "JSON", "time-standard": "UTC",
    }
    request = Request(URL + "?" + urlencode(params), headers={
        "Accept": "application/json", "User-Agent": "ObservatorioClimatico/0.5 (https://github.com/guimig/criseclimatica)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise NasaSourceError("NASA POWER returned a non-success response")
            body = response.read(900_001)
            if len(body) > 900_000:
                raise NasaSourceError("NASA POWER response exceeds safety limit")
        result = json.loads(body.decode("utf-8"))
        if not isinstance(result, dict):
            raise NasaSourceError("NASA POWER result is not a JSON object")
        return result
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise NasaSourceError(f"NASA POWER request failed: {type(exc).__name__}") from None


def unavailable(point: dict[str, Any], stamp: str, status: str = "unavailable") -> dict[str, Any]:
    return {"schema_version": 1, "kind": KIND, "status": status,
            "checked_at": stamp, "retrieved_at": None,
            "source": {"id": "nasa-power", "name": "NASA POWER", "url": DOCS},
            "point": {"location_id": point["id"], "name": point["name"],
                      "latitude": point["latitude"], "longitude": point["longitude"]},
            "reference": "UTC gridded estimates, not station observations", "latest_data_day_utc": None,
            "days_since_latest": None, "daily": []}


def collect(point: dict[str, Any], stamp: str, previous: dict[str, Any] | None = None,
            *, now: datetime | None = None, fetcher: Callable = fetch) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    reusable = False
    age = timedelta(days=999)
    if isinstance(previous, dict) and previous.get("schema_version") == 1 and previous.get("kind") == KIND:
        old_point = previous.get("point") if isinstance(previous.get("point"), dict) else {}
        if (old_point.get("location_id") == point["id"] and
                old_point.get("latitude") == point["latitude"] and
                old_point.get("longitude") == point["longitude"] and
                previous.get("status") in ("available", "cached", "stale") and
                isinstance(previous.get("daily"), list) and previous["daily"]):
            try:
                age = now - _utc(previous.get("retrieved_at"))
                reusable = timedelta(0) <= age <= timedelta(hours=STALE_HOURS)
            except ValueError:
                pass
    if reusable and age < timedelta(hours=CACHE_HOURS):
        return {**previous, "status": "cached", "checked_at": stamp}
    try:
        return normalize(fetcher(point, now), point, stamp, now=now)
    except (NasaSourceError, ValueError, TypeError, KeyError, OSError) as exc:
        if reusable:
            return {**previous, "status": "stale", "checked_at": stamp}
        return unavailable(point, stamp)
