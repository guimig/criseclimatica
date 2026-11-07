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

    def test_both_epagri_datasets_are_read_in_boot_and_rendered_on_selection(self):
        script = (ROOT / 'web/app.js').read_text(encoding='utf-8')
        self.assertIn('data/epagri_geo.json', script)
        self.assertIn('data/epagri_notices.json', script)
        self.assertIn('renderEpagriStations();', script)
        self.assertIn('renderEpagriNotices();', script)
        self.assertIn('epagri_arcgis_station_registry_not_live_measurements', script)
        self.assertIn('epagri_ciram_official_advisories_not_civil_defense_alerts', script)
