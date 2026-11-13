"""Real portal formats, slow responses, full text and expired alert windows."""
import io
import json
import sys
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from observatorio.config import load_locations
from observatorio.defesa_civil_sc import (collect,parse_wp_json,parse_rss,event_window,
    CivilDefenseError,_download,REQUEST_TIMEOUT,WP_API,ALERTAS,PORTAL)
from observatorio.source_evidence import publication_evidence
NOW=datetime(2026,11,13,22,30,tzinfo=timezone.utc)
STAMP=NOW.isoformat().replace('+00:00','Z')
LOCATIONS=load_locations(Path(__file__).resolve().parents[1]/'config/locations.json')


def payload(title='ATENÇÃO – 13/11 19:24 – TEMPORAIS nas próximas 2 horas.'):
    return [{'date_gmt':'2026-11-13T22:28:08','link':'https://www.defesacivil.sc.gov.br/2026/11/13/aviso-test/',
             'title':{'rendered':title},'excerpt':{'rendered':'<p>Texto resumido.</p>'},
             'content':{'rendered':'<p>TEMPORAIS para os municípios de Araquari e Joinville nas próximas 2 horas.</p><script>ignore()</script>'}}]


class DefesaRecoveryTests(unittest.TestCase):
    def test_timeout_exceeds_observed_response_time_without_sleeping_in_test(self):
        class Reply(io.BytesIO):
            status=200
            def geturl(self):return ALERTAS
        with patch('observatorio.defesa_civil_sc.urlopen',return_value=Reply(b'{}')) as request:
            self.assertEqual(_download(ALERTAS),b'{}')
            self.assertEqual(request.call_args.kwargs['timeout'],20)
        self.assertGreater(REQUEST_TIMEOUT,9)

    def test_full_json_content_avoids_article_requests_and_identifies_municipality(self):
        with patch('observatorio.defesa_civil_sc._download',return_value=json.dumps(payload()).encode()) as request:
            feed=collect(LOCATIONS,STAMP)
        self.assertEqual(request.call_count,1);self.assertIn('content',WP_API)
        self.assertEqual(feed['status'],'available');p=feed['publications'][0]
        self.assertIn('araquari',p['mentioned_location_ids']);self.assertIn('joinville',p['mentioned_location_ids'])
        self.assertNotIn('ignore()',p['assessment_text']);self.assertEqual(p['text_origin'],'wordpress_content')
        self.assertEqual(p['event_window']['end_at'],'2026-11-14T00:24:00Z')
        self.assertEqual(p['event_window']['start_at'],'2026-11-13T22:24:00Z')
        self.assertEqual(p['validity_status'],'not_verified_from_publication_date')
        evidence,_=publication_evidence({},feed,STAMP)
        self.assertEqual(len(evidence),1);self.assertEqual(evidence[0]['scope'],'municipality_explicit')

    def test_monitoring_and_meteorological_observation_are_not_discarded(self):
        for title,category in [('Monitoramento Meteorológico DC/SC 13/11 11:20','monitoramento_publicado'),
                               ('Observação Meteorológica DC/SC 13/11 10:50 – Condições do fim de semana','aviso_publicado')]:
            raw=payload(title);raw[0]['content']['rendered']='<p>Condições em Santa Catarina e no Litoral Norte.</p>'
            p=parse_wp_json(json.dumps(raw).encode(),LOCATIONS,NOW)[0]
            self.assertEqual(p['category'],category);self.assertIn('litoral_norte',p['regional_references'])
            self.assertNotIn('event_window',p)

    def test_expired_alert_is_context_not_current_classification(self):
        feed={'status':'available','last_successful_check':STAMP,'publications':parse_wp_json(json.dumps(payload()).encode(),LOCATIONS,NOW)}
        later=(NOW+timedelta(hours=3)).isoformat()
        rows,pending=publication_evidence({},feed,later)
        self.assertEqual(rows,[]);self.assertEqual(pending[0]['reason'],'expired_event_window')

    def test_incomplete_or_conflicting_duration_cannot_generate_window(self):
        for title in ['ATENÇÃO – 13/11 19:24 – Temporais nas próximas horas.',
                      'ATENÇÃO – 13/11 19:24 – Temporais nas próximas 30 horas.']:
            raw=payload(title);raw[0]['content']['rendered']='<p>Temporais em Araquari.</p>'
            self.assertNotIn('event_window',parse_wp_json(json.dumps(raw).encode(),LOCATIONS,NOW)[0])
        raw=payload();raw[0]['content']['rendered']='Nas próximas 3 horas para Araquari.'
        self.assertNotIn('event_window',parse_wp_json(json.dumps(raw).encode(),LOCATIONS,NOW)[0])

    def test_title_clock_is_not_replaced_by_publication_clock(self):
        p=parse_wp_json(json.dumps(payload()).encode(),LOCATIONS,NOW)[0]
        self.assertEqual(p['event_window']['start_at'],'2026-11-13T22:24:00Z')
        self.assertNotEqual(p['event_window']['start_at'],p['published_at'])
        p['published_at']='2026-11-14T22:30:00Z';self.assertIsNone(event_window(p))

    def test_alert_listing_is_first_html_fallback(self):
        listing=b'<h3><a href="https://www.defesacivil.sc.gov.br/2026/11/13/alerta/">ATENCAO - 13/11 19:24 - Chuva em Araquari</a></h3>'
        def fetch(url,**kwargs):
            if url==ALERTAS:return listing
            raise CivilDefenseError('timeout')
        with patch('observatorio.defesa_civil_sc._download',side_effect=fetch) as request:
            feed=collect(LOCATIONS,STAMP)
        self.assertEqual(feed['status'],'partial');self.assertEqual(len(feed['publications']),1)
        urls=[c.args[0] for c in request.call_args_list]
        self.assertIn(ALERTAS,urls);self.assertNotIn(PORTAL,urls)

    def test_completed_source_failure_keeps_previous_original_clock(self):
        with patch('observatorio.defesa_civil_sc._download',return_value=json.dumps(payload()).encode()):previous=collect(LOCATIONS,STAMP)
        later=(NOW+timedelta(minutes=30)).isoformat().replace('+00:00','Z')
        with patch('observatorio.defesa_civil_sc._download',side_effect=CivilDefenseError('timeout')):
            result=collect(LOCATIONS,later,previous=previous)
        self.assertEqual(result['status'],'stale');self.assertEqual(result['last_successful_check'],STAMP)
        self.assertEqual(result['publications'][0]['event_window'],previous['publications'][0]['event_window'])

    def test_z_timestamp_and_similar_municipal_name_are_handled(self):
        raw=payload();raw[0]['date_gmt']+='Z';raw[0]['content']['rendered']='<p>Araraquari não é o nome cadastrado.</p>'
        p=parse_wp_json(json.dumps(raw).encode(),LOCATIONS,NOW)[0]
        self.assertNotIn('araquari',p['mentioned_location_ids'])

    def test_rss_full_content_retains_qualitative_information(self):
        rss='''<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><item>
        <title>ATENÇÃO – 13/11 19:24 – Temporais nas próximas 2 horas.</title>
        <link>https://www.defesacivil.sc.gov.br/2026/11/13/aviso/</link><pubDate>Fri, 13 Nov 2026 19:28:08 -0300</pubDate>
        <description>Resumo.</description><content:encoded><![CDATA[<p>Temporais para os municípios de Araquari e Joinville nas próximas 2 horas.</p>]]></content:encoded>
        </item></channel></rss>'''
        p=parse_rss(rss.encode(),'alerta_publicado',LOCATIONS,NOW)[0]
        self.assertIn('araquari',p['mentioned_location_ids']);self.assertTrue(p['event_window'])

if __name__=='__main__':unittest.main()
