"""Best-effort official *publications* from Santa Catarina Civil Defense.

WordPress JSON and category RSS feeds are public-facing publication channels,
not a documented machine-readable feed of currently valid civil-defense alerts.
Never infer active status, cancellations, event occurrence or precise territory
from a headline, a short excerpt or a publishing date.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from unicodedata import normalize
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

BASE = "https://www.defesacivil.sc.gov.br"
WP_API = BASE + "/wp-json/wp/v2/posts?per_page=35&_fields=date,date_gmt,link,title,excerpt"
FEEDS = {
    "alerta_publicado": BASE + "/categoria/alerta/feed/",
    "aviso_publicado": BASE + "/categoria/aviso/feed/",
    "previsao_publicada": BASE + "/categoria/boletins-para-os-proximos-5-dias/feed/",
}
PORTAL = BASE + "/boletins-do-tempo/"
ALERTAS = BASE + "/alerta/"
MUNICIPAL = "https://araquari.atende.net/subportal/secretaria-de-seguranca-publica-e-defesa-civil"
KIND = "defesa_civil_sc_publications_not_verified_active_alerts"
MAX_BYTES = 450_000


class CivilDefenseError(RuntimeError):
    """Unreliable or unavailable institutional publication source."""


class _Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._hidden = 0
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._hidden += 1
    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._hidden = max(self._hidden - 1, 0)
    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self.parts.append(data)


def _text(value: Any, limit: int = 320) -> str:
    parser = _Plain()
    parser.feed(value if isinstance(value, str) else "")
    return re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()[:limit]


def _safe_link(raw: Any) -> str | None:
    if not isinstance(raw, str) or len(raw) > 650:
        return None
    parsed = urlparse(raw)
    return raw if parsed.scheme == "https" and parsed.hostname in ("defesacivil.sc.gov.br", "www.defesacivil.sc.gov.br") and not parsed.username and not parsed.password else None


def _date(raw: str, *, rss: bool) -> datetime:
    try:
        result = parsedate_to_datetime(raw) if rss else datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError, IndexError) as exc:
        raise CivilDefenseError("Malformed publication timestamp") from exc
    if result.tzinfo is None:
        raise CivilDefenseError("Publication timestamp without timezone")
    return result.astimezone(timezone.utc)


def _classify_title(title: str) -> str:
    u = title.upper()
    if re.match(r"^(ALERTA|ATENÇÃO|ATENCAO|OBSERVAÇÃO|OBSERVACAO)\s*[–-]", u):
        return "alerta_publicado"
    if any(s in u for s in ("ATENÇÃO HIDROMETEOROLÓGICA", "OBSERVAÇÃO MARÍTIMA", "AVISO METEOROLÓGICO")):
        return "aviso_publicado"
    if any(s in u for s in ("PREVISÃO PARA OS PRÓXIMOS", "PREVISÃO DO TEMPO", "NOTA METEOROLÓGICA")):
        return "previsao_publicada"
    return "publicacao_geral"


def _fold(value: str) -> str:
    return "".join(c for c in normalize("NFKD", value.casefold()) if not ("\u0300" <= c <= "\u036f"))


def _row(title: str, summary: str, link: str, dt: datetime, category: str, locations: list[dict], now: datetime) -> dict | None:
    if not title or not link or dt < now - timedelta(days=21) or dt > now + timedelta(hours=6):
        return None
    haystack = _fold(title + " " + summary)
    # Explicit reference only. Missing mention != no risk; an excerpt may be incomplete.
    mentioned = [loc["id"] for loc in locations if _fold(loc["name"]) in haystack]
    return {
        "title": title, "summary": summary, "url": link, "published_at": dt.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "category": category, "mentioned_location_ids": mentioned,
        "geography_status": "explicit_mention_in_title_or_excerpt" if mentioned else "not_determined_from_excerpt",
        "validity_status": "not_verified_from_publication_date",
    }


def parse_wp_json(raw: bytes, locations: list[dict], now: datetime) -> list[dict]:
    if len(raw) > MAX_BYTES:
        raise CivilDefenseError("Excessive WordPress response")
    try:
        posts = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise CivilDefenseError("Invalid WordPress JSON") from exc
    if not isinstance(posts, list) or len(posts) > 100:
        raise CivilDefenseError("Unexpected WordPress response")
    results = []
    for post in posts:
        if not isinstance(post, dict):
            continue
        link = _safe_link(post.get("link"))
        if not link:
            continue
        title = _text(post.get("title", {}).get("rendered") if isinstance(post.get("title"), dict) else post.get("title"), 180)
        summary = _text(post.get("excerpt", {}).get("rendered") if isinstance(post.get("excerpt"), dict) else post.get("excerpt"), 380)
        try:
            dt = _date((post.get("date_gmt") or "") + "Z", rss=False)
        except CivilDefenseError:
            continue
        category = _classify_title(title)
        if category == "publicacao_geral":
            continue
        item = _row(title, summary, link, dt, category, locations, now)
        if item:
            results.append(item)
    return results


def parse_rss(raw: bytes, category: str, locations: list[dict], now: datetime) -> list[dict]:
    if len(raw) > MAX_BYTES or not raw or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise CivilDefenseError("Invalid RSS size/doctype")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise CivilDefenseError("Invalid RSS XML") from exc
    if root.tag.lower() != "rss":
        raise CivilDefenseError("Not a WordPress RSS feed")
    results = []
    for item in root.findall("./channel/item")[:40]:
        link = _safe_link(item.findtext("link"))
        if not link:
            continue
        try:
            dt = _date(item.findtext("pubDate"), rss=True)
        except CivilDefenseError:
            continue
        row = _row(_text(item.findtext("title"), 180), _text(item.findtext("description"), 380), link, dt, category, locations, now)
        if row:
            results.append(row)
    return results


def _download(url: str, *, timeout: int = 8) -> bytes:
    request = Request(url, headers={"Accept": "application/json,application/rss+xml,application/xml;q=0.9", "User-Agent": "criseclimatica-observatorio/0.3 (public meteorological bulletin catalog)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            if not _safe_link(response.geturl()):
                raise CivilDefenseError("Civil Defense source redirected outside official HTTPS domain")
            if response.status != 200:
                raise CivilDefenseError("Unexpected public website response")
            content = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise CivilDefenseError(f"Public bulletin unavailable: {type(exc).__name__}") from exc
    if len(content) > MAX_BYTES:
        raise CivilDefenseError("Public bulletin exceeded size limit")
    return content


def unavailable(checked_at: str, *, status: str = "unavailable") -> dict:
    return {
        "schema_version": 1, "kind": KIND, "status": status,
        "checked_at": checked_at, "source": {"id": "defesa-civil-sc", "name": "Defesa Civil de Santa Catarina", "url": PORTAL},
        "municipal_source": {"name": "Defesa Civil de Araquari", "url": MUNICIPAL, "integration": "official_contact_page_not_automatic_warning_feed"},
        "publications": [],
        "notice": "Publicacoes oficiais nao equivalem a alertas vigentes. Consulte sempre os canais da Defesa Civil.",
    }


def collect(locations: list[dict], checked_at: str, *, fixture: dict | None = None) -> dict:
    """Publications are best-effort; the absence of posts never proves no active alerts."""
    now = _date(checked_at, rss=False)
    records = []
    fetched_feeds = 0
    status = "unavailable"
    if fixture is not None:
        for category, raw in fixture.items():
            if category == "wp":
                records += parse_wp_json(raw.encode("utf-8"), locations, now)
            elif category in FEEDS:
                records += parse_rss(raw.encode("utf-8"), category, locations, now)
            else:
                raise ValueError("Unknown fixture source")
        fetched_feeds = len(fixture)
        status = "available"
    else:
        try:
            records = parse_wp_json(_download(WP_API), locations, now)
            fetched_feeds = 1
            status = "available"
        except (CivilDefenseError, ValueError):
            pass
        # The general WP feed may have only unrelated posts; still check
        # official category RSS if it has no recent meteorological entries.
        if not records:
            rss_ok = 0
            for category, url in FEEDS.items():
                try:
                    records += parse_rss(_download(url), category, locations, now)
                    rss_ok += 1
                except (CivilDefenseError, ValueError):
                    continue
            fetched_feeds += rss_ok
            if rss_ok:
                status = "available" if rss_ok == len(FEEDS) else "partial"
    if status == "unavailable":
        return unavailable(checked_at)
    # De-duplicate edits exposed by both feeds, deterministic newest-first.
    by_url = {r["url"]: r for r in sorted(records, key=lambda x: x["published_at"])}
    recent = sorted(by_url.values(), key=lambda x: (x["published_at"], x["url"]), reverse=True)[:35]
    response = unavailable(checked_at, status=status if recent else "no_recent_publications")
    response["publications"] = recent
    response["retrieval_method"] = "wp_json_or_public_rss"
    response["feeds_retrieved"] = fetched_feeds
    return response
