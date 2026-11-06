"""Public Epagri/SC ArcGIS station registry: locations, NOT live telemetry.

Layer 1 is described as 'Estacoes ativas atuais', but the service metadata
is not a guarantee of present-day transmission or station operation.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .inmet import haversine_km

LAYER = "https://gis.epagri.sc.gov.br/arcgis/rest/services/Zoneamento/Potencial_estacoes/MapServer/1"
QUERY = LAYER + "/query"
KIND = "epagri_arcgis_station_registry_not_live_measurements"
FIELDS = "CD_ESTAC,NM_ESTAC,NM_MUNIC,SG_UF,DS_CLASS,DS_STATU_ESTAC,VL_LATIT_ESTAC,VL_LONGI_ESTAC,NM_RESPO"
MAX_BYTES = 1_500_000
MAX_FEATURES = 2000
MAX_DISTANCE_KM = 110


class EpagriGeoError(RuntimeError):
    """Unable to validate an official public ArcGIS station response."""


def _datetime(value: Any) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise EpagriGeoError("Invalid registry time") from exc
    if dt.tzinfo is None:
        raise EpagriGeoError("Registry time lacks timezone")
    return dt.astimezone(timezone.utc)


def _float_coordinate(value: Any, limit: float) -> float | None:
    try:
        n = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return n if math.isfinite(n) and -limit <= n <= limit else None


def request_url() -> str:
    """Ask ArcGIS for a bounded SC coast area in WGS84 (input SR=4326)."""
    params = {
        "where": "1=1", "geometry": "-49.25,-27.15,-48.10,-25.70",
        "geometryType": "esriGeometryEnvelope", "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects", "outFields": FIELDS,
        # Service advertises Supports Pagination: false. Do not send
        # resultRecordCount/resultOffset; enforce a bounded spatial envelope.
        "returnGeometry": "false", "f": "json",
    }
    return QUERY + "?" + urlencode(params)


def fetch_registry(*, timeout: int = 12) -> Any:
    req = Request(request_url(), headers={"Accept": "application/json", "User-Agent": "criseclimatica-regional-stations/0.8"})
    try:
        with urlopen(req, timeout=timeout) as response:
            parsed = urlparse(response.geturl())
            if response.status != 200 or parsed.scheme != "https" or parsed.hostname != "gis.epagri.sc.gov.br":
                raise EpagriGeoError("ArcGIS response from unexpected origin")
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise EpagriGeoError("ArcGIS response too large")
        return json.loads(raw.decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as exc:
        raise EpagriGeoError(f"ArcGIS public registry unavailable: {type(exc).__name__}") from exc


def normalize_registry(payload: Any, locations: list[dict], stamp: str) -> dict:
    if not isinstance(payload, dict) or "error" in payload or payload.get("exceededTransferLimit"):
        raise EpagriGeoError("Invalid or truncated ArcGIS registry")
    features = payload.get("features")
    if not isinstance(features, list) or len(features) > MAX_FEATURES:
        raise EpagriGeoError("Unexpected number of ArcGIS features")
    stations: dict[str, dict] = {}
    for feature in features:
        if not isinstance(feature, dict) or not isinstance(feature.get("attributes"), dict):
            continue
        attrs = feature["attributes"]
        code = attrs.get("CD_ESTAC")
        lat = _float_coordinate(attrs.get("VL_LATIT_ESTAC"), 90)
        lon = _float_coordinate(attrs.get("VL_LONGI_ESTAC"), 180)
        name = attrs.get("NM_ESTAC")
        if isinstance(code, bool) or not isinstance(code, (int, str)) or lat is None or lon is None:
            continue
        if not isinstance(name, str) or not name.strip() or len(name) > 160:
            continue
        key = str(code).strip()
        if not key.isdigit() or len(key) > 15:
            continue
        state = attrs.get("SG_UF")
        if state is not None and state != "SC":
            continue
        def clean(field: str, max_len: int) -> str | None:
            value = attrs.get(field)
            return value.strip()[:max_len] if isinstance(value, str) and value.strip() else None
        stations[key] = {
            "code": key, "name": name.strip(), "state": state,
            "municipality": clean("NM_MUNIC", 100), "category": clean("DS_CLASS", 70),
            "catalog_status": clean("DS_STATU_ESTAC", 50), "responsible": clean("NM_RESPO", 100),
            "latitude": lat, "longitude": lon,
        }
    nearby = []
    for place in locations:
        candidates = []
        for station in stations.values():
            dist = haversine_km(place["latitude"], place["longitude"], station["latitude"], station["longitude"])
            if dist <= MAX_DISTANCE_KM:
                candidates.append({**station, "distance_km": round(dist, 1)})
        candidates.sort(key=lambda row: (row["distance_km"], row["code"]))
        nearby.append({"location_id": place["id"], "stations": candidates[:6]})
    return {
        "schema_version": 1, "kind": KIND, "status": "available", "retrieved_at": stamp,
        "checked_at": stamp, "source": {"id": "epagri-gis", "name": "Epagri SC GIS",
                                   "url": LAYER},
        "note": "Catalogo georreferenciado, sem prova de operacao atual ou leitura recente. Camada GIS nao e telemetria.",
        "locations": nearby, "total_features_returned": len(features),
        "valid_georeferenced_stations": len(stations),
    }


def unavailable(stamp: str) -> dict:
    return {
        "schema_version": 1, "kind": KIND, "status": "unavailable", "retrieved_at": None,
        "checked_at": stamp, "source": {"id": "epagri-gis", "name": "Epagri SC GIS", "url": LAYER},
        "note": "Cadastro indisponivel; nao implica ausencia de estacoes na regiao.", "locations": [],
    }


def collect(locations: list[dict], stamp: str, *, previous: dict | None = None,
            fixture: Any = None) -> dict:
    now = _datetime(stamp)
    previous_ok = (isinstance(previous, dict) and previous.get("schema_version") == 1 and
                   previous.get("kind") == KIND and isinstance(previous.get("locations"), list) and
                   {rec.get("location_id") for rec in previous["locations"] if isinstance(rec, dict)} ==
                   {loc["id"] for loc in locations} and previous.get("retrieved_at"))
    age = None
    if previous_ok:
        try:
            age = now - _datetime(previous["retrieved_at"])
        except EpagriGeoError:
            previous_ok = False
    if fixture is None and previous_ok and timedelta(0) <= age < timedelta(hours=24):
        return {**previous, "checked_at": stamp, "status": "cached"}
    try:
        result = normalize_registry(fetch_registry() if fixture is None else fixture, locations, stamp)
        return result
    except (EpagriGeoError, ValueError) as exc:
        print(f"Epagri GIS registry: {type(exc).__name__}")
        if previous_ok and timedelta(0) <= age <= timedelta(days=7):
            return {**previous, "checked_at": stamp, "status": "stale"}
        return unavailable(stamp)
