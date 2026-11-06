"""INMET station CATALOG (not observations). Do not infer fresh sensor readings."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CATALOG_URL = "https://apitempo.inmet.gov.br/estacoes/T"
CATALOG_WEB = "https://tempo.inmet.gov.br/TabelaEstacoes/"


class CatalogError(RuntimeError):
    """Invalid or unavailable public station catalog."""


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(a)))


def _coordinate(value: Any, limit: int) -> float | None:
    try:
        coordinate = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return coordinate if math.isfinite(coordinate) and -limit <= coordinate <= limit else None


def normalize_catalog(raw: Any) -> list[dict[str, Any]]:
    """Normalize provider metadata, preserving INMET's catalog status verbatim."""
    if not isinstance(raw, list) or not raw or len(raw) > 10000:
        raise CatalogError("Invalid INMET catalog payload")
    unique: dict[str, dict[str, Any]] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        code, name = row.get("CD_ESTACAO"), row.get("DC_NOME")
        lat = _coordinate(row.get("VL_LATITUDE"), 90)
        lon = _coordinate(row.get("VL_LONGITUDE"), 180)
        if not isinstance(code, str) or not code.isalnum() or len(code) > 12:
            continue
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            continue
        if lat is None or lon is None or code in unique:
            continue
        state = row.get("SG_ESTADO")
        status = row.get("CD_SITUACAO")
        unique[code] = {
            "code": code,
            "name": name.strip(),
            "state": state if isinstance(state, str) and len(state) == 2 else None,
            "latitude": lat,
            "longitude": lon,
            "catalog_status": status[:70] if isinstance(status, str) else "Nao informado",
            "catalog_provider": "INMET",
        }
    if not unique:
        raise CatalogError("INMET catalog contains no valid coordinates")
    return list(unique.values())


def nearby_catalog(
    locations: list[dict[str, Any]], stations: list[dict[str, Any]],
    collected_at: str, *, per_place: int = 6, max_distance_km: float = 170.0,
) -> dict[str, Any]:
    """Select real station records near each MODEL location, without implying coverage."""
    results = []
    for location in locations:
        candidates = []
        for station in stations:
            distance = haversine_km(location["latitude"], location["longitude"], station["latitude"], station["longitude"])
            if distance <= max_distance_km:
                candidates.append({**station, "distance_km": round(distance, 1)})
        candidates.sort(key=lambda station: (station["distance_km"], station["code"]))
        results.append({"location_id": location["id"], "stations": candidates[:per_place]})
    return {
        "schema_version": 1,
        "kind": "station_catalog_metadata_not_measurements",
        "source": {"id": "inmet", "name": "INMET", "url": CATALOG_URL},
        "retrieved_at": collected_at,
        "coverage_note": "Distancia geografica nao garante representatividade ou atualizacao de sensores.",
        "locations": results,
    }


def fetch_catalog(*, timeout: int = 15) -> list[dict[str, Any]]:
    request = Request(CATALOG_URL, headers={"Accept": "application/json", "User-Agent": "criseclimatica-observatorio/0.2 (open research)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise CatalogError(f"Unexpected INMET status {response.status}")
            raw = response.read(5_000_001)
            if len(raw) > 5_000_000:
                raise CatalogError("INMET station catalog exceeded 5 MB")
        return normalize_catalog(json.loads(raw.decode("utf-8")))
    except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CatalogError(f"INMET station catalog unavailable: {type(exc).__name__}") from exc


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
