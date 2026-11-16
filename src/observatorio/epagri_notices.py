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

from .notice_time import normalize_window, moment
from .notice_territory import classify as territory_classify, fold

ROOT = "https://ciram.epagri.sc.gov.br"
CATEGORY = ROOT + "/index.php/category/avisos-meteorologicos/"
RSS = CATEGORY + "feed/"
KIND = "epagri_ciram_official_advisories_not_civil_defense_alerts"
TZ = ZoneInfo("America/Sao_Paulo")
MAX_BYTES = 650_000
MAX_PAGE_BYTES = 700_000
MAX_NOTICES = 32
REGION_PATTERN = re.compile(r"(?:regi[oõ]es?|abrang[eê]ncia|munic[ií]pios|localidades?|[áa]reas?)\s*:\s*([^\n]{0,800})", re.I)
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
    """Read explicitly published Brazilian dates; optional 8h, 08h30 or 08:30."""
    fields = []
    for key in ("In[ií]cio", "Fim"):
        match = re.search(rf"\b{key}\s*:\s*(\d{{1,2}}/\d{{1,2}}/\d{{4}})([^\n]{{0,60}})", text, re.I)
        if not match:
            return None, None
        date, suffix = match.groups()
        try:
            day = datetime.strptime(date, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return None, None
        suffix = suffix.strip()
        clock_match = re.search(r"(?:[àa]s?\s*)?(\d{1,2})\s*[h:]\s*(\d{2})?(?:min)?\b", suffix, re.I)
        if clock_match:
            hour, minute = clock_match.groups()
            clock = f"{int(hour):02d}:{minute or '00'}"
        else:
            # A date followed by an unparsable time must not become a whole-day
            # notice by accident.
            if re.search(r"\b(?:[àa]s|as)\s*\d|\b\d{1,2}\s*[h:]", suffix, re.I):
                return None, None
            clock = None
        fields.append((day, clock))
    return normalize_window(fields[0][0], fields[0][1], fields[1][0], fields[1][1])[:2]


def _region(text: str) -> tuple[str | None, str]:
    match = REGION_PATTERN.search(text)
    if not match:
        return None, "not_confirmed"
    line = re.split(r"\n|Previs[aã]o\s*:|Sistema\s*:", match.group(1), maxsplit=1, flags=re.I)[0]
    line = re.sub(r"\s+", " ", line).strip()[:800]
    scope, _ = territory_classify(line, full_text=text)
    return line or None, "mentioned" if scope in ("municipality_explicit", "regional_reference_not_municipal_confirmation") else "other_regions_or_unclear"


def _enrich_articles(notices: list[dict], *, fixture: bool) -> list[dict]:
    """Visit bounded official articles only when feed lacks an explicit interval."""
    if fixture:
        return notices
    attempts = 0
    for notice in notices:
        if notice["valid_from"] and notice["valid_until"]:
            continue
        if attempts >= 4:
            break
        attempts += 1
        try:
            page = _plain(_download(notice["url"], max_bytes=MAX_PAGE_BYTES).decode("utf-8"))
            begins, ends = _window(page)
            places, coverage = _region(page)
            if begins and ends:
                notice.update(valid_from=begins, valid_until=ends,
                              window_status="explicit_in_official_article")
            if places:
                notice.update(regions_text=places, north_coast_scope=coverage)
            if begins or places:
                notice["assessment_text"] = page[:6000]
            if _explicit_cancellation(notice["title"], page):
                notice["cancelled"] = True
        except (EpagriNoticeError, UnicodeDecodeError, ValueError):
            continue
    return notices


def _retain_active(previous: dict | None, now: datetime) -> list[dict]:
    """Historical time in cache does not invalidate an issued official warning."""
    if not isinstance(previous, dict) or previous.get("kind") != KIND:
        return []
    records = previous.get("notices", [])
    if not isinstance(records, list) or len(records) > MAX_NOTICES:
        return []
    result = []
    for row in records:
        if not isinstance(row, dict) or row.get("cancelled") or not _safe_url(row.get("url")):
            continue
        end = moment(row.get("valid_until"))
        if end and end > now:
            result.append({**row, "retained_previous": True,
                           "verification_status": "not_reconfirmed"})
    return result


def _explicit_cancellation(title: str, text: str) -> bool:
    """Only explicit cancellation phrases; never infer cancellation from RSS omission."""
    for fragment in (title, text[:300]):
        value = fold(fragment)
        if re.search(r"\b(?:aviso|alerta)\b.{0,80}\b(?:cancelad[oa]|encerrad[oa])\b", value):
            if not re.search(r"\bnao\s+(?:foi\s+)?(?:cancelad[oa]|encerrad[oa])\b", value):
                return True
        if re.search(r"\bcancelamento\s+d[oa]\s+(?:aviso|alerta)\b", value):
            return True
    return False


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
            "assessment_text": full_text[:6000],
            "notice_kind": "epagri_meteorological_advisory_not_civil_defense_alert",
            "cancelled": _explicit_cancellation(title, full_text),
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
    if (fixture is None and valid_previous and timedelta(0) <= age < timedelta(hours=3)
            and all(isinstance(n, dict) and "assessment_text" in n for n in previous["notices"])):
        return {**previous, "status": "cached", "checked_at": stamp}
    try:
        notices = _enrich_articles(parse_feed(_download(RSS) if fixture is None else fixture, stamp), fixture=fixture is not None)
        indexed = {n["url"]: n for n in notices}
        for old in _retain_active(previous, now):
            indexed.setdefault(old["url"], old)
        notices = sorted(indexed.values(), key=lambda n: n["published_at"], reverse=True)[:MAX_NOTICES]
        # Do not open unverified article URLs or infer alert validity. Some
        # official feeds expose a complete content:encoded body with dates.
        result = unavailable(stamp)
        result.update({"status": "available" if notices else "no_recent_notices",
                       "retrieved_at": stamp, "notices": notices})
        return result
    except (EpagriNoticeError, ValueError) as exc:
        print(f"Epagri/Ciram advisories: {type(exc).__name__}")
        active = _retain_active(previous, now)
        if active:
            return {**previous, "status": "stale", "checked_at": stamp, "notices": active}
        return unavailable(stamp)
