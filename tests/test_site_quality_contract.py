"""Deployment contracts for regional gauge quality and Epagri editorial forecasts."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_site import build
from validate_site import validate


class QualityDeploymentTests(unittest.TestCase):
    def test_offline_build_has_both_new_attributed_datasets(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'site'
            build(target,fixture=ROOT/'tests/fixtures/open_meteo.json')
            quality=json.loads((target/'data/regional_quality.json').read_text())
            bulletins=json.loads((target/'data/epagri_bulletins.json').read_text())
            self.assertEqual(quality['status'],'unavailable')
            self.assertEqual(quality['kind'],'regional_gauge_coverage_and_spatial_model_context_not_live_alert')
            self.assertTrue(all(x['selected_station'] is None for x in quality['locations']))
            self.assertEqual(bulletins['status'],'available')
            self.assertEqual(bulletins['kind'],'epagri_ciram_editorial_forecast_bulletins_not_emergency_alerts')
            validate(target,fixture=True)

    def test_site_validation_rejects_fictional_observed_rain(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'site'
            build(target,fixture=ROOT/'tests/fixtures/open_meteo.json')
            file=target/'data/regional_quality.json'
            data=json.loads(file.read_text())
            data['locations'][0]['status']='available'
            data['locations'][0]['selected_station']={'code':'A851','last_complete_rain_mm':None}
            file.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'complete dated measurement'):
                validate(target,fixture=True)

    def test_site_validation_rejects_editorial_as_emergency_alert(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'site'
            build(target,fixture=ROOT/'tests/fixtures/open_meteo.json')
            file=target/'data/epagri_bulletins.json'
            data=json.loads(file.read_text())
            data['bulletins'][0]['data_kind']='active_defesa_civil_alert'
            file.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'mislabeled'):
                validate(target,fixture=True)

    def test_web_new_sources_loaded_and_rendered_on_municipal_changes(self):
        js=(ROOT/'web/app.js').read_text()
        html=(ROOT/'web/dados.html').read_text()
        for src in ('regional_quality.json','epagri_bulletins.json'):
            self.assertIn(src,js)
        for function in ('renderRegionalQuality();','renderEpagriBulletins();'):
            self.assertIn(function,js)
        for dom_id in ('regional-quality-data','epagri-bulletins-list','regional-quality-foot','epagri-bulletins-updated'):
            self.assertIn(f'id="{dom_id}"',html)

if __name__=='__main__':unittest.main()
