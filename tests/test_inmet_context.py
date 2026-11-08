"""Regional notices are visible context, independent of the classifier."""
import unittest
from copy import deepcopy
from test_multisource_analysis import NOW, STAMP, PLACE, primary, detail, epagri
from observatorio.analysis import notice_analysis
from observatorio.dashboard import regional_notice_context
from observatorio.objective_analysis import summarize, integrate
from observatorio.protocol import assess


class InmetContextTests(unittest.TestCase):
    def test_notices_and_failed_feed_do_not_change_numeric_coverage_or_state(self):
        baseline = summarize(primary(), detail(), epagri(), STAMP)
        for status, notices in [('available', [{'id': '1', 'severity': 'Grande perigo'}]), ('unavailable', [])]:
            p = primary()
            p['official_notices'] = {'status': status, 'notices': notices}
            result = summarize(p, detail(), epagri(), STAMP)
            for key in ['core_complete', 'coverage_gaps', 'proposed_level', 'maximum_band', 'signals']:
                self.assertEqual(result[key], baseline[key])
            self.assertEqual(integrate(assess(epagri(), {}, STAMP), result)['monitoring_state'], 'routine')

    def test_notice_details_survive_analysis_without_available_forecast(self):
        raw = {'id': '1', 'type': 'Tempestade', 'risks': ['Granizo'], 'instructions': ['Proteja-se'],
               'start_at': '2026-11-07T10:00:00Z', 'end_at': '2026-11-08T10:00:00Z'}
        feed = {'status': 'available', 'retrieved_at': STAMP,
                'locations': [{'location_id': 'araquari', 'ibge_code': '4201307', 'alerts': [raw]}]}
        result = notice_analysis(feed, 'araquari', {'status': 'unavailable'}, NOW)['notices'][0]
        self.assertEqual(result['risks'], ['Granizo'])
        self.assertEqual(result['instructions'], ['Proteja-se'])
        self.assertEqual(result['ibge_code'], '4201307')
        self.assertEqual(result['temporal_relation'], 'forecast_unavailable')

    def test_region_deduplicates_and_excludes_distant_expired_stale_or_unknown_points(self):
        n = {'id': '1', 'type': 'Chuva', 'lifecycle': 'unverified', 'ibge_code': '4201307'}
        places = []
        details = {}
        for slug, lat in [('araquari', -26.375), ('joinville', -26.3044), ('far', -28), ('unknown', None), ('stale', -26.4)]:
            feed = {'status': 'available', 'retrieved_at': STAMP,
                    'notices': [deepcopy(n), {**n, 'id': 'expired', 'lifecycle': 'expired'}]}
            if slug == 'stale': feed['retrieved_at'] = '2026-11-06T00:00:00Z'
            places.append({'location_id': slug, 'name': slug, 'official_notices': feed})
            details[slug] = {'location': {**PLACE, 'latitude': lat}}
        result = regional_notice_context({'locations': places}, details, STAMP)
        self.assertEqual(len(result['notices']), 1)
        self.assertEqual([m['location_id'] for m in result['notices'][0]['municipalities']], ['araquari', 'joinville'])
        self.assertEqual(result['role'], 'context_only_not_classification')
        self.assertEqual(regional_notice_context({'locations': []}, {}, STAMP)['status'], 'unavailable')
