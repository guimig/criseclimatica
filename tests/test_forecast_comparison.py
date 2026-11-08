import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from observatorio.forecast_comparison import (MODELS, FIELDS, ARCHIVE_KIND, collect, normalize, summarize, merge_archive)

STAMP='2026-11-07T12:15:00Z'
START=datetime(2026,11,7,12,tzinfo=timezone.utc)
LOCATION={'id':'araquari','latitude':-26.37,'longitude':-48.72}
def iso(t):return t.isoformat().replace('+00:00','Z')
def source(model='ecmwf_ifs025',rain=1):
    return {'id':model,'name':MODELS.get(model,model),'status':'available','collected_at':STAMP,
            'hourly':[{'time':iso(START+timedelta(hours=i)),'precipitation_mm':rain,'temperature_c':25,'wind_kmh':15,'gust_kmh':30} for i in range(169)]}
def detail():
    return {**source('best_match'), 'location':LOCATION,'current':{'time':iso(START)}}

class ComparisonTests(unittest.TestCase):
    def test_comparison_never_outlives_its_oldest_available_model(self):
        old=source();old['collected_at']=iso(START-timedelta(hours=7))
        result=summarize(detail(),[old],{},STAMP)
        self.assertEqual(result['valid_until'],iso(START+timedelta(hours=1)))

    def test_old_primary_reference_also_limits_comparison(self):
        d=detail();d['current']['time']=iso(START-timedelta(hours=7))
        result=summarize(d,[source()],{},STAMP)
        self.assertEqual(result['valid_until'],iso(START+timedelta(hours=1)))

    def test_unavailable_model_does_not_shorten_remaining_comparison(self):
        old=source();old['collected_at']=iso(START-timedelta(hours=10))
        result=summarize(detail(),[old],{},STAMP)
        self.assertEqual(result['valid_until'],iso(datetime.fromisoformat(STAMP.replace('Z','+00:00'))+timedelta(hours=3)))

    def test_unavailable_primary_collection_does_not_expire_other_models(self):
        d=detail();d['collected_at']=iso(START-timedelta(hours=10));d['current']['time']=iso(START-timedelta(hours=7))
        result=summarize(d,[source(),source('ncep_gfs_global')],{},STAMP)
        self.assertEqual(result['records'][0]['status'],'unavailable')
        self.assertEqual(result['valid_until'],iso(datetime.fromisoformat(STAMP.replace('Z','+00:00'))+timedelta(hours=3)))

    def test_co_timed_ranges_preserve_extremes_no_mean(self):
        r=summarize(detail(),[source(rain=3),source('ncep_gfs_global',5)],{},STAMP)
        rain=r['windows'][0]['metrics'][0]
        self.assertEqual((rain['minimum'],rain['maximum'],rain['spread']),(24,120,96))
        self.assertEqual(rain['highest_sources'],['ncep_gfs_global'])
        self.assertNotIn('mean',rain)
        self.assertEqual(r['primary_id'],'best_match')

    def test_incomplete_and_conflicting_duplicates_are_excluded(self):
        a=source();a['hourly'].pop(5)
        b=source('ncep_gfs_global');b['hourly'].append({**b['hourly'][8],'precipitation_mm':99})
        r=summarize(detail(),[a,b],{},STAMP)['windows'][0]['metrics'][0]
        self.assertEqual(r['status'],'insufficient_sources')
        self.assertIsNone(r['minimum'])
        self.assertEqual([v['value'] for v in r['members']],[24,None,None])

    def test_identical_duplicates_do_not_increase_totals(self):
        a=source();a['hourly']+=copy.deepcopy(a['hourly'])
        r=summarize(detail(),[a],{},STAMP)
        self.assertEqual(r['windows'][0]['metrics'][0]['members'][1]['value'],24)

    def test_rain_uses_preceding_intervals_not_instantaneous_window(self):
        d=detail();d['hourly'][0]['precipitation_mm']=99;d['hourly'][24]['precipitation_mm']=3
        d['hourly'][24]['temperature_c']=60
        r=summarize(d,[],{},STAMP)['windows'][0]['metrics']
        self.assertEqual(r[0]['members'][0]['value'],26)
        self.assertEqual(r[1]['members'][0]['value'],25)

    def test_stale_missing_invalid_and_partial_variables(self):
        a=source();a['collected_at']='2026-11-06T12:00:00Z'
        b=source('ncep_gfs_global');b['hourly'][2]['gust_kmh']=float('nan')
        r=summarize({},[a,b],{},STAMP)['windows'][0]['metrics']
        self.assertEqual(r[0]['status'],'insufficient_sources')
        self.assertIsNone(r[3]['members'][2]['value'])
        self.assertEqual(r[0]['members'][2]['value'],24)

    def test_cptec_remains_separate_even_when_fresh(self):
        cp={'checked_at':STAMP,'locations':[{'location_id':'araquari','status':'available','days':[{'day':'2026-11-07','maximum_c':45}]}]}
        r=summarize(detail(),[source()],cp,STAMP)
        self.assertEqual(r['cptec']['status'],'available')
        self.assertFalse(r['cptec']['numeric_comparison'])
        self.assertEqual(len(r['windows'][0]['metrics'][0]['members']),2)

    def test_model_normalization_units_bounds_time_grid(self):
        payload={'utc_offset_seconds':0,'latitude':-26.4,'longitude':-48.7,'hourly':{'time':['2026-11-07T13:00']},'hourly_units':{}}
        for field,(key,unit,lo,hi) in FIELDS.items():payload['hourly'][key]=[1];payload['hourly_units'][key]=unit
        normalized=normalize(payload,'ecmwf_ifs025',LOCATION,STAMP)
        self.assertEqual(normalized['hourly'][0]['time'],'2026-11-07T13:00:00Z')
        for change in ['unit','timezone','length','timestamp','grid','structure']:
            p=copy.deepcopy(payload)
            if change=='unit':p['hourly_units']['precipitation']='inch'
            if change=='timezone':p['utc_offset_seconds']=3600
            if change=='length':p['hourly']['precipitation']=[]
            if change=='timestamp':p['hourly']['time']=['2026-11-07T13:30']
            if change=='grid':p['latitude']=None
            if change=='structure':p['hourly']=[]
            with self.subTest(change=change),self.assertRaises(ValueError):normalize(p,'ecmwf_ifs025',LOCATION,STAMP)

    @patch('observatorio.forecast_comparison.urlopen',side_effect=TimeoutError)
    def test_failures_are_isolated_and_fixture_never_queries(self,request):
        rows=collect(LOCATION,STAMP)
        self.assertEqual([r['status'] for r in rows],['unavailable','unavailable'])
        self.assertEqual(request.call_count,2)
        request.reset_mock();collect(LOCATION,STAMP,fixture=True);request.assert_not_called()

    def test_archive_idempotent_future_only_and_fail_closed(self):
        c=summarize(detail(),[source()],{},STAMP)
        a=merge_archive(None,c);b=merge_archive(a,c)
        self.assertEqual(a,b)
        self.assertEqual(len(a['publications']),1)
        for r in a['publications'][0]['records']:
            self.assertTrue(all(datetime.fromisoformat(p['time'].replace('Z','+00:00'))-timedelta(hours=1)>datetime.fromisoformat(STAMP.replace('Z','+00:00')) for p in r['hourly']))
        with self.assertRaises(ValueError):merge_archive({'kind':'wrong'},c)
        a['publications'][0]['saved_at']='2026-10-01T00:00:00Z'
        self.assertEqual(len(merge_archive(a,c)['publications']),1)

if __name__=='__main__':unittest.main()
