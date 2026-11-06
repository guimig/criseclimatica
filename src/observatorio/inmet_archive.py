"""Delayed INMET annual ZIP observations, distinct from real-time station readings.

The publicly published annual file can lag days or months. We read only a bounded
subset of local station CSV members, never extract paths, and publish *coverage*
next to every total. This is neither a live rain gauge nor a municipal estimate.
"""

from __future__ import annotations

import csv
import io
import math
import re
import tempfile
import unicodedata
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from .inmet import haversine_km

ARCHIVE_ROOT = "https://portal.inmet.gov.br/uploads/dadoshistoricos/"
SOURCE_PAGE = "https://portal.inmet.gov.br/dadoshistoricos"
KIND = "inmet_annual_zip_delayed_station_measurements_not_real_time"
MAX_ZIP_BYTES = 180_000_000
MAX_MEMBERS = 1600
MAX_MEMBER_BYTES = 18_000_000
MAX_STATIONS = 12
MAX_RECENT_DAYS = 14
CACHE_DAYS = 7
RETRY_HOURS = 24
STATION_RE = re.compile(r"(?<![A-Za-z0-9])(A\d{3,4})(?![A-Za-z0-9])", re.I)


class InmetArchiveError(RuntimeError):
    """The official annual archive was unavailable or failed strict validation."""


def _moment(value: Any) -> datetime:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise InmetArchiveError("Invalid archive timestamp") from exc
    if result.tzinfo is None:
        raise InmetArchiveError("Archive timestamp lacks timezone")
    return result.astimezone(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _fold(s: str) -> str:
    text = unicodedata.normalize("NFKD", s.upper())
    return "".join(c for c in text if not unicodedata.combining(c)).replace("  ", " ").strip()


def _number(value: str, low: float, high: float) -> float | None:
    raw = value.strip().replace(" ", "")
    if not raw or raw in {"-9999", "-9999,0", "9999", "9999,0", "NULL", "null", "NaN"}:
        return None
    try:
        result = float(raw.replace(",", "."))
    except (ValueError, OverflowError):
        return None
    return round(result, 2) if math.isfinite(result) and low <= result <= high else None


def _hour(date_text: str, hour_text: str) -> datetime:
    day_text = date_text.strip().replace("/", "-")
    hour = hour_text.strip().upper().replace("UTC", "").strip()
    if hour.isdigit():
        if len(hour) <= 2:
            hour = f"{int(hour):02d}:00"
        elif len(hour) in (3, 4):
            hour = hour.zfill(4)
            hour = hour[:2] + ":" + hour[2:]
    try:
        moment = datetime.fromisoformat(f"{day_text}T{hour}:00+00:00")
    except ValueError as exc:
        raise InmetArchiveError("Invalid official CSV date/hour") from exc
    if moment.minute != 0:
        raise InmetArchiveError("INMET hourly record is not aligned to hour")
    return moment


def nearby_station_codes(catalog: dict[str, Any], *, max_stations: int = MAX_STATIONS) -> dict[str, dict[str, Any]]:
    """Select catalog automatic stations only; conventional codes are not in this archive."""
    candidates: dict[str, dict[str, Any]] = {}
    for loc in catalog.get("locations", []) if isinstance(catalog, dict) else []:
        for station in loc.get("stations", []) if isinstance(loc, dict) else []:
            if not isinstance(station, dict):
                continue
            code = station.get("code")
            # Catalogues published before the conventional-network integration
            # lacked `network_type`. A validated INMET A-code identifies an
            # automatic station even for those cached legacy records.
            if not isinstance(code, str) or not STATION_RE.fullmatch(code):
                continue
            if station.get("network_type", "automatica") != "automatica":
                continue
            distance = station.get("distance_km")
            if not isinstance(distance, (int, float)) or isinstance(distance, bool) or not (0 <= distance <= 130):
                continue
            prior = candidates.get(code)
            if prior is None or distance < prior["distance_km"]:
                candidates[code] = {"code": code, "name": station.get("name") or code,
                                    "latitude": station.get("latitude"), "longitude": station.get("longitude"),
                                    "distance_km": float(distance)}
    return dict(list(sorted(candidates.items(), key=lambda item: (item[1]["distance_km"], item[0])))[:max_stations])


def station_metadata_from_zip(
    archive: zipfile.ZipFile, locations: list[dict[str, Any]], *,
    max_stations: int = MAX_STATIONS, max_distance_km: float = 130.0,
) -> dict[str, dict[str, Any]]:
    """Discover nearby INMET A-code stations from official CSV headers.

    The annual ZIP includes WMO code and coordinates before the measurement
    table. This is independent of the changing JSON station-catalogue schema.
    No entry is extracted to disk and only the first 4 KiB of a member is read.
    """
    candidates: dict[str, dict[str, Any]] = {}
    for entry in archive.infolist():
        if (entry.is_dir() or not entry.filename.upper().endswith(".CSV") or
                entry.file_size > MAX_MEMBER_BYTES or entry.flag_bits & 0x1):
            continue
        matches = STATION_RE.findall(Path(entry.filename).name.upper())
        if len(set(matches)) != 1:
            continue
        code = matches[0]
        try:
            with archive.open(entry) as source:
                raw = source.read(4096)
            # INMET exports historically use Latin-1 with a few UTF-8 exports.
            text = raw.decode("utf-8-sig") if raw.startswith(b"\xef\xbb\xbf") else raw.decode("latin-1")
        except (RuntimeError, OSError, UnicodeError, zipfile.BadZipFile):
            continue
        metadata: dict[str, str] = {}
        for line in text.splitlines()[:14]:
            if ";" not in line:
                continue
            key, value, *_ = (chunk.strip() for chunk in line.split(";"))
            normalized = _fold(key).rstrip(":")
            if normalized.startswith(("LATITUDE", "LONGITUDE", "ESTACAO", "CODIGO", "UF")):
                metadata[normalized.split(" (")[0]] = value
        header_code = metadata.get("CODIGO", "").upper()
        if header_code != code:
            continue
        try:
            lat = float(metadata["LATITUDE"].replace(",", "."))
            lon = float(metadata["LONGITUDE"].replace(",", "."))
        except (KeyError, ValueError, OverflowError):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        distances = [haversine_km(loc["latitude"], loc["longitude"], lat, lon) for loc in locations]
        if not distances:
            continue
        minimum = min(distances)
        if minimum > max_distance_km:
            continue
        station = {"code": code, "name": metadata.get("ESTACAO") or code,
                   "latitude": lat, "longitude": lon, "distance_km": round(minimum, 1),
                   "metadata_source": "inmet_annual_csv_header"}
        old = candidates.get(code)
        if old is None or station["distance_km"] < old["distance_km"]:
            candidates[code] = station
    return dict(sorted(candidates.items(), key=lambda item: (item[1]["distance_km"], item[0]))[:max_stations])


def _read_station_csv(archive: zipfile.ZipFile, entry: zipfile.ZipInfo, *, year: int) -> list[dict[str, Any]]:
    if entry.file_size > MAX_MEMBER_BYTES or entry.flag_bits & 0x1:
        raise InmetArchiveError("INMET CSV member exceeds size policy or is encrypted")
    with archive.open(entry) as fh:
        content = fh.read(MAX_MEMBER_BYTES + 1)
    if len(content) > MAX_MEMBER_BYTES:
        raise InmetArchiveError("INMET CSV exceeds decompressed cap")
    reader = csv.reader(io.StringIO(content.decode("utf-8-sig") if content.startswith(b"\xef\xbb\xbf") else content.decode("latin-1")), delimiter=";")
    header = None
    data_i = hour_i = rain_i = temp_i = None
    rows: dict[str, dict[str, Any]] = {}
    for index, fields in enumerate(reader):
        if index > 250_000:
            raise InmetArchiveError("INMET station row count exceeds policy")
        names = [_fold(s) for s in fields]
        if header is None:
            if any(s.startswith("DATA ") or s == "DATA" for s in names) and any(s.startswith("HORA") for s in names):
                header = names
                data_i = next(i for i, s in enumerate(names) if s.startswith("DATA"))
                hour_i = next(i for i, s in enumerate(names) if s.startswith("HORA"))
                rain_i = next((i for i, s in enumerate(names) if "PRECIPIT" in s and "HORAR" in s), None)
                temp_i = next((i for i, s in enumerate(names) if "TEMPERATURA" in s and "BULBO SECO" in s and "HORAR" in s), None)
                if rain_i is None:
                    raise InmetArchiveError("Official CSV has no hourly precipitation column")
            continue
        if len(fields) <= max(data_i, hour_i, rain_i):
            continue
        try:
            observed = _hour(fields[data_i], fields[hour_i])
        except InmetArchiveError:
            continue
        if observed.year != year:
            continue
        stamp = _stamp(observed)
        rain = _number(fields[rain_i], 0, 300)
        temp = _number(fields[temp_i], -60, 65) if temp_i is not None and len(fields) > temp_i else None
        value = {"at": stamp, "rain_mm": rain, "temperature_c": temp}
        existing = rows.get(stamp)
        if existing is not None and existing != value:
            raise InmetArchiveError("Conflicting duplicate INMET hour")
        rows[stamp] = value
    if header is None:
        raise InmetArchiveError("INMET station CSV missing header")
    return [rows[key] for key in sorted(rows)]


def parse_annual_zip(data: bytes, selected: dict[str, dict[str, Any]], now: datetime,
                     *, locations: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Read limited CSV members without extracting untrusted ZIP file paths.

    If `locations` is provided, the ZIP itself supplies a fallback catalogue.
    """
    if not isinstance(data, bytes) or not data.startswith(b"PK") or len(data) > MAX_ZIP_BYTES:
        raise InmetArchiveError("Invalid official annual ZIP")
    now = now.astimezone(timezone.utc)
    results = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > MAX_MEMBERS:
                raise InmetArchiveError("Annual ZIP has too many members")
            if locations is not None:
                from_zip = station_metadata_from_zip(archive, locations)
                # Prefer ZIP metadata when the saved catalogue is incomplete;
                # both sources are official, but the ZIP ties coordinates to data.
                selected = dict(sorted({**selected, **from_zip}.items(),
                                       key=lambda kv: (kv[1]["distance_km"], kv[0]))[:MAX_STATIONS])
            for code, station in selected.items():
                matches = [e for e in members if not e.is_dir() and e.filename.upper().endswith(".CSV")
                           and code in STATION_RE.findall(Path(e.filename).name.upper())]
                if not matches:
                    continue
                # 2026 archives may contain split periods; reject overlaps with conflicting measurements.
                combined: dict[str, dict[str, Any]] = {}
                for entry in matches[:6]:
                    for row in _read_station_csv(archive, entry, year=now.year):
                        old = combined.get(row["at"])
                        if old is not None and old != row:
                            raise InmetArchiveError("Conflicting overlapping annual CSV members")
                        combined[row["at"]] = row
                if not combined:
                    continue
                ordered = [combined[stamp] for stamp in sorted(combined)]
                last = _moment(ordered[-1]["at"])
                if last > now + timedelta(hours=2):
                    raise InmetArchiveError("Official archive contains future readings")
                latest_date = last.date()
                lower = latest_date - timedelta(days=MAX_RECENT_DAYS - 1)
                grouped: dict[date, list[dict[str, Any]]] = defaultdict(list)
                for row in ordered:
                    obs_day = _moment(row["at"]).date()
                    if lower <= obs_day <= latest_date:
                        grouped[obs_day].append(row)
                days = []
                for day in sorted(grouped, reverse=True):
                    rows = grouped[day]
                    measured = [r["rain_mm"] for r in rows if r["rain_mm"] is not None]
                    rain_hours = len(measured)
                    # Totals are published only when all 24 hourly readings are present.
                    day_sum = round(sum(measured), 2) if rain_hours == 24 else None
                    days.append({"day_utc": day.isoformat(), "rain_total_complete_mm": day_sum,
                                 "rain_sum_available_hours_mm": round(sum(measured), 2) if measured else None,
                                 "rain_measured_hours": rain_hours, "rain_expected_hours": 24})
                results.append({"code": code, "name": station["name"], "latitude": station["latitude"],
                                "longitude": station["longitude"], "last_observation_at": _stamp(last),
                                "days": days})
    except (zipfile.BadZipFile, EOFError, OSError, UnicodeError) as exc:
        raise InmetArchiveError(f"Invalid INMET archive: {type(exc).__name__}") from exc
    return results


def _download_year(year: int, *, timeout: int = 80) -> bytes:
    url = f"{ARCHIVE_ROOT}{year}.zip"
    req = Request(url, headers={"Accept": "application/zip,application/octet-stream", "User-Agent": "criseclimatica/0.7 (public historical weather analysis)"})
    try:
        with urlopen(req, timeout=timeout) as response:
            final = urlparse(response.geturl())
            if (response.status != 200 or final.scheme != "https" or
                    final.hostname != "portal.inmet.gov.br" or final.username or final.password or
                    not final.path.endswith(f"/{year}.zip")):
                raise InmetArchiveError("Annual archive redirected outside allowed official ZIP")
            # Stream and cap bytes. A ZIP is not read into RAM until size is verified.
            with tempfile.SpooledTemporaryFile(max_size=8_000_000) as temporary:
                total = 0
                while True:
                    chunk = response.read(1_000_000)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_ZIP_BYTES:
                        raise InmetArchiveError("Annual archive download exceeds 180 MB")
                    temporary.write(chunk)
                temporary.seek(0)
                return temporary.read()
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise InmetArchiveError(f"Official annual ZIP unavailable: {type(exc).__name__}") from exc


def unavailable_archive(checked_at: str, status: str = "unavailable") -> dict[str, Any]:
    return {"schema_version": 1, "kind": KIND, "status": status, "checked_at": checked_at,
            "last_attempt_at": checked_at, "retrieved_at": None, "archive_year": _moment(checked_at).year,
            "latest_observation_at": None,
            "source": {"id": "inmet-annual", "name": "INMET - arquivo anual de automaticas", "url": SOURCE_PAGE},
            "stations": [], "locations": [],
            "notice": "Arquivo anual oficial de leituras horarias, publicado com atraso. Nunca representa chuva em tempo real."}


def _valid_previous(previous: Any, year: int) -> bool:
    return (isinstance(previous, dict) and previous.get("schema_version") == 1 and
            previous.get("kind") == KIND and previous.get("archive_year") == year and
            isinstance(previous.get("stations"), list) and len(previous["stations"]) <= MAX_STATIONS and
            isinstance(previous.get("source"), dict) and previous["source"].get("id") == "inmet-annual")


def _present(data: dict[str, Any], checked_at: str, *, cached: bool = False) -> dict[str, Any]:
    out = {**data, "checked_at": checked_at}
    last = out.get("latest_observation_at")
    if last:
        age = _moment(checked_at) - _moment(last)
        out["status"] = "stale" if age > timedelta(days=14) else "cached" if cached else "available"
    return out


def collect_archive(locations: list[dict], catalog: dict, checked_at: str, *,
                    previous: dict | None = None, fixture_zip: bytes | None = None) -> dict:
    """Refresh at most weekly; on errors preserve validated cached readings with dates.

    Empty/failed downloads cannot magically mean there was zero precipitation.
    """
    now = _moment(checked_at)
    year = now.year
    selected = nearby_station_codes(catalog)
    previous_ok = _valid_previous(previous, year)
    if fixture_zip is None and previous_ok:
        def age_of(value: Any) -> timedelta:
            try:
                return now - _moment(value)
            except InmetArchiveError:
                return timedelta(days=100)
        since_download = age_of(previous.get("retrieved_at"))
        since_attempt = age_of(previous.get("last_attempt_at"))
        if previous.get("stations") and timedelta(0) <= since_download < timedelta(days=CACHE_DAYS):
            return _present(previous, checked_at, cached=True)
        if (timedelta(0) <= since_attempt < timedelta(hours=RETRY_HOURS) and
                (previous.get("stations") or previous.get("station_discovery_version") == 2)):
            return _present(previous, checked_at, cached=True) if previous.get("stations") else {**previous, "checked_at": checked_at}
    try:
        # An incomplete or legacy INMET JSON catalogue must not stop us from
        # discovering genuine local A-code stations in the official ZIP itself.
        data = fixture_zip if fixture_zip is not None else _download_year(year)
        stations = parse_annual_zip(data, selected, now, locations=locations)
        if not stations:
            result = unavailable_archive(checked_at, "no_nearby_stations")
            result["station_discovery_version"] = 2
            return result
        closest: list[dict] = []
        for place in locations:
            matching = sorted(({"code": row["code"], "distance_km": round(haversine_km(
                place["latitude"], place["longitude"], row["latitude"], row["longitude"]), 1)}
                for row in stations if isinstance(row.get("latitude"), (int, float)) and isinstance(row.get("longitude"), (int, float))),
                key=lambda x: (x["distance_km"], x["code"]))
            closest.append({"location_id": place["id"], "stations": [x for x in matching if x["distance_km"] <= 130][:4]})
        latest = max(station["last_observation_at"] for station in stations)
        result = unavailable_archive(checked_at)
        result.update({"stations": stations, "locations": closest, "retrieved_at": checked_at,
                       "station_discovery_version": 2, "last_attempt_at": checked_at,
                       "latest_observation_at": latest})
        return _present(result, checked_at)
    except (InmetArchiveError, ValueError, TypeError) as exc:
        # Status is honest and does not reveal token or internal URL query strings.
        print(f"INMET annual archive: {type(exc).__name__}")
        if previous_ok and previous.get("stations"):
            return _present({**previous, "last_attempt_at": checked_at}, checked_at, cached=True)
        result = unavailable_archive(checked_at)
        result["diagnostic"] = "archive_not_readable_or_not_published"
        return result
