"""Cemaden PED recent instrumental readings, separate from rainfall accumulations.

One bounded SC-wide recent-data query replaces ten sensor-by-city calls. The
source's own station coordinates determine regional proximity; the values are
not forecast data nor an estimate of weather in a whole municipality.
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .cemaden_auth import SgaaAuthError, SgaaSession
from .inmet import haversine_km

ROOT = "https://sws.cemaden.gov.br/PED/rest"
RECENT_API = ROOT + "/pcds/pcds-dados-recentes"
TYPES_API = ROOT + "/pcds-tipo-estacao/sensores"
SOURCE = "https://sws.cemaden.gov.br/PED/api/ui/"
KIND = "cemaden_recent_instrumental_sensor_readings_not_model_forecast"
STATION_CODE = re.compile(r"[A-Za-z0-9-]{4,25}")
MAX_BODY_BYTES = 12_000_000
MAX_STATE_RECORDS = 30_000
MAX_RECORDS = 2 * MAX_STATE_RECORDS
MAX_NEARBY_KM = 130.0
MAX_STATIONS_PER_PLACE = 24
MAX_READINGS_PER_STATION = 12
MAX_AGE = timedelta(hours=3, minutes=20)
# PED Swagger identifies 10 as Chuva (pluviometric); Cemaden station graphs
# express precipitation in mm. References and unresolved sensor units are in
# docs/CEMADEN_SENSORES_E_EXPANSAO_REGIONAL.md. No conversion or time-window sum.
DOCUMENTED_UNITS = {10: "mm", 30: "m³/s", 60: "°C"}


class SensorSourceError(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(f"Cemaden PED sensors: {reason}")
        self.reason = reason


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request_json(path: str, token: str, params: dict[str, str], *, max_bytes: int,
                  timeout: int = 18) -> Any:
    if not isinstance(token, str) or not 1 <= len(token) <= 4096 or any(c.isspace() for c in token):
        raise SensorSourceError("access_restricted")
    if path not in (RECENT_API, TYPES_API):
        raise SensorSourceError("invalid_request")
    url = path + ("?" + urlencode(params) if params else "")
    request = Request(url, headers={"Accept": "application/json", "token": token,
                                    "User-Agent": "criseclimatica/1.1 (+https://github.com/guimig/criseclimatica)"})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            if response.status != 200:
                raise SensorSourceError("service_unavailable")
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise SensorSourceError("response_too_large")
        return json.loads(body.decode("utf-8"))
    except HTTPError as exc:
        reason = ("token_expired" if exc.code == 401 else
                  "bad_request" if exc.code == 400 else
                  "access_restricted" if exc.code == 403 else
                  "rate_limited" if exc.code == 429 else "service_unavailable")
        raise SensorSourceError(reason) from None
    except (URLError, TimeoutError, OSError, UnicodeError, ValueError) as exc:
        raise SensorSourceError("service_unavailable") from None


def fetch_recent(token: str, *, uf: str = "SC") -> Any:
    if uf not in ("SC", "PR"):
        raise SensorSourceError("invalid_state")
    return _request_json(RECENT_API, token, {"rede": "11", "uf": uf, "formato": "JSON"},
                         max_bytes=MAX_BODY_BYTES)


def fetch_sensor_types(token: str) -> Any:
    return _request_json(TYPES_API, token, {}, max_bytes=600_000)


def normalize_types(payload: Any) -> dict[int, str]:
    """Read sensor descriptions from the official station-type catalog."""
    if not isinstance(payload, list) or len(payload) > 100:
        raise SensorSourceError("invalid_sensor_catalog")
    mapping: dict[int, str] = {}
    for station_type in payload:
        if not isinstance(station_type, dict) or not isinstance(station_type.get("sensor"), list):
            continue
        for entry in station_type["sensor"][:100]:
            if not isinstance(entry, dict):
                continue
            sensor_id, label = entry.get("sensor"), entry.get("sensordescricao")
            if (isinstance(sensor_id, int) and not isinstance(sensor_id, bool) and 0 < sensor_id < 10000
                    and isinstance(label, str) and 1 <= len(label.strip()) <= 100):
                mapping.setdefault(sensor_id, label.strip())
    return mapping


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _coordinate(value: Any, max_abs: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        val = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return val if math.isfinite(val) and abs(val) <= max_abs else None


def _reading(value: Any, sensor_id: int) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        val = float(value.replace(",", ".") if isinstance(value, str) else value)
    except (ValueError, TypeError, OverflowError):
        return None
    if not math.isfinite(val) or val in (-999, -9999, 9999, 99999) or abs(val) > 100_000:
        return None
    if sensor_id in (10, 30, 240) and val < 0:
        return None
    if sensor_id == 60 and not -70 <= val <= 70:
        return None
    return round(val, 3)


def normalize_recent(payload: Any, sensor_labels: dict[int, str], locations: list[dict],
                     stamp: str, *, now: datetime | None = None) -> dict:
    """Keep only valid source observations close to a configured locality."""
    if not isinstance(payload, list) or len(payload) > MAX_RECORDS:
        raise SensorSourceError("invalid_recent_response")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    allowed_states = {loc.get("state", "SC") for loc in locations} & {"SC", "PR"}
    by_station: dict[str, dict] = {}
    by_sensor: dict[tuple[str, int], dict] = {}
    ambiguous: set[tuple[str, int]] = set()
    for item in payload:
        if not isinstance(item, dict) or str(item.get("uf", "")).upper() not in allowed_states:
            continue
        code = item.get("codestacao")
        if not isinstance(code, str) or not STATION_CODE.fullmatch(code):
            continue
        lat = _coordinate(item.get("latitude"), 90)
        lon = _coordinate(item.get("longitude"), 180)
        if lat is None or lon is None or not locations:
            continue
        if all(haversine_km(lat, lon, loc["latitude"], loc["longitude"]) > MAX_NEARBY_KM for loc in locations):
            continue
        observed_at = _time(item.get("datahora"))
        if observed_at is None or not -timedelta(minutes=10) <= now - observed_at <= MAX_AGE:
            continue
        sensor_id = item.get("id_sensor")
        if not isinstance(sensor_id, int) or isinstance(sensor_id, bool) or not 0 < sensor_id < 10000:
            continue
        measurement = _reading(item.get("valor"), sensor_id)
        if measurement is None:
            continue
        station = by_station.setdefault(code, {
            "code": code, "name": str(item.get("nome") or code)[:100],
            "municipality": str(item.get("cidade") or "Não informado")[:100],
            "state": str(item.get("uf", "")).upper(),
            "latitude": lat, "longitude": lon, "readings": []})
        # Conflicting coordinate metadata for one code is not merged into an
        # apparently precise station position.
        if abs(station["latitude"] - lat) > 0.02 or abs(station["longitude"] - lon) > 0.02:
            continue
        key = (code, sensor_id)
        reading = {
            "sensor_id": sensor_id,
            "sensor_name": sensor_labels.get(sensor_id, f"Sensor {sensor_id} (descrição indisponível)")[:100],
            "unit": DOCUMENTED_UNITS.get(sensor_id),
            "value": measurement,
            "observed_at": observed_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "quality_code_as_reported": str(item.get("qualificacao") or "")[:16],
        }
        old = by_sensor.get(key)
        if old is None or reading["observed_at"] > old["observed_at"]:
            by_sensor[key] = reading
            ambiguous.discard(key)
        elif reading["observed_at"] == old["observed_at"] and reading["value"] != old["value"]:
            ambiguous.add(key)
    for key, reading in by_sensor.items():
        if key not in ambiguous:
            by_station[key[0]]["readings"].append(reading)
    stations = [station for station in by_station.values() if station["readings"]]
    for station in stations:
        station["readings"].sort(key=lambda row: (row["sensor_id"]))
        station["readings"] = station["readings"][:MAX_READINGS_PER_STATION]
        station["latest_observed_at"] = max(r["observed_at"] for r in station["readings"])
    stations.sort(key=lambda station: station["code"])
    regional = []
    for place in locations:
        matches = sorted(({
            "code": row["code"],
            "distance_km": round(haversine_km(place["latitude"], place["longitude"],
                                                 row["latitude"], row["longitude"]), 1),
        } for row in stations if haversine_km(place["latitude"], place["longitude"],
                                             row["latitude"], row["longitude"]) <= MAX_NEARBY_KM),
            key=lambda x: (x["distance_km"], x["code"]))
        regional.append({"location_id": place["id"], "eligible_station_count": len(matches), "stations": matches[:MAX_STATIONS_PER_PLACE]})
    return {
        "schema_version": 1, "kind": KIND,
        "status": "available" if stations else "no_recent_data",
        "checked_at": stamp,
        "source": {"id": "cemaden", "name": "Cemaden PED — sensores recentes",
                   "url": SOURCE, "attribution": "DADOS DA REDE OBSERVACIONAL DO CEMADEN/MCTIC"},
        "station_data_kind": "raw_station_sensor_values_last_three_hours_not_local_forecast",
        "geography": "SC/PR; leitura de uma estação próxima não representa o município inteiro",
        "catalog_status": "available" if sensor_labels else "unavailable",
        "selection": {"radius_km": MAX_NEARBY_KM, "max_stations_per_location": MAX_STATIONS_PER_PLACE,
                      "regional_station_count": len(stations)},
        "stations": stations, "locations": regional,
    }


def unavailable(locations: list[dict], stamp: str, status: str, *, reason: str | None = None) -> dict:
    out = normalize_recent([], {}, locations, stamp)
    out.update({"status": status, "diagnostic": reason or status})
    return out


def collect(locations: list[dict], stamp: str, *, session: SgaaSession | None = None,
            token: str | None = None, on_request: Callable[[], None] | None = None,
            recent_fetcher: Callable[[str], Any] | None = None,
            sensor_fetcher: Callable[[str], Any] = fetch_sensor_types,
            now: datetime | None = None) -> dict:
    """Fetch regional sensor observations with a common, rate-limited SGAA JWT."""
    if token is None:
        email = os.environ.get("CEMADEN_PED_EMAIL", "")
        password = os.environ.get("CEMADEN_PED_PASSWORD", "")
        if email or password:
            if not email or not password:
                return unavailable(locations, stamp, "not_configured", reason="incomplete_sgaa_credentials")
            session = session or SgaaSession(email, password)
        else:
            token = os.environ.get("CEMADEN_PED_TOKEN", "")
    if session is None and not token:
        return unavailable(locations, stamp, "not_configured")
    try:
        current_token = session.token() if session is not None else token
    except SgaaAuthError as exc:
        return unavailable(locations, stamp, "access_restricted" if exc.reason == "access_restricted" else "unavailable",
                           reason="sgaa_" + exc.reason)

    def guarded_fetch(fetcher: Callable[[str], Any]) -> Any:
        nonlocal current_token
        try:
            if on_request is not None:
                on_request()
            return fetcher(current_token)
        except SensorSourceError as exc:
            if session is None or exc.reason not in ("token_expired", "bad_request"):
                raise
            current_token = session.token(rejected=current_token)
            if on_request is not None:
                on_request()
            return fetcher(current_token)

    try:
        catalog_status = "available"
        try:
            sensor_labels = normalize_types(guarded_fetch(sensor_fetcher))
        except (SensorSourceError, SgaaAuthError, ValueError):
            sensor_labels = {}
            catalog_status = "unavailable"
        states = sorted({loc.get("state", "SC") for loc in locations} & {"SC", "PR"})
        state_status = {}
        rows = []
        if recent_fetcher is not None:
            rows = guarded_fetch(recent_fetcher)
        else:
            for uf in states:
                try:
                    part = guarded_fetch(lambda jwt, uf=uf: fetch_recent(jwt, uf=uf))
                    if not isinstance(part, list) or len(part) > MAX_STATE_RECORDS:
                        raise SensorSourceError("invalid_recent_response")
                    rows.extend(row for row in part if isinstance(row, dict) and str(row.get("uf", "")).upper() == uf)
                    state_status[uf] = "available"
                except (SensorSourceError, SgaaAuthError) as exc:
                    state_status[uf] = exc.reason
            if not any(status == "available" for status in state_status.values()):
                result = unavailable(locations, stamp, "unavailable", reason="all_state_queries_failed")
                result["state_queries"] = state_status
                return result
        result = normalize_recent(rows, sensor_labels, locations, stamp, now=now)
        result["state_queries"] = state_status
        if any(status != "available" for status in state_status.values()):
            result["diagnostic"] = "partial_state_coverage"
            if result["status"] == "no_recent_data":
                result["status"] = "unavailable"
        result["catalog_status"] = catalog_status
        return result
    except (SgaaAuthError, SensorSourceError) as exc:
        reason = exc.reason
        status = "access_restricted" if reason in ("token_expired", "bad_request", "access_restricted") else "unavailable"
        return unavailable(locations, stamp, status, reason=reason)

