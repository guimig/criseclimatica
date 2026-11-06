"""Airport METAR observations near the north coast, separate from model estimates.

The AWC service does not provide a rain-gauge accumulation; a report is valid
for the aerodrome, NOT every municipality in its vicinity.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .inmet import haversine_km

API_URL = "https://aviationweather.gov/api/data/metar"
DOCS_URL = "https://aviationweather.gov/data/api/"
STATIONS = frozenset({"SBJV", "SBNF"})  # Joinville and Navegantes; no implied municipal coverage.
KIND = "aerodrome_metar_observations_not_municipal_measurements"


class MetarSourceError(RuntimeError):
    """Aviation Weather Center data could not be validated."""


def _number(value: Any, lo: float, hi: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    return round(float(value), 1) if math.isfinite(value) and lo <= value <= hi else None


def _moment(raw: Any) -> datetime | None:
    try:
        if isinstance(raw, (float, int)) and not isinstance(raw, bool):
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        if isinstance(raw, str):
            date = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return date.astimezone(timezone.utc) if date.tzinfo else None
    except (ValueError, OverflowError, OSError):
        pass
    return None


def normalize_metars(raw: Any, locations: list[dict[str, Any]], collected_at: str, *, now: datetime | None = None) -> dict[str, Any]:
    if not isinstance(raw, list) or len(raw) > 400:
        raise MetarSourceError("Invalid METAR response list")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must have a timezone")
    now = now.astimezone(timezone.utc)
    stations: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("icaoId"), str) or item["icaoId"] not in STATIONS:
            continue
        observed = _moment(item.get("obsTime")) or _moment(item.get("reportTime"))
        if observed is None or not -timedelta(minutes=10) <= now - observed <= timedelta(hours=6):
            continue
        lat = _number(item.get("lat"), -90, 90)
        lon = _number(item.get("lon"), -180, 180)
        if lat is None or lon is None:
            continue
        code = item["icaoId"]
        speed = _number(item.get("wspd"), 0, 200)
        gust = _number(item.get("wgst"), 0, 220)
        record = {
            "icao": code, "name": (str(item.get("name") or code).strip())[:110],
            "latitude": lat, "longitude": lon,
            "observed_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "temperature_c": _number(item.get("temp"), -80, 65),
            "dewpoint_c": _number(item.get("dewp"), -90, 65),
            "wind_kmh": round(speed * 1.852, 1) if speed is not None else None,
            "gust_kmh": round(gust * 1.852, 1) if gust is not None else None,
            "wind_direction_deg": _number(item.get("wdir"), 0, 360),
            "pressure_hpa": _number(item.get("slp"), 800, 1100),
            "metar_type": (str(item.get("metarType") or "METAR"))[:20],
        }
        prior = stations.get(code)
        if prior is None or record["observed_at"] > prior["observed_at"]:
            stations[code] = record

    by_location: list[dict[str, Any]] = []
    for place in locations:
        nearest = sorted(
            ((haversine_km(place["latitude"], place["longitude"], r["latitude"], r["longitude"]), r) for r in stations.values()),
            key=lambda pair: pair[0],
        )
        if nearest and nearest[0][0] <= 100:
            distance, record = nearest[0]
            by_location.append({"location_id": place["id"], "status": "available", "distance_km": round(distance, 1), "observation": record})
        else:
            by_location.append({"location_id": place["id"], "status": "no_recent_report", "distance_km": None, "observation": None})
    return {
        "schema_version": 1, "kind": KIND,
        "status": "available" if stations else "no_recent_reports",
        "retrieved_at": collected_at,
        "source": {"id": "aviation-weather-center", "name": "Aviation Weather Center (NOAA)", "url": DOCS_URL},
        "limitations": "Medição em aeródromo; não equivale a observação municipal. METAR não fornece chuva acumulada em mm.",
        "stations": sorted(stations.values(), key=lambda x: x["icao"]),
        "locations": by_location,
    }


def unavailable_metars(locations: list[dict[str, Any]], checked_at: str) -> dict[str, Any]:
    return {
        "schema_version": 1, "kind": KIND, "status": "unavailable", "retrieved_at": None, "checked_at": checked_at,
        "source": {"id": "aviation-weather-center", "name": "Aviation Weather Center (NOAA)", "url": DOCS_URL},
        "limitations": "Medições indisponíveis; não inferir valores do modelo.",
        "stations": [],
        "locations": [{"location_id": loc["id"], "status": "unavailable", "distance_km": None, "observation": None} for loc in locations],
    }


def fetch_metars(*, timeout: int = 20) -> list[dict[str, Any]]:
    url = API_URL + "?" + urlencode({"ids": ",".join(sorted(STATIONS)), "format": "json", "hours": 6})
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "ObservatorioTempoClima/0.3 (+https://github.com/guimig/criseclimatica)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status == 204:
                return []
            if response.status != 200:
                raise MetarSourceError(f"METAR HTTP {response.status}")
            content = response.read(1_000_001)
            if len(content) > 1_000_000:
                raise MetarSourceError("METAR response too large")
        data = json.loads(content.decode("utf-8"))
        if not isinstance(data, list):
            raise MetarSourceError("METAR response should be a JSON list")
        return data
    except (HTTPError, URLError, OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MetarSourceError(f"METAR request failed: {type(exc).__name__}") from exc
