"""Browser-only layout checks; synthetic data is intercepted, never published.

CI installs pinned Playwright in an isolated environment. Run directly after
installing the browser to inspect 390 px and 1440 px layouts and screenshots.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from ui_style_system import check_style_system

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'ui-artifacts'


def fixture():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    iso = lambda t: t.isoformat().replace('+00:00', 'Z')
    stamp, expiry = iso(now), iso(now + timedelta(hours=3))
    start = now.replace(minute=0, second=0)
    catalog = [{'source': 'cemaden-rain', 'station': code, 'name': name, 'municipality': 'Araquari',
                'latitude': -26.37, 'longitude': -48.72, 'distance_km': 2}
               for code, name in [('420130701A', 'Rainha'), ('420130702A', 'Porto Grande'), ('420130704A', 'Centro')]]
    records = [{'source': 'cemaden-rain', 'station': station['station'], 'observed_at': stamp,
                'rain_1h_mm': value, 'rain_24h_mm': value + 2}
               for station, value in zip(catalog, [0, 20.8, 5.6])]
    signal = {'source': 'cemaden', 'station': '420130702A', 'variable': 'rain_1h_mm', 'value': 20.8,
              'unit': 'mm', 'kind': 'observation', 'band': 1, 'start_at': iso(now-timedelta(hours=1)), 'end_at': stamp}
    wind = {'source': 'open-meteo', 'station': 'araquari', 'variable': 'gust_kmh', 'value': 51.5,
            'unit': 'km/h', 'kind': 'forecast', 'band': 1, 'start_at': iso(start+timedelta(hours=16)), 'end_at': iso(start+timedelta(hours=16))}
    data = {'schema_version': 1, 'kind': 'araquari_weather_dashboard_not_official_decision', 'location_id': 'araquari',
            'decision_automated': False, 'generated_at': stamp, 'valid_until': expiry,
            'assessment': {'valid_until': expiry, 'suggested_level': None, 'monitoring_state': 'technical_attention',
                           'numeric_support': {'valid_until': expiry, 'maximum_band': 1, 'core_complete': True,
                                               'signals': [signal, wind], 'coincidences': []}},
            'station_catalog': catalog, 'source_status': [{'source':'Epagri/Ciram · avisos','status':'available','reference_at':stamp}],
            'regional_rain_context': {'radius_km': 40, 'stations': [{'source': 'cemaden-rain', 'station': 'N', 'name': 'Pirabeiraba', 'municipality': 'Joinville'}],
                                     'records': [{'source': 'cemaden-rain', 'station': 'N', 'observed_at': stamp, 'rain_1h_mm': 3}]},
            'gauge_distribution': {'status': 'available', 'median_mm': 7.6, 'maximum_mm': 22.8, 'station_count': 3},
            'forecast': {'status':'available','collected_at':stamp,'reference_at':stamp,'start_at': iso(start), 'rain': {'status': 'complete', 'total_mm': 18, 'start_at': iso(start), 'end_at': iso(start+timedelta(hours=24))},
                         'wind': {'gust_kmh': {'maximum': 51.5, 'at': wind['start_at']}},
                         'heat': {'maximum_c': 29.3, 'maximum_at': iso(start+timedelta(hours=15))}},
            'forecast_series': [{'time': iso(start+timedelta(hours=i)), 'precipitation_mm': [0.1, 0.2, 1, 5, 9, 3][max(0, min(5, i-13))] if 13 <= i <= 18 else 0.1,
                                 'wind_kmh': 15, 'gust_kmh': 51.5 if i == 16 else 20, 'temperature_c': 24}
                                for i in range(25)]}
    history = {'kind': 'araquari_point_observation_history_not_climatology', 'location_id': 'araquari', 'generated_at': stamp, 'records': records}
    return {'campus_station.json': {'schema_version':1,'kind':'ifc_araquari_campus_observations_not_risk_criteria','location_id':'araquari','risk_criteria':False,'publication_at':stamp,'checked_at':stamp,'status':'unavailable','metrics':{}}, 'latest.json': {'schema_version': 1, 'generated_at': stamp}, 'dashboard.json': data, 'observation_history.json': history}


@contextmanager
def server():
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT/'web')))
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_port}/'
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def check_layout(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal page overflow'
    visible = page.locator('#observed-panel')
    assert visible.is_visible()
    assert page.locator('.station-bar').count() == 3
    assert page.locator('#plot').inner_text().count('4201307') == 0
    assert 'superaç' not in page.locator('.level-card').inner_text()
    assert page.locator('[data-risk-level]').count() == 6
    assert page.locator('[data-mode]').count()==0
    assert page.locator('#chart-range').is_visible()
    assert page.locator('#forecast-variable option').count()==3
    assert page.locator('#level-kind').inner_text()=='Consultivo'
    assert page.locator('#level-card').get_attribute('data-risk') == 'amarelo'
    assert page.locator('#level-title').inner_text()=='Atenção'
    page.locator('.station-filter summary').click()
    page.get_by_label('Acumulado observado',exact=True).select_option('1')
    # Main controls must remain comfortably operable on mobile.
    for selector in ['#rain-scope', '#station-select', '#rain-window']:
        box = page.locator(selector).bounding_box()
        assert box and box['height'] >= 34
    assert page.get_by_role('link',name='Ver análise e critérios →').get_attribute('href')=='./dados.html#weather-synthesis-detail'
    check_style_system(page)
    page.get_by_label('Área', exact=True).select_option('nearby')
    assert page.locator('.station-bar').count() == 1
    assert 'Joinville' in page.locator('#plot').inner_text()
    page.get_by_label('Área', exact=True).select_option('local')
    page.get_by_role('button', name='Ao longo do tempo', exact=True).click()
    assert page.locator('#plot .rain-interval').count() == 3
    page.get_by_role('button', name='Por estação', exact=True).click()
    assert page.locator('.station-bar').count() == 3
    page.locator('[data-focus=gust_kmh]').click()
    assert page.locator('#forecast-panel').is_visible()
    assert page.locator('#observed-panel').is_visible()
    assert page.locator('#chart-range').input_value() == '24'
    page.locator('#forecast-variable').select_option('precipitation_mm')
    assert page.locator('#station-details').count()==0
    page.locator('.station-filter summary').click()


def main():
    from playwright.sync_api import sync_playwright
    OUTPUT.mkdir(exist_ok=True)
    data = fixture()
    with server() as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        errors = []
        for width, height in [(1440, 1150), (390, 844)]:
            context = browser.new_context(viewport={'width': width, 'height': height}, color_scheme='light')
            context.route('**/data/*.json*', lambda route: route.fulfill(content_type='application/json', body=json.dumps(data[route.request.url.split('/')[-1].split('?')[0]])))
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(url)
            page.locator('.station-bar').first.wait_for()
            try:
                check_layout(page)
            except Exception:
                page.screenshot(path=str(OUTPUT/f'failure-{width}.png'), full_page=True)
                raise
            if width == 1440:
                a, b = page.locator('#observed-panel').bounding_box(), page.locator('#forecast-panel').bounding_box()
                assert abs(a['y']-b['y']) < 3, 'Desktop graphs must align'
                left,right=page.locator('#plot').bounding_box(),page.locator('#forecast-plot').bounding_box()
                assert abs(left['y']-right['y'])<4, 'Plot starts must align below shared controls'
            else:
                a, b = page.locator('#observed-panel').bounding_box(), page.locator('#forecast-panel').bounding_box()
                assert b['y'] > a['y'] + a['height'], 'Mobile graphs must stack'
            page.screenshot(path=str(OUTPUT/f'attention-light-{width}.png'), full_page=True)
            page.locator('#theme-toggle').click()
            assert page.locator('html').get_attribute('data-theme') == 'dark'
            check_style_system(page)
            page.screenshot(path=str(OUTPUT/f'attention-dark-{width}.png'), full_page=True)
            context.close()
        # Positive routine data may show descriptive green; missing/expired data may not.
        policy = data['dashboard.json']['assessment']
        policy['monitoring_state'] = 'routine'
        policy['numeric_support'].update(maximum_band=0, signals=[{'band': 0}])
        for index, row in enumerate(data['observation_history.json']['records']):
            row.update(rain_1h_mm=index, rain_24h_mm=index+2)
        data['dashboard.json']['forecast']['wind']['gust_kmh']['maximum'] = 25
        data['dashboard.json']['gauge_distribution'].update(median_mm=3, maximum_mm=4)
        context = browser.new_context(viewport={'width': 1440, 'height': 1150})
        context.route('**/data/*.json*', lambda route: route.fulfill(content_type='application/json', body=json.dumps(data[route.request.url.split('/')[-1].split('?')[0]])))
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(url)
        page.get_by_role('heading', name='Normalidade').wait_for()
        assert page.locator('#level-card').get_attribute('data-risk') == 'verde'
        page.screenshot(path=str(OUTPUT/'normality-light-1440.png'), full_page=True)
        assert not page.locator('#epagri-context').is_visible()
        assert not page.locator('#inmet-context').is_visible()
        data['dashboard.json']['inmet_context'] = {'status': 'available', 'retrieved_at': data['dashboard.json']['generated_at'], 'notices': []}
        page.reload()
        page.get_by_role('heading', name='Normalidade').wait_for()
        assert not page.locator('#inmet-context').is_visible()
        policy['evidence'] = [{'status': 'eligible', 'title': 'Aviso regional de teste',
            'valid_from': data['dashboard.json']['generated_at'], 'valid_until': data['dashboard.json']['valid_until'],
            'regions_text': 'Litoral Norte', 'url': 'https://ciram.epagri.sc.gov.br/'}]
        assert page.locator('#epagri-context,#inmet-context').count()==0
        policy['evidence']=[]
        policy['monitoring_state'] = 'partial'
        policy['numeric_support']['core_complete'] = False
        page.reload()
        page.get_by_role('heading', name='Dados insuficientes para classificar').wait_for()
        assert page.locator('#level-card').get_attribute('data-risk') == 'neutral'
        assert not errors, errors
        context.close()
        browser.close()
    print('Browser UX checks passed: mobile/desktop, themes, dialogs, human names, exact rain windows, surrounding isolation, descriptive normality and missing data.')


if __name__ == '__main__':
    main()
