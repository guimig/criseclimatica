"""Recent observed precipitation from the documented CEMADEN PED endpoint.

JWT in `token` request HEADER; never publish, log, or include the token in URLs.
Only station accumulations from exact IBGE municipalities are presented, no
arbitrary averaging or inference for municipalities without a station.
"""
from __future__ import annotations

import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

API = "https://sws.cemaden.gov.br/PED/rest/pcds-acum/acumulados-recentes"
DOCS = "https://sws.cemaden.gov.br/PED/api/ui/"
KIND = "cemaden_recent_observed_station_rainfall_raw"
IBGE = re.compile(r"\d{7}")
STATION = re.compile(r"[A-Za-z0-9-]{4,25}")


class CemadenError(RuntimeError):
    def __init__(self, message: str, reason: str = "unavailable"):
        super().__init__(message)
        self.reason = reason


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the JWT to another origin.


def fetch(ibge: str, token: str, *, timeout: int = 12) -> list[dict[str, Any]]:
    if not IBGE.fullmatch(ibge) or not token or len(token) > 4096 or any(c.isspace() for c in token):
        raise CemadenError("Invalid municipality or authorization configuration", "access_restricted")
    url = API + "?" + urlencode({"codibge": ibge, "formato": "JSON"})
    request = Request(url, headers={"Accept": "application/json", "token": token,
                                     "User-Agent": "ObservatorioClimatico/0.5 (https://github.com/guimig/criseclimatica)"})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            if response.status != 200:
                raise CemadenError("Cemaden returned unexpected status")
            body = response.read(800_001)
            if len(body) > 800_000:
                raise CemadenError("Cemaden response too large")
        raw = json.loads(body.decode("utf-8"))
        if not isinstance(raw, list) or len(raw) > 300:
            raise CemadenError("Cemaden API returned an invalid dataset")
        return raw
    except HTTPError as exc:
        reason = "access_restricted" if exc.code in (401, 403) else "unavailable"
        raise CemadenError("Cemaden request rejected", reason) from None
    except (URLError, TimeoutError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise CemadenError("Cemaden request could not be completed") from None


def _number(value: Any, upper: float) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = float(value.replace(",", ".")) if isinstance(value, str) else float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return round(n, 2) if math.isfinite(n) and 0 <= n <= upper else None


def _timestamp(value: Any) -> datetime | None:
    """PED example timestamps are UTC without TZ suffix; Cemaden records in UTC."""
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when.astimezone(timezone.utc)
    except ValueError:
        return None


def normalize(raw: Any, ibge: str, now: datetime) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) > 300:
        raise CemadenError("Invalid Cemaden station response")
    by_station: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict) or str(item.get("codibge")) != ibge:
            continue
        code = str(item.get("codestacao") or "")
        time = _timestamp(item.get("datahora"))
        if not STATION.fullmatch(code) or time is None:
            continue
        if not -timedelta(minutes=10) <= now - time <= timedelta(hours=6):
            continue
        r1 = _number(item.get("acc1hr"), 500)
        r24 = _number(item.get("acc24hr"), 1500)
        if r1 is None and r24 is None:
            continue
        entry = {"code": code, "observed_at": time.isoformat(timespec="seconds").replace("+00:00", "Z"),
                 "rain_1h_mm": r1, "rain_24h_mm": r24,
                 "quality": "cemaden_raw_station_accumulations_not_municipality_averages"}
        old = by_station.get(code)
        if old is None or entry["observed_at"] > old["observed_at"]:
            by_station[code] = entry
    return sorted(by_station.values(), key=lambda s: s["code"])


def collect(locations: list[dict[str, Any]], stamp: str, *, token: str | None = None,
            now: datetime | None = None, fetcher: Callable = fetch) -> dict[str, Any]:
    token = token if token is not None else os.environ.get("CEMADEN_PED_TOKEN", "")
    status = "not_configured" if not token else "unavailable"
    base = {"schema_version": 1, "kind": KIND, "status": status, "checked_at": stamp,
            "source": {"id": "cemaden", "name": "Cemaden PED", "url": DOCS},
            "locations": [{"location_id": loc["id"], "ibge_code": str(loc["ibge_code"]), "stations": []} for loc in locations],
            "municipalities_checked": 0, "municipalities_failed": 0,
            "diagnostic": "token_not_configured" if not token else None}
    if not token:
        return base
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    def get(loc):
        ibge = str(loc["ibge_code"])
        try:
            return normalize(fetcher(ibge, token), ibge, now), None
        except CemadenError as exc:
            return [], exc.reason
        except (ValueError, TypeError, OSError):
            return [], "unavailable"
    with ThreadPoolExecutor(max_workers=min(3, len(locations))) as pool:
        results = list(pool.map(get, locations))
    failures = [err for _, err in results if err]
    for row, (stations, _) in zip(base["locations"], results):
        row["stations"] = stations
    base["municipalities_checked"] = len(locations)
    base["municipalities_failed"] = len(failures)
    if any(rows for rows, _ in results):
        base["status"] = "available"
    elif failures and all(reason == "access_restricted" for reason in failures):
        base["status"] = "access_restricted"
    elif failures:
        base["status"] = "unavailable"
    else:
        base["status"] = "no_recent_data"
    base["diagnostic"] = "partial" if base["status"] == "available" and failures else (failures[0] if failures else "ok")
    return base
