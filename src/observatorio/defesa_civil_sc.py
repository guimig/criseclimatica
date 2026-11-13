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
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from unicodedata import normalize
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

BASE = "https://www.defesacivil.sc.gov.br"
WP_API = BASE + "/wp-json/wp/v2/posts?per_page=20&_fields=date,date_gmt,link,title,excerpt,content"
FEEDS = {
    "alerta_publicado": BASE + "/categoria/alerta/feed/",
    "aviso_publicado": BASE + "/categoria/aviso/feed/",
    "previsao_publicada": BASE + "/categoria/boletins-para-os-proximos-5-dias/feed/",
}
PORTAL = BASE + "/boletins-do-tempo/"
ALERTAS = BASE + "/alerta/"
MUNICIPAL = "https://araquari.atende.net/subportal/secretaria-de-seguranca-publica-e-defesa-civil"
KIND = "defesa_civil_sc_publications_not_verified_active_alerts"
MAX_BYTES = 750_000
REQUEST_TIMEOUT = 20
COLLECT_BUDGET_SECONDS = 70
MAX_PAGE_BYTES = 1_300_000


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
    u = _fold(title).upper()
    if re.match(r"^(ALERTA|ATENCAO|OBSERVACAO)\s*[–—-]", u):
        return "alerta_publicado"
    if u.startswith("MONITORAMENTO METEOROLOGICO"):
        return "monitoramento_publicado"
    if u.startswith(("OBSERVACAO METEOROLOGICA", "ALERTA METEOROLOGICO")):
        return "aviso_publicado"
    if any(s in u for s in ("ATENCAO HIDROMETEOROLOGICA", "OBSERVACAO MARITIMA", "AVISO METEOROLOGICO", "AVISO HIDROMETEOROLOGICO")):
        return "aviso_publicado"
    if any(s in u for s in ("PREVISAO PARA OS PROXIMOS", "PREVISAO DO TEMPO", "NOTA METEOROLOGICA")):
        return "previsao_publicada"
    return "publicacao_geral"


def _fold(value: str) -> str:
    return "".join(c for c in normalize("NFKD", value.casefold()) if not ("\u0300" <= c <= "\u036f"))


def _row(title: str, summary: str, link: str, dt: datetime, category: str, locations: list[dict], now: datetime) -> dict | None:
    if not title or not link or dt < now - timedelta(days=21) or dt > now + timedelta(hours=6):
        return None
    haystack = _fold(title + " " + summary)
    # Explicit reference only. Missing mention != no risk; an excerpt may be incomplete.
    mentioned = [loc["id"] for loc in locations if re.search(r"\b"+re.escape(_fold(loc["name"]))+r"\b",haystack)]
    return {
        "title": title, "summary": summary, "url": link, "published_at": dt.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "category": category, "mentioned_location_ids": mentioned,
        "geography_status": "explicit_mention_in_title_or_excerpt" if mentioned else "not_determined_from_excerpt",
        "validity_status": "not_verified_from_publication_date",
    }



class _BodyPlain(_Plain):
    def handle_starttag(self,tag,attrs):
        super().handle_starttag(tag,attrs)
        if tag in ('p','div','br','li','h2','h3','h4'):self.parts.append('\n')
    def handle_endtag(self,tag):
        super().handle_endtag(tag)
        if tag in ('p','div','li','h2','h3','h4'):self.parts.append('\n')


def _body_text(raw):
    parser=_BodyPlain();parser.feed(raw if isinstance(raw,str) else '')
    return re.sub(r'[ \t]+',' ',html.unescape(''.join(parser.parts))).strip()[:12000]


def event_window(post):
    """Explicit alert title clock plus explicit duration; never pubDate alone."""
    title=_fold(post.get('title',''));text=_fold(post.get('assessment_text') or post.get('summary',''))
    match=re.match(r'^(?:alerta|atencao|observacao)\s*[–—-]\s*(\d{2})/(\d{2})\s+(\d{1,2})[:h](\d{2})',title)
    hours={int(h) for h in re.findall(r'nas proximas\s+(\d{1,2})\s*horas?',title+' '+text)}
    if not match or len(hours)!=1 or not 1<=next(iter(hours))<=24:return None
    try:
        published=_date(post.get('published_at'),rss=False)
        local=published.astimezone(ZoneInfo('America/Sao_Paulo'))
        day,month,hour,minute=map(int,match.groups());year=local.year
        if local.month==1 and month==12:year-=1
        if local.month==12 and month==1:year+=1
        start=datetime(year,month,day,hour,minute,tzinfo=ZoneInfo('America/Sao_Paulo')).astimezone(timezone.utc)
    except (CivilDefenseError,ValueError,TypeError):return None
    if not -timedelta(minutes=10)<=published-start<=timedelta(hours=6):return None
    end=start+timedelta(hours=next(iter(hours)))
    return {'start_at':start.isoformat(timespec='seconds').replace('+00:00','Z'),
            'end_at':end.isoformat(timespec='seconds').replace('+00:00','Z'),
            'basis':'explicit_title_clock_and_reported_duration','duration_hours':next(iter(hours))}


def _enrich(row,body,locations,origin):
    if body:
        row.update(assessment_text=body,text_origin=origin)
        combined=_fold(row['title']+' '+body)
        row['mentioned_location_ids']=[loc['id'] for loc in locations
            if re.search(r'\b'+re.escape(_fold(loc['name']))+r'\b',combined)]
        if row['mentioned_location_ids']:row['geography_status']='explicit_mention_in_full_text'
        regions=[]
        if re.search(r'\blitoral norte\b',combined):regions.append('litoral_norte')
        if re.search(r'em santa catarina|todo o estado|todas as regioes|maior parte de santa catarina',combined):regions.append('state_context_not_municipal_confirmation')
        row['regional_references']=regions
    window=event_window(row)
    if window:row['event_window']=window
    return row


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
            # date_gmt is UTC. WordPress `date` is the local site timezone;
            # interpreting it as UTC silently shifts warning publication time.
            if post.get("date_gmt"):
                raw_date=str(post["date_gmt"])
                dt = _date(raw_date if raw_date.endswith(("Z","+00:00")) else raw_date+"Z", rss=False)
            else:
                local = datetime.fromisoformat(str(post.get("date") or ""))
                dt = (local if local.tzinfo else local.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))).astimezone(timezone.utc)
        except (CivilDefenseError, ValueError, TypeError):
            continue
        category = _classify_title(title)
        if category == "publicacao_geral":
            continue
        item = _row(title, summary, link, dt, category, locations, now)
        if item:
            raw_body=post.get('content',{})
            body=_body_text(raw_body.get('rendered') if isinstance(raw_body,dict) else raw_body)
            results.append(_enrich(item,body,locations,'wordpress_content'))
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
            content=item.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or ''
            results.append(_enrich(row,_body_text(content),locations,'rss_full_content'))
    return results


class _PublicPageLinks(HTMLParser):
    """Only h2/h3 headlines linking to dated posts on the official HTTPS portal."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heading = None
        self.url = None
        self.words = []
        self.entries = []

    def handle_starttag(self, tag, attrs):
        if tag in ("h2", "h3"):
            self.heading = tag
        if tag == "a" and self.heading is not None:
            url = dict(attrs).get("href")
            if _safe_link(url) and re.search(r"/20\d{2}/\d{2}/\d{2}/", url):
                self.url = url
                self.words = []

    def handle_data(self, data):
        if self.url is not None:
            self.words.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.url is not None:
            self.entries.append((self.url, " ".join(self.words)))
            self.url = None
            self.words = []
        if tag == self.heading:
            self.heading = None


def parse_public_page(raw: bytes, locations: list[dict], now: datetime) -> list[dict]:
    """Fallback to the official public listing, never claiming exact alert validity.

    Date extracted from the post URL is only a calendar day, not its timestamp.
    """
    if not raw or len(raw) > MAX_PAGE_BYTES:
        raise CivilDefenseError("Public listing has invalid size")
    page = _PublicPageLinks()
    try:
        page.feed(raw.decode("utf-8"))
    except UnicodeError as exc:
        raise CivilDefenseError("Public listing is not UTF-8") from exc
    results = []
    for url, text in page.entries[:100]:
        title = _text(text, 180)
        category = _classify_title(title)
        if category == "publicacao_geral":
            continue
        date_match = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", url)
        if not date_match:
            continue
        try:
            day = datetime(int(date_match[1]), int(date_match[2]), int(date_match[3]), tzinfo=timezone.utc)
        except ValueError:
            continue
        row = _row(title, "", url, day, category, locations, now)
        if row:
            row["publication_precision"] = "calendar_day_from_url_not_exact_time"
            results.append(row)
    return results


def _download(url: str, *, timeout: int = REQUEST_TIMEOUT, limit: int = MAX_BYTES) -> bytes:
    request = Request(url, headers={"Accept": "application/json,application/rss+xml,application/xml;q=0.9", "User-Agent": "criseclimatica-observatorio/0.3 (public meteorological bulletin catalog)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            if not _safe_link(response.geturl()):
                raise CivilDefenseError("Civil Defense source redirected outside official HTTPS domain")
            if response.status != 200:
                raise CivilDefenseError("Unexpected public website response")
            content = response.read(limit + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        # Keep only status category, never session tokens or full URLs.
        reason=getattr(exc,'reason',exc)
        category = (f"http_{exc.code}" if isinstance(exc, HTTPError) else
                    'tls_certificate' if isinstance(reason,ssl.SSLCertVerificationError) else
                    'tls_connection' if isinstance(reason,ssl.SSLError) else
                    'dns' if isinstance(reason,socket.gaierror) else
                    'timeout' if isinstance(reason,TimeoutError) else
                    'connection' if isinstance(reason,ConnectionError) else type(exc).__name__)
        raise CivilDefenseError(f"Public bulletin unavailable: {category}") from exc
    if len(content) > limit:
        raise CivilDefenseError("Public bulletin exceeded size limit")
    return content


def unavailable(checked_at: str, *, status: str = "unavailable") -> dict:
    return {
        "schema_version": 1, "kind": KIND, "status": status,
        "checked_at": checked_at, "source": {"id": "defesa-civil-sc", "name": "Defesa Civil de Santa Catarina", "url": PORTAL},
        "municipal_source": {"name": "Defesa Civil de Araquari", "url": MUNICIPAL, "integration": "official_contact_page_not_automatic_warning_feed"},
        "publications": [],
        "notice": "Publicacoes oficiais nao equivalem a alertas vigentes. Consulte sempre os canais da Defesa Civil.",
        "retrieval_method": "none", "last_successful_check": None,
        "request_timeout_seconds":REQUEST_TIMEOUT,"collection_budget_seconds":COLLECT_BUDGET_SECONDS,
    }


def _prior_publications(previous: Any, now: datetime) -> list[dict]:
    """Validate last publication before reusing it with an explicit STALE label."""
    if (not isinstance(previous, dict) or previous.get("schema_version") != 1 or
            previous.get("kind") != KIND or previous.get("status") not in
            ("available", "partial", "no_recent_publications", "stale")):
        return []
    posts = previous.get("publications")
    if not isinstance(posts, list) or len(posts) > 35:
        return []
    safe = []
    for post in posts:
        if not isinstance(post, dict) or post.get("validity_status") != "not_verified_from_publication_date" or not _safe_link(post.get("url")):
            continue
        try:
            moment = _date(post.get("published_at"), rss=False)
        except CivilDefenseError:
            continue
        if now - timedelta(days=21) <= moment <= now + timedelta(hours=6):
            safe.append(post)
    return safe


def collect(locations: list[dict], checked_at: str, *, fixture: dict | None = None,
            previous: dict | None = None) -> dict:
    """Publications are best-effort; a source failure never proves no active alert."""
    now = _date(checked_at, rss=False)
    deadline=time.monotonic()+COLLECT_BUDGET_SECONDS
    def download(url,*,limit=MAX_BYTES):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise CivilDefenseError('Public bulletin unavailable: collection_budget')
        return _download(url,timeout=min(REQUEST_TIMEOUT,remaining),limit=limit)
    records: list[dict] = []
    fetched_feeds = 0
    status = "unavailable"
    errors: list[str] = []
    retrieval_method = "none"
    if fixture is not None:
        for category, raw in fixture.items():
            if category == "wp":
                records += parse_wp_json(raw.encode("utf-8"), locations, now)
            elif category in FEEDS:
                records += parse_rss(raw.encode("utf-8"), category, locations, now)
            elif category == "public_page":
                records += parse_public_page(raw.encode("utf-8"), locations, now)
            else:
                raise ValueError("Unknown fixture source")
        fetched_feeds = len(fixture)
        status = "available"
        retrieval_method = "synthetic_fixture"
    else:
        try:
            records = parse_wp_json(download(WP_API), locations, now)
            fetched_feeds = 1
            status = "available"
            retrieval_method = "wordpress_json"
        except (CivilDefenseError, ValueError) as exc:
            errors.append(f"wp:{type(exc).__name__}:{str(exc)[:45]}")
        if not records:
            def read_feed(item):
                category,url=item
                try:return parse_rss(download(url),category,locations,now),None
                except (CivilDefenseError,ValueError) as exc:
                    return [],f"rss:{category}:{type(exc).__name__}:{str(exc)[:45]}"
            with ThreadPoolExecutor(max_workers=3) as pool:
                feed_results=list(pool.map(read_feed,FEEDS.items()))
            rss_ok=0
            for rows,error in feed_results:
                if error:errors.append(error)
                else:rss_ok+=1;records+=rows
            fetched_feeds += rss_ok
            if rss_ok:
                status = "available" if rss_ok == len(FEEDS) else "partial"
                retrieval_method = "official_category_rss"
        if not records:
            # The dedicated alert listing precedes the general bulletin portal.
            for page in (ALERTAS,PORTAL):
                try:
                    records=parse_public_page(download(page,limit=MAX_PAGE_BYTES),locations,now)
                    fetched_feeds+=1
                    if records:
                        status='partial';retrieval_method='official_public_html_titles';break
                except (CivilDefenseError,ValueError) as exc:
                    errors.append(f"listing:{type(exc).__name__}:{str(exc)[:45]}")
    if status == "unavailable":
        response = unavailable(checked_at)
        response["source_diagnostics"] = errors[:7]
        prior = _prior_publications(previous, now)
        if prior:
            response["status"] = "stale"
            response["publications"] = prior
            response["retrieval_method"] = "previously_published_publications"
            response["last_successful_check"] = previous.get("last_successful_check") or previous.get("checked_at")
        return response
    by_url = {r["url"]: r for r in sorted(records, key=lambda x: x["published_at"])}
    recent = sorted(by_url.values(), key=lambda x: (x["published_at"], x["url"]), reverse=True)[:35]
    if fixture is None:
        from .publication_text import extract
        for post in [p for p in recent if not p.get('assessment_text')][:2]:
            try:
                body=extract(download(post['url'],limit=MAX_PAGE_BYTES))
                _enrich(post,body,locations,'official_article_body')
            except (CivilDefenseError,UnicodeError,ValueError):
                post['text_origin']='excerpt_article_unavailable'
    response = unavailable(checked_at, status=status if recent else "no_recent_publications")
    response["publications"] = recent
    response["retrieval_method"] = retrieval_method
    response["last_successful_check"] = checked_at
    response["feeds_retrieved"] = fetched_feeds
    response["source_diagnostics"] = errors[:7]
    return response
