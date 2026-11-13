"""Source failures, different products, geography and positive evidence."""
import sys
import io
from unittest.mock import patch
from urllib.error import HTTPError
import unittest
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from test_forecast_contingency import NOW, STAMP, model, dashboard, context
from observatorio.analysis import iso
from observatorio.multisource import build, evidence
from observatorio.source_evidence import (model_evidence,cptec_days,publication_evidence,antecedent_rain,
                                          regional_inmet_rain,sensor_inventory)
from observatorio.risk_classification import classify,history_snapshot
from observatorio.inmet_periods import assess
from observatorio.publication_text import extract


def cptec(code='t',locality='Araquari'):
    return {'cptec':{'status':'available','checked_at':STAMP,'locality':locality,'updated_day':'2026-11-13',
                    'days':[{'day':'2026-11-13','minimum_c':19,'maximum_c':27,'condition_code':code},
                            {'day':'2026-11-14','minimum_c':18,'maximum_c':28,'condition_code':code}]}}


def bulletin(text,source='Epagri/Ciram'):
    row={'title':'Previsão regional','summary':text,'assessment_text':text,'published_at':iso(NOW-timedelta(minutes=5)),
         'url':'https://ciram.epagri.sc.gov.br/index.php/2026/11/13/previsao/'}
    if source=='Epagri/Ciram':return {'status':'available','retrieved_at':STAMP,'bulletins':[row]}
    row['url']='https://www.defesacivil.sc.gov.br/2026/11/13/aviso/'
    return {'status':'available','last_successful_check':STAMP,'publications':[row]}


class SourceEvidenceTests(unittest.TestCase):
    def test_other_model_attention_is_not_hidden_by_calm_selected_product(self):
        calm=model(NOW);storm=model(NOW,'ecmwf_ifs025');storm['hourly'][3]['gust_kmh']=70
        d=dashboard();d['assessment']={};s,h,detail=build(d,{}, {}, {}, {'records':[calm,storm]}, {}, {},STAMP)
        d['synthesis']=s;r=classify(d,detail,STAMP)
        self.assertEqual(s['selected_forecast']['sources_by_variable']['gust_kmh']['id'],'best_match')
        self.assertEqual(r['level'],'amarelo')
        row=next(r for r in s['forecast_ranges'] if r['variable']=='gust_kmh')
        self.assertTrue(row['attention_disagreement']);self.assertEqual(row['independent_provider_count'],1)
        self.assertEqual(len(row['members']),2)

    def test_additional_model_coincidence_requires_same_observed_time(self):
        observation=evidence('cemaden','420130701A','gust_kmh',70,STAMP,unit='km/h')
        observation['band']=2
        storm=model(NOW,'ecmwf_ifs025');storm['hourly'][1]['gust_kmh']=75
        matches=[]
        model_evidence({'records':[storm]},None,STAMP,observed_signals=[observation],matches=matches)
        self.assertEqual(len(matches),1)
        d=dashboard();d['synthesis']['observation_model_matches']=matches
        self.assertEqual(classify(d,{},STAMP)['level'],'laranja')
        storm['hourly'][1]['gust_kmh']=10;storm['hourly'][8]['gust_kmh']=100
        matches=[];model_evidence({'records':[storm]},None,STAMP,observed_signals=[observation],matches=matches)
        self.assertEqual(matches,[])

    def test_stale_or_incomplete_other_model_does_not_create_attention(self):
        bad=model(NOW,'ncep_gfs_global');bad['hourly'][3]['gust_kmh']=150;bad['hourly'][5]['gust_kmh']=None
        rows,_,_=model_evidence({'records':[bad]},None,STAMP)
        self.assertFalse(any(r['variable']=='gust_kmh' for r in rows))
        bad=model(NOW-timedelta(hours=9),'ncep_gfs_global')
        self.assertEqual(model_evidence({'records':[bad]},None,STAMP)[0],[])

    def test_cptec_exact_locality_current_codes_and_unknown(self):
        self.assertEqual(cptec_days(cptec(),STAMP)[0]['source'],'CPTEC/INPE')
        for comp in (cptec(locality='Joinville'),cptec(code='unknown')):
            self.assertEqual(cptec_days(comp,STAMP),[])
        old=cptec();old['cptec']['updated_day']='2026-11-05';self.assertEqual(cptec_days(old,STAMP),[])
        future=cptec();future['cptec']['checked_at']=iso(NOW+timedelta(minutes=30));self.assertEqual(cptec_days(future,STAMP),[])

    def test_cptec_storm_supports_attention_without_inmet(self):
        d=dashboard();d['synthesis']['forecast_context']={'days':cptec_days(cptec(),STAMP)}
        r=classify(d,{},STAMP);self.assertEqual(r['level'],'amarelo');self.assertIn('CPTEC/INPE',r['reason'])
        self.assertEqual(r['basis'],'cptec_qualitative_forecast_attention')

    def test_cptec_can_cover_rain_but_does_not_fabricate_wind_or_rain_amount(self):
        q=assess({'days':cptec_days(cptec('pn'),STAMP)},STAMP)
        self.assertTrue(q['coverage']['rain']['available']);self.assertFalse(q['coverage']['wind']['available'])
        self.assertNotIn('precipitation_mm',q['periods'][0]);self.assertNotIn('gust_kmh',q['periods'][0])

    def test_partial_sources_can_jointly_cover_periods_without_losing_provenance(self):
        ctx=context();ctx['days'][1]['periods'].pop(0)
        ctx['days']+=cptec_days(cptec('pn'),STAMP)
        q=assess(ctx,STAMP);self.assertTrue(q['coverage']['rain']['available'])
        self.assertFalse(q['coverage']['wind']['available'])

    def test_inmet_numeric_temperature_is_retained_without_invented_risk_limit(self):
        feed={'status':'available','retrieved_at':STAMP,'valid_until':iso(NOW+timedelta(hours=6)),
              'days':[{'day':'2026-11-13','minimum_c':19,'maximum_c':29,'periods':[]} ]}
        d=dashboard();d['assessment']={};s,_,detail=build(d,{}, {}, {}, {'records':[]},feed,{},STAMP)
        d['synthesis']=s;r=classify(d,detail,STAMP)
        self.assertEqual(r['quantitative_context'][0]['source'],'INMET')
        self.assertEqual(r['quantitative_context'][0]['maximum_c'],29)
        self.assertIsNone(r['level'])

    def test_publication_requires_source_region_event_dates_and_positive_cue(self):
        text='Início: 13/11/2026 às 06h00\nFim: 13/11/2026 às 18h00\nRegiões: Litoral Norte\nChuva intensa.'
        for source in ('Epagri/Ciram','Defesa Civil SC'):
            feed=bulletin(text,source)
            rows,pending=publication_evidence(feed if source=='Epagri/Ciram' else {},feed if source!='Epagri/Ciram' else {},STAMP)
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['source'],source)
            d=dashboard();d['synthesis']['publication_evidence']=rows
            self.assertEqual(classify(d,{},STAMP)['level'],'amarelo')
        for bad in (text.replace('Litoral Norte','Oeste'),text.replace('13/11/2026','12/11/2026'),
                    'Regiões: Litoral Norte. Tempestade nas próximas horas.',text.replace('Chuva intensa','Sem tempestade')):
            self.assertEqual(publication_evidence(bulletin(bad),{},STAMP)[0],[])

    def test_editorial_wind_and_explicit_exclusion_are_respected(self):
        text='Início: 13/11/2026 às 06h00\nFim: 13/11/2026 às 18h00\nRegiões: Litoral Norte\nVento forte.'
        self.assertEqual(len(publication_evidence(bulletin(text),{},STAMP)[0]),1)
        excluded=text.replace('Regiões: Litoral Norte','Regiões: Todo o estado, menos o Litoral Norte')
        self.assertEqual(publication_evidence(bulletin(excluded),{},STAMP)[0],[])

    def test_other_region_positive_text_cannot_leak_into_local_publication(self):
        text='Início: 13/11/2026 às 06h00\nFim: 13/11/2026 às 18h00\nRegiões: Litoral Norte\nTempo estável no Litoral Norte. Tempestade no Oeste.'
        self.assertEqual(publication_evidence(bulletin(text),{},STAMP)[0],[])

    def test_editorial_day_sections_use_event_day_and_relevant_clause(self):
        text='Sexta-feira (13/11): Tempo firme em SC. À tarde temporais isolados na faixa leste do estado. Sábado (14/11): Tempo estável em SC.'
        rows,_=publication_evidence(bulletin(text),{},STAMP)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['start_at'],'2026-11-13T03:00:00Z')
        self.assertEqual(rows[0]['scope'],'regional_reference_not_municipal_confirmation')
        self.assertEqual(publication_evidence(bulletin(text.replace('(13/11)','(12/11)')),{},STAMP)[0],[])

    def test_impact_potential_is_not_a_verified_disaster_or_calamity(self):
        text='Início: 13/11/2026 às 06h00\nFim: 13/11/2026 às 18h00\nRegiões: Araquari\nForam registrados alagamentos.'
        feed=bulletin(text,'Defesa Civil SC');rows,_=publication_evidence({},feed,STAMP)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['level'],'amarelo')
        feed=bulletin(text.replace('Foram registrados','Podem ser registrados'),'Defesa Civil SC')
        self.assertEqual(publication_evidence({},feed,STAMP)[0],[])

    def test_failed_stale_future_or_untrusted_publication_does_not_classify(self):
        text='Sexta-feira (13/11): Tempestades em SC.'
        for change in ({'status':'stale'},{'retrieved_at':iso(NOW-timedelta(hours=7))}):
            feed=bulletin(text);feed.update(change);self.assertEqual(publication_evidence(feed,{},STAMP)[0],[])
        feed=bulletin(text);feed['bulletins'][0]['url']='https://evil.example/aviso'
        self.assertEqual(publication_evidence(feed,{},STAMP)[0],[])
        feed=bulletin(text);feed['bulletins'][0]['published_at']=iso(NOW+timedelta(hours=1))
        self.assertEqual(publication_evidence(feed,{},STAMP)[0],[])

    def test_antecedent_windows_are_separate_equal_weight_and_lower_bound_is_positive_only(self):
        p={'observed_rain':{'stations':[{'code':'420130701A','observed_at':STAMP,'rain_3h_mm':60,'rain_6h_mm':65,'rain_72h_mm':90}]}}
        rain=antecedent_rain(p,STAMP)
        self.assertEqual([r['hours'] for r in rain['windows']],[3,6,72])
        self.assertEqual(len(rain['attention_lower_bounds']),2)
        d=dashboard();d['synthesis']['antecedent_rain']=rain
        self.assertEqual(classify(d,{},STAMP)['level'],'amarelo')
        p['observed_rain']['stations'][0]['rain_24h_mm']=70
        self.assertEqual(antecedent_rain(p,STAMP)['attention_lower_bounds'],[])
        p['observed_rain']['stations'][0]['rain_6h_mm']=1
        self.assertEqual(antecedent_rain(p,STAMP)['windows'],[])

    def test_regional_inmet_rain_needs_nearby_real_complete_observation(self):
        feed={'status':'available','checked_at':STAMP,'stations':[{'code':'A851','latitude':-26.38,'longitude':-48.72,
              'observed_at':STAMP,'rain_last_hour_mm':25,'rain_last_24_readings_mm':70,'rain_24h_complete':True,'hourly_coverage_24':24}]}
        point={'latitude':-26.375,'longitude':-48.721}
        rows=regional_inmet_rain(feed,point,STAMP);self.assertEqual(len(rows),2)
        self.assertTrue(all(r['scope']=='regional_not_araquari_station' for r in rows))
        feed['stations'][0]['hourly_coverage_24']=23
        self.assertEqual(len(regional_inmet_rain(feed,point,STAMP)),1)
        feed['stations'][0]['latitude']=-27.5
        self.assertEqual(regional_inmet_rain(feed,point,STAMP),[])
        self.assertEqual(regional_inmet_rain({'status':'not_configured'},point,STAMP),[])

    def test_metar_contingency_remains_regional_and_does_not_replace_unreported_gust(self):
        d=dashboard();d['synthesis']['observations']=[o for o in d['synthesis']['observations'] if o['variable'].startswith('rain')]
        d['synthesis']['signals']=[{**o,'band':0} for o in d['synthesis']['observations']]
        regional=[{**evidence('NOAA/METAR','SBJV',field,10,STAMP,unit='km/h',ttl=2),
                   'scope':'regional_not_araquari_station','distance_km':20} for field in ('wind_kmh','gust_kmh')]
        d['synthesis']['regional_observations']=regional
        r=classify(d,{},STAMP);self.assertEqual(r['level'],'verde');self.assertTrue(r['coverage']['regional_reference_used'])
        self.assertTrue(all(o['station']!='SBJV' for o in d['synthesis']['observations']))
        d['synthesis']['regional_observations'].pop();self.assertIsNone(classify(d,{},STAMP)['level'])
        d['synthesis']['regional_observations']=regional
        for row in regional:row['distance_km']=40
        self.assertIsNone(classify(d,{},STAMP)['level'])

    def test_article_extractor_excludes_sidebar_and_scripts_preserving_fields(self):
        raw=b'<nav>Temporal no Oeste</nav><div class="entry-content"><p>Regioes: Araquari</p><script>bad()</script><p>Fim: 13/11/2026</p></div><aside>other region</aside>'
        text=extract(raw)
        self.assertIn('\n',text);self.assertNotIn('Oeste',text);self.assertNotIn('bad()',text);self.assertNotIn('other',text)

    def test_unknown_sensor_does_not_gain_a_numeric_risk_threshold(self):
        feed={'status':'available','checked_at':STAMP,'stations':[{'code':'420130701A','readings':[
              {'sensor_id':240,'value':50,'unit':None,'observed_at':STAMP},{'sensor_id':60,'value':22,'unit':'°C','observed_at':STAMP}]}]}
        rows=sensor_inventory(feed,STAMP);self.assertEqual(rows[0]['use'],'context_only');self.assertEqual(rows[1]['use'],'temperature_observation')

    def test_previous_history_recovers_from_503_without_reinitializing(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
        from build_site import fetch_previous_json
        error=HTTPError('https://example.org/data/history.json',503,'Unavailable',{},None)
        with patch('build_site.urlopen',side_effect=[error,io.BytesIO(b'{"records":[1]}')]) as request, patch('build_site.time.sleep') as sleep:
            self.assertEqual(fetch_previous_json('https://example.org/','data/history.json'),{'records':[1]})
            self.assertEqual(request.call_count,2);self.assertIn('?retry=',request.call_args.args[0].full_url)
            sleep.assert_called_once_with(1)
        with patch('build_site.urlopen',side_effect=error) as request, patch('build_site.time.sleep'):
            with self.assertRaises(RuntimeError):fetch_previous_json('https://example.org/','data/history.json')
            self.assertEqual(request.call_count,3)
        with patch('build_site.urlopen',return_value=io.BytesIO(b'{"fixture_mode":true}')), patch('build_site.time.sleep'):
            with self.assertRaises(ValueError):fetch_previous_json('https://example.org/','data/history.json')

    def test_summary_history_preserves_level_provenance_and_does_not_duplicate_full_context(self):
        d=dashboard();r=classify(d,{},STAMP);summary=history_snapshot(r)
        self.assertEqual(summary['level'],r['level']);self.assertEqual(summary['method_version'],r['method_version'])
        self.assertNotIn('qualitative_forecast',summary);self.assertTrue(summary['candidates'][0]['evidence'])
        self.assertEqual(summary,history_snapshot(r));self.assertIn('qualitative_forecast',r)

if __name__=='__main__':unittest.main()
