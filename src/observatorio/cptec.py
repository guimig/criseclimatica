"""CPTEC/INPE public XML 7-day forecast. Independent of Open-Meteo.

CPTEC's documented geographic endpoint returns a forecast for the nearest
locality to the given coordinates; no claims of station observations or
municipality-wide measurements should be made from this response.
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

BASE = "https://servicos.cptec.inpe.br/XML/cidade/7dias/"
DOCS = "https://servicos.cptec.inpe.br/XML/"
KIND = "cptec_inpe_daily_forecast_nearest_locality_not_station_measurements"
MAX_BYTES = 180_000


class CptecError(RuntimeError):
    """Unusable official forecast, with no fabricated replacement."""


def _float(raw: str | None, low: float, high: float) -> float | None:
    try:
        num = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
    return round(num, 1) if num is not None and math.isfinite(num) and low <= num <= high else None


def parse_forecast(raw: bytes, location: dict[str, Any], now: datetime) -> dict[str, Any]:
    if not raw or len(raw) > MAX_BYTES or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise CptecError("Invalid CPTEC XML size or document type")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise CptecError("CPTEC returned malformed XML") from exc
    if root.tag != "cidade":
        raise CptecError("CPTEC response is not a forecast")
    state = (root.findtext("uf") or "").strip().upper()
    if state and state != location["state"].upper():
        raise CptecError("Nearest CPTEC forecast belongs to another state")
    updated = (root.findtext("atualizacao") or "").strip()
    try:
        updated_day = date.fromisoformat(updated)
    except ValueError as exc:
        raise CptecError("CPTEC update date missing or invalid") from exc
    now = now.astimezone(timezone.utc)
    if updated_day > now.date() + timedelta(days=1) or updated_day < now.date() - timedelta(days=14):
        raise CptecError("CPTEC publication is implausibly dated")
    forecasts = []
    seen = set()
    for element in root.findall("previsao"):
        value = (element.findtext("dia") or "").strip()
        try:
            day = date.fromisoformat(value)
        except ValueError:
            continue
        if day in seen or day < now.date() - timedelta(days=1) or day > now.date() + timedelta(days=15):
            continue
        low, high = _float(element.findtext("minima"), -60, 65), _float(element.findtext("maxima"), -60, 65)
        if low is None or high is None or high < low:
            continue
        code = (element.findtext("tempo") or "").strip()
        forecasts.append({
            "day": day.isoformat(), "minimum_c": low, "maximum_c": high,
            "condition_code": code[:12], "uv_index_max": _float(element.findtext("iuv"), 0, 20),
        })
        seen.add(day)
    forecasts.sort(key=lambda item: item["day"])
    if not forecasts:
        raise CptecError("CPTEC has no usable forecast days")
    return {
        "location_id": location["id"],
        "status": "stale" if updated_day < now.date() - timedelta(days=2) else "available",
        "nearest_cptec_locality": (root.findtext("nome") or "").strip()[:90] or None,
        "updated_day": updated, "days": forecasts[:8],
    }


def fetch_forecast(location: dict[str, Any], *, timeout: int = 10, now: datetime | None = None) -> dict[str, Any]:
    lat, lon = location["latitude"], location["longitude"]
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise CptecError("Invalid coordinates")
    url = f"{BASE}{lat:.4f}/{lon:.4f}/previsaoLatLon.xml"
    request = Request(url, headers={"Accept": "application/xml,text/xml", "User-Agent": "criseclimatica-observatorio/0.3 (research)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            final = urlparse(response.geturl())
            if final.scheme != "https" or final.hostname != "servicos.cptec.inpe.br":
                raise CptecError("CPTEC forecast redirected outside trusted HTTPS host")
            if response.status != 200:
                raise CptecError(f"CPTEC HTTP {response.status}")
            raw = response.read(MAX_BYTES + 1)
    except (OSError, URLError, HTTPError, TimeoutError) as exc:
        raise CptecError(f"CPTEC service unavailable: {type(exc).__name__}") from exc
    return parse_forecast(raw, location, now or datetime.now(timezone.utc))


def collect(locations: list[dict[str, Any]], checked_at: str, fixture: bytes | None = None) -> dict[str, Any]:
    """Isolate per-location outages; never confuse XML forecasts with observations."""
    now = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    def safe(loc):
        try:
            return parse_forecast(fixture, loc, now) if fixture is not None else fetch_forecast(loc, now=now)
        except (CptecError, OSError, ValueError):
            return {"location_id": loc["id"], "status": "unavailable", "days": []}

    with ThreadPoolExecutor(max_workers=min(len(locations), 4)) as executor:
        rows = list(executor.map(safe, locations))
    available = sum(r["status"] == "available" for r in rows)
    return {
        "schema_version": 1, "kind": KIND, "source": {"id": "cptec-inpe", "name": "CPTEC/INPE", "url": DOCS},
        "checked_at": checked_at,
        "status": "available" if available == len(locations) else "partial" if available else "unavailable",
        "locations": rows,
        "note": "Independent CPTEC forecast for nearest geographic locality; not an observation.",
    }
