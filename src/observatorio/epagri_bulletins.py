"""Recent Epagri/Ciram human-readable regional forecast bulletins via official RSS.

Editorial weather text is NOT an automated point forecast, measured weather,
or an official Civil Defense alert. Publication timestamps do not prove that
conditions still apply at a precise municipality.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from .epagri_notices import _plain

ROOT = "https://ciram.epagri.sc.gov.br"
CATEGORY = ROOT + "/index.php/category/previsao/"
FEED = CATEGORY + "feed/"
KIND = "epagri_ciram_editorial_forecast_bulletins_not_emergency_alerts"
MAX_BYTES = 700_000
MAX_BULLETINS = 4


class BulletinError(RuntimeError):
    """Unexpected or inaccessible official Epagri editorial forecast feed."""


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise BulletinError("Missing time")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BulletinError("Invalid time") from exc
    if dt.tzinfo is None:
        raise BulletinError("Timezone missing")
    return dt.astimezone(timezone.utc)


def _safe(url: Any) -> bool:
    if not isinstance(url, str) or len(url) > 600:
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == "ciram.epagri.sc.gov.br" and not parsed.username and not parsed.password


def _fetch(*, timeout: int = 12) -> bytes:
    req = Request(FEED, headers={"Accept": "application/rss+xml,application/xml", "User-Agent": "criseclimatica-editorial-forecast/0.9"})
    try:
        with urlopen(req, timeout=timeout) as response:
            if response.status != 200 or not _safe(response.geturl()):
                raise BulletinError("Unexpected editorial feed redirect")
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise BulletinError("Oversized editorial feed")
        return data
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise BulletinError(f"Epagri editorial forecast feed inaccessible: {type(exc).__name__}") from exc


def parse_feed(data: bytes, stamp: str) -> list[dict]:
    if (not isinstance(data, bytes) or len(data) > MAX_BYTES or
            b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper()):
        raise BulletinError("Invalid editorial feed")
    now = _utc(stamp)
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise BulletinError("Malformed editorial feed XML") from exc
    if root.tag.lower() != "rss" or root.find("channel") is None:
        raise BulletinError("Unexpected Epagri editorial RSS schema")
    found = {}
    for entry in root.findall("./channel/item")[:30]:
        link = (entry.findtext("link") or "").strip()
        if not _safe(link) or "/category/" in link:
            continue
        title = re.sub(r"\s+", " ", _plain(entry.findtext("title") or "")).strip()[:160]
        if not title:
            continue
        try:
            when = parsedate_to_datetime(entry.findtext("pubDate") or "")
            if when.tzinfo is None:
                continue
            when = when.astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
        if not now - timedelta(days=7) <= when <= now + timedelta(hours=3):
            continue
        content = (entry.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or
                   entry.findtext("description") or "")
        description = re.sub(r"\s+", " ", _plain(content)).strip()[:900]
        lowered = title.lower()
        category = "five_day_outlook" if "5 dias" in lowered or "cinco dias" in lowered else (
            "ten_day_tendency" if "10 dias" in lowered or "tendência" in lowered or "tendencia" in lowered else
            "regional_forecast_text")
        found[link] = {
            "title": title, "url": link,
            "published_at": when.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "bulletin_kind": category,
            "summary": description,
            "assessment_text": _plain(content)[:12000],
            "data_kind": "editorial_regional_forecast_not_station_observation_or_civil_defense_alert",
        }
    return sorted(found.values(), key=lambda x: x["published_at"], reverse=True)[:MAX_BULLETINS]


def unavailable(stamp: str) -> dict:
    return {
        "schema_version": 1, "kind": KIND, "status": "unavailable", "checked_at": stamp,
        "retrieved_at": None, "source": {"id": "epagri-ciram-editorial", "name": "Epagri/Ciram", "url": CATEGORY},
        "bulletins": [], "note": "Previsao regional editorial; nao e alerta da Defesa Civil nem leitura instrumental.",
    }


def collect(stamp: str, *, previous: dict | None = None, fixture: bytes | None = None) -> dict:
    now = _utc(stamp)
    previous_ok = (isinstance(previous, dict) and previous.get("kind") == KIND and
                   previous.get("schema_version") == 1 and previous.get("status") in
                   ("available", "cached", "stale", "no_recent_bulletins") and
                   isinstance(previous.get("bulletins"), list) and len(previous["bulletins"]) <= MAX_BULLETINS and
                   previous.get("retrieved_at"))
    age = None
    if previous_ok:
        try:
            age = now - _utc(previous["retrieved_at"])
        except BulletinError:
            previous_ok = False
    if fixture is None and previous_ok and timedelta(0) <= age < timedelta(hours=3):
        return {**previous, "checked_at": stamp, "status": "cached"}
    try:
        bulletins = parse_feed(fixture if fixture is not None else _fetch(), stamp)
        if fixture is None:
            from .epagri_notices import _download, EpagriNoticeError
            from .publication_text import extract
            for bulletin in bulletins[:2]:
                try:
                    body=extract(_download(bulletin['url']))
                    if body:bulletin.update(assessment_text=body,text_origin='official_article_body')
                except (EpagriNoticeError, OSError, ValueError, UnicodeError):
                    bulletin['text_origin']='feed_text_article_unavailable'
        result = unavailable(stamp)
        result.update({"status": "available" if bulletins else "no_recent_bulletins",
                       "retrieved_at": stamp, "bulletins": bulletins})
        return result
    except (BulletinError, ValueError) as exc:
        print(f"Epagri editorial forecast: {type(exc).__name__}")
        if previous_ok and timedelta(0) <= age <= timedelta(hours=24):
            return {**previous, "checked_at": stamp, "status": "stale"}
        return unavailable(stamp)
