"""Epagri/Ciram official weather-advisory publications (not emergency alerts).

Read the official RSS category and its own public article pages. Only report a
validity window when explicitly published by the meteorologists. The system
never asserts an active Civil Defense alert or citywide coverage.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = "https://ciram.epagri.sc.gov.br"
CATEGORY = ROOT + "/index.php/category/avisos-meteorologicos/"
RSS = CATEGORY + "feed/"
KIND = "epagri_ciram_official_advisories_not_civil_defense_alerts"
TZ = ZoneInfo("America/Sao_Paulo")
MAX_BYTES = 650_000
MAX_PAGE_BYTES = 700_000
MAX_NOTICES = 8
REGION_PATTERN = re.compile(r"regi[oõ]es\s*:\s*([^\n]{0,220})", re.I)
WINDOW_PATTERN = r"{label}\s*:\s*(\d{{2}}/\d{{2}}/\d{{4}})\s*(?:[àa]s|as)?\s*(\d{{1,2}})\s*[h:]\s*(\d{{2}})"


class EpagriNoticeError(RuntimeError):
    """Epagri public advisory feed was not readable or structurally valid."""


class _Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.hidden += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.hidden = max(0, self.hidden - 1)
        if tag in ("p", "div", "li"):
            self.parts.append("\n")

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)


def _plain(value: str) -> str:
    parser = _Plain()
    parser.feed(value)
    text = html.unescape("".join(parser.parts)).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text)


def _safe_url(url: Any) -> bool:
    if not isinstance(url, str) or len(url) > 600:
        return False
    parsed = urlparse(url)
    return (parsed.scheme == "https" and parsed.hostname == "ciram.epagri.sc.gov.br" and
            not parsed.username and not parsed.password)


def _download(url: str, *, max_bytes: int = MAX_BYTES, timeout: int = 12) -> bytes:
    if not _safe_url(url):
        raise EpagriNoticeError("Untrusted advisory URL")
    req = Request(url, headers={"Accept": "application/rss+xml,application/xml,text/html", "User-Agent": "criseclimatica-epagri-advisories/0.8"})
    try:
        with urlopen(req, timeout=timeout) as response:
            if response.status != 200 or not _safe_url(response.geturl()):
                raise EpagriNoticeError("Epagri advisory redirected outside official source")
            raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise EpagriNoticeError("Advisory response exceeds size policy")
        return raw
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise EpagriNoticeError(f"Official advisory unavailable: {type(exc).__name__}") from exc


def _utc(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise EpagriNoticeError("Invalid advisory timestamp") from exc
    if dt.tzinfo is None:
        raise EpagriNoticeError("Naive advisory timestamp")
    return dt.astimezone(timezone.utc)


def _window(text: str) -> tuple[str | None, str | None]:
    moments = []
    for key in ("In[ií]cio", "Fim"):
        match = re.search(WINDOW_PATTERN.format(label=key), text, re.I)
        if not match:
            return None, None
        day, hour, minute = match.groups()
        try:
            dt = datetime.strptime(day, "%d/%m/%Y").replace(hour=int(hour), minute=int(minute), tzinfo=TZ)
        except ValueError:
            return None, None
        moments.append(dt.astimezone(timezone.utc))
    if moments[1] < moments[0] or moments[1] - moments[0] > timedelta(days=14):
        return None, None
    return tuple(dt.isoformat(timespec="seconds").replace("+00:00", "Z") for dt in moments)


def _region(text: str) -> tuple[str | None, str]:
    match = REGION_PATTERN.search(text)
    if not match:
        return None, "not_confirmed"
    line = re.split(r"\n|Previs[aã]o\s*:|Sistema\s*:", match.group(1), maxsplit=1, flags=re.I)[0]
    line = re.sub(r"\s+", " ", line).strip()[:200]
    norm = html.unescape(line).lower()
    region = "mentioned" if any(s in norm for s in ("litoral norte", "todas as regi", "todo o estado")) else "other_regions_or_unclear"
    return line or None, region


def parse_feed(data: bytes, checked_at: str) -> list[dict[str, Any]]:
    """Validate RSS; no advisory is labeled as an active official alert."""
    now = _utc(checked_at)
    if len(data) > MAX_BYTES or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise EpagriNoticeError("Invalid official RSS size or entity declaration")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise EpagriNoticeError("Malformed Epagri RSS") from exc
    if root.tag.lower() != "rss" or root.find("channel") is None:
        raise EpagriNoticeError("Unexpected Epagri RSS document")
    result = {}
    for item in root.findall("./channel/item")[:50]:
        link = (item.findtext("link") or "").strip()
        if not _safe_url(link) or "/category/" in link:
            continue
        title = re.sub(r"\s+", " ", _plain(item.findtext("title") or "")).strip()[:180]
        if not title:
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo is None:
                raise ValueError("No timezone")
            published = published.astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
        if not now - timedelta(days=15) <= published <= now + timedelta(hours=3):
            continue
        content = (item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or
                   item.findtext("description") or "")
        full_text = _plain(content)[:12_000]
        begins, ends = _window(full_text)
        places, coverage = _region(full_text)
        result[link] = {
            "title": title, "url": link,
            "published_at": published.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "valid_from": begins, "valid_until": ends,
            "window_status": "explicit_in_publication" if begins else "not_confirmed",
            "regions_text": places, "north_coast_scope": coverage,
            "summary": re.sub(r"\s+", " ", full_text).strip()[:600],
            "notice_kind": "epagri_meteorological_advisory_not_civil_defense_alert",
        }
    return sorted(result.values(), key=lambda x: x["published_at"], reverse=True)[:MAX_NOTICES]


def unavailable(stamp: str) -> dict:
    return {
        "schema_version": 1, "kind": KIND, "status": "unavailable", "checked_at": stamp,
        "retrieved_at": None, "source": {"id": "epagri-ciram", "name": "Epagri/Ciram", "url": CATEGORY},
        "notices": [], "note": "Avisos meteorologicos publicados nao substituem alertas de emergencia da Defesa Civil.",
    }


def collect(stamp: str, *, previous: dict | None = None, fixture: bytes | None = None) -> dict:
    now = _utc(stamp)
    valid_previous = (isinstance(previous, dict) and previous.get("schema_version") == 1 and
                      previous.get("kind") == KIND and previous.get("status") in ("available", "cached", "stale", "no_recent_notices") and
                      isinstance(previous.get("notices"), list) and len(previous["notices"]) <= MAX_NOTICES and
                      previous.get("retrieved_at"))
    age = None
    if valid_previous:
        try:
            age = now - _utc(previous["retrieved_at"])
        except EpagriNoticeError:
            valid_previous = False
    if fixture is None and valid_previous and timedelta(0) <= age < timedelta(hours=3):
        return {**previous, "status": "cached", "checked_at": stamp}
    try:
        notices = parse_feed(_download(RSS) if fixture is None else fixture, stamp)
        # Do not open unverified article URLs or infer alert validity. Some
        # official feeds expose a complete content:encoded body with dates.
        result = unavailable(stamp)
        result.update({"status": "available" if notices else "no_recent_notices",
                       "retrieved_at": stamp, "notices": notices})
        return result
    except (EpagriNoticeError, ValueError) as exc:
        print(f"Epagri/Ciram advisories: {type(exc).__name__}")
        if valid_previous and timedelta(0) <= age <= timedelta(hours=48):
            return {**previous, "status": "stale", "checked_at": stamp}
        return unavailable(stamp)
