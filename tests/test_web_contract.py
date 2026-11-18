"""Keep HTML/JavaScript and new public-data contracts synchronized."""
from __future__ import annotations
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class WebContract(unittest.TestCase):
    def test_every_dollar_dom_lookup_has_corresponding_html_id(self):
        script = (ROOT / 'web/app.js').read_text(encoding='utf-8')
        page = (ROOT / 'web/dados.html').read_text(encoding='utf-8')
        lookup_ids = set(re.findall(r"\$\(['\"]([a-zA-Z][\w-]*)['\"]\)", script))
        html_ids = set(re.findall(r'\bid="([^"]+)"', page))
        self.assertFalse(lookup_ids - html_ids, f'Missing HTML ids: {lookup_ids-html_ids}')

    def test_inmet_public_portal_and_technical_feed_are_distinct(self):
        home = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        details = (ROOT / 'web' / 'dados.html').read_text(encoding='utf-8')
        client = (ROOT / 'web' / 'dashboard.js').read_text(encoding='utf-8')
        detail_js = (ROOT / 'web' / 'app.js').read_text(encoding='utf-8')
        self.assertIn('https://avisos.inmet.gov.br/', details)
        self.assertIn('RSS/XML INMET · fonte técnica', details)
        self.assertIn('https://apiprevmet3.inmet.gov.br/avisos/rss', details)
        self.assertIn('Ler riscos e orientações do aviso', client)
        self.assertIn("const INMET_PUBLIC_PORTAL='https://avisos.inmet.gov.br/'", client)
        self.assertIn("'https://avisos.inmet.gov.br/'", detail_js)
        self.assertIn('dashboard.js?v=bordering-collapse-20261118', home)
        self.assertNotIn('href="https://alertas2.inmet.gov.br/', details)

    def test_telegram_group_link_on_both_headers(self):
        from html.parser import HTMLParser

        class HeaderLinks(HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_header = False
                self.telegram = []

            def handle_starttag(self, tag, attrs):
                if tag == 'header':
                    self.in_header = True
                if tag == 'a' and self.in_header:
                    attributes = dict(attrs)
                    if 'telegram-link' in attributes.get('class', '').split():
                        self.telegram.append(attributes)

            def handle_endtag(self, tag):
                if tag == 'header':
                    self.in_header = False

        for filename in ('index.html', 'dados.html'):
            with self.subTest(page=filename):
                parser = HeaderLinks()
                parser.feed((ROOT / 'web' / filename).read_text(encoding='utf-8'))
                self.assertEqual(len(parser.telegram), 1)
                link = parser.telegram[0]
                self.assertEqual(link.get('href'), 'https://t.me/+8gSPhMQrAUU2NWYx')
                self.assertEqual(link.get('target'), '_blank')
                self.assertEqual(set(link.get('rel', '').split()), {'noopener', 'noreferrer'})
                self.assertIn('Telegram', link.get('aria-label', ''))

    def test_both_epagri_datasets_are_read_in_boot_and_rendered_on_selection(self):
        script = (ROOT / 'web/app.js').read_text(encoding='utf-8')
        self.assertIn('data/epagri_geo.json', script)
        self.assertIn('data/epagri_notices.json', script)
        self.assertIn('renderEpagriStations();', script)
        self.assertIn('renderEpagriNotices();', script)
        self.assertIn('epagri_arcgis_station_registry_not_live_measurements', script)
        self.assertIn('epagri_ciram_official_advisories_not_civil_defense_alerts', script)
