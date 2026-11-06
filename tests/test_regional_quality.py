"""Real observed archives and NASA model estimates must never be conflated."""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from observatorio.regional_quality import KIND, summarize
from observatorio.inmet_archive import KIND as INMET_KIND
from observatorio.nasa_power import KIND as NASA_KIND

STAMP = '2026-11-06T12:00:00Z'
PLACES = [{'id': 'araquari', 'name': 'Araquari', 'latitude': -26.375, 'longitude': -48.721},
          {'id': 'itapoa', 'name': 'Itapoa', 'latitude': -26.1156, 'longitude': -48.618}]


def archive(*, valid=True):
    current = date(2026, 10, 31)
    return {
        'schema_version': 1, 'kind': INMET_KIND, 'status': 'available',
        'stations': [
            {'code':'A851','name':'ITAPOA','days':[{'day_utc':(current - timedelta(days=i)).isoformat(),
                'rain_total_complete_mm': None, 'rain_measured_hours': 0} for i in range(14)]},
            {'code':'A868','name':'ITAJAI','days':[{'day_utc':(current - timedelta(days=i)).isoformat(),
                'rain_total_complete_mm': float(i+1), 'rain_measured_hours':24} for i in range(14)]},
        ] if valid else [],
        'locations': [
            {'location_id':'araquari','stations':[{'code':'A851','distance_km':33.6}, {'code':'A868','distance_km':64.2}]},
            {'location_id':'itapoa','stations':[{'code':'A851','distance_km':4.3}, {'code':'A868','distance_km':91.1}]},
        ],
    }


def nasa():
    return {'kind':NASA_KIND, 'status':'available', 'point':{'location_id':'araquari'},
            'daily':[{'date_utc':'2026-10-31','rain_estimated_mm_day':4.9}]}


def geo():
    return {'locations':[{'location_id':'araquari','stations':[
        {'distance_km':16}, {'distance_km':28}, {'distance_km':67}]}]}


class RegionalQualityTests(unittest.TestCase):
    def test_nearest_station_without_rain_is_not_assigned_zero(self):
        result = summarize(PLACES, archive(), nasa(), geo(), STAMP)
        self.assertEqual(result['kind'], KIND)
        self.assertEqual(result['status'], 'available')
        araquari = result['locations'][0]
        self.assertEqual(araquari['selected_station']['code'],'A868')
        self.assertEqual(araquari['selected_station']['distance_km'],64.2)
        self.assertTrue(araquari['nearest_station_missing_rain'])
        self.assertEqual(araquari['station_candidates'][0]['code'], 'A851')
        self.assertIsNone(araquari['station_candidates'][0]['last_complete_rain_mm'])
        self.assertEqual(araquari['epagri_catalog_within_30km'],2)

    def test_only_seven_complete_consecutive_days_have_total(self):
        result = summarize(PLACES, archive(), nasa(), geo(), STAMP)
        s=result['locations'][0]['selected_station']
        self.assertEqual(s['total_7_complete_days_mm'], 28.0)
        data=archive()
        data['stations'][1]['days'][3]['rain_measured_hours']=23
        data['stations'][1]['days'][3]['rain_total_complete_mm']=4000
        res=summarize(PLACES,data,nasa(),geo(),STAMP)
        self.assertIsNone(res['locations'][0]['selected_station']['total_7_complete_days_mm'])

    def test_cannot_claim_a_municipal_observation_or_accuracy(self):
        x=summarize(PLACES,archive(),nasa(),geo(),STAMP)
        pair=x['locations'][0]['spatial_comparison']
        self.assertEqual(pair['day_utc'],'2026-10-31')
        self.assertEqual(pair['inmet_station_measurement_mm'],1)
        self.assertEqual(pair['nasa_gridded_estimate_mm'],4.9)
        self.assertIn('NAO demonstra erro',pair['note'])
        self.assertIsNone(x['locations'][1]['spatial_comparison'])
        self.assertFalse(x['locations'][0]['epagri_catalog_is_measurement'])

    def test_incomplete_and_missing_station_data_never_becomes_zero(self):
        data=archive()
        data['stations'][1]['days']=[{'day_utc':'2026-10-31','rain_measured_hours':24,'rain_total_complete_mm':None}]
        x=summarize(PLACES,data,{},None,STAMP)
        self.assertEqual(x['status'],'no_complete_gauge_data')
        self.assertEqual(x['locations'][0]['status'],'no_complete_gauge_data')
        self.assertIsNone(x['locations'][0]['selected_station'])

    def test_stale_future_and_non_finite_values_rejected(self):
        data=archive()
        for s in data['stations']:
            s['days']=[{'day_utc':'2026-11-30','rain_measured_hours':24,'rain_total_complete_mm':5.5},
                       {'day_utc':'2026-09-01','rain_measured_hours':24,'rain_total_complete_mm':3.0},
                       {'day_utc':'2026-10-31','rain_measured_hours':24,'rain_total_complete_mm':float('nan')}]
        x=summarize(PLACES,data,nasa(),geo(),STAMP)
        self.assertIsNone(x['locations'][0]['selected_station'])

    def test_different_source_and_no_registry_are_unavailable(self):
        x=summarize(PLACES, {'kind':'forecast'}, nasa(), {}, STAMP)
        self.assertEqual(x['status'],'unavailable')
        self.assertIsNone(x['locations'][0]['selected_station'])
        self.assertFalse(x['locations'][0]['nearest_station_missing_rain'])

    def test_repeated_calls_are_deterministic(self):
        self.assertEqual(summarize(PLACES,archive(),nasa(),geo(),STAMP),
                         summarize(PLACES,archive(),nasa(),geo(),STAMP))

    def test_invalid_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            summarize(PLACES,archive(),nasa(),geo(),'2026-11-06T12:00:00')


if __name__=='__main__':
    unittest.main()
