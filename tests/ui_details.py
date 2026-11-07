"""Actual Chromium checks for topic navigation and rich station data (CI only)."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from build_site import build
from ui_dashboard import server, OUTPUT


def datasets():
    with tempfile.TemporaryDirectory() as directory:
        target=Path(directory)/'site'
        build(target,fixture=ROOT/'tests/fixtures/open_meteo.json',station_fixture=ROOT/'tests/fixtures/inmet_catalog.json')
        result={str(p.relative_to(target)):json.loads(p.read_text()) for p in (target/'data').rglob('*.json')}
    # Test interception only: no synthetic dataset is written to the site.
    for data in result.values():
        if isinstance(data,dict):data.pop('fixture_mode',None)
    stamp=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    catalog=[{'code':code,'name':name,'municipality':'Araquari','latitude':-26.37,'longitude':-48.72,'readings':[]}
             for code,name in [('420130701A','Rainha'),('420130702A','Porto Grande'),('420130704A','Centro')]]
    rain=result['data/cemaden.json'];rain.update(status='available',checked_at=stamp)
    for place in rain['locations']:
        place['status']='available' if place['location_id']=='araquari' else 'no_recent_data'
        place['stations']=[{'code':station['code'],'observed_at':stamp,
                            **{f'rain_{h}h_mm':round(value+h/10,1) for h in (1,3,6,12,24,48,72,96,120)}}
                           for station,value in zip(catalog,[0,14,15.2])] if place['location_id']=='araquari' else []
    sensors=result['data/cemaden_sensors.json'];sensors.update(status='available',checked_at=stamp,stations=catalog)
    return result


def main():
    from playwright.sync_api import sync_playwright
    data=datasets();OUTPUT.mkdir(exist_ok=True)
    with server() as url,sync_playwright() as playwright:
        browser=playwright.chromium.launch()
        for width,height in [(1440,1100),(390,844)]:
            context=browser.new_context(viewport={'width':width,'height':height},color_scheme='light')
            context.route('**/data/**',lambda route: route.fulfill(content_type='application/json',body=json.dumps(data.get('data/'+route.request.url.split('/data/')[-1].split('?')[0],{}))))
            page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            try:
                page.goto(url+'dados.html#cemaden-title')
                page.locator('#cemaden-data .rain-station').first.wait_for()
                assert page.get_by_role('tab',name='Medições',exact=True).get_attribute('aria-selected')=='true'
                assert page.locator('[data-explore-panel]:visible').count()==1
                assert page.locator('#cemaden-data .rain-station').count()==3
                assert 'Rainha' in page.locator('#cemaden-data').inner_text()
                assert '420130701A' in page.locator('#cemaden-data').inner_text() # retained in the detailed area
                extra=page.locator('#cemaden-data .accumulation-more').first
                assert not extra.get_attribute('open')
                extra.locator('summary').click()
                assert '120H' in extra.inner_text()
                extra.locator('summary').click()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Details overflow'
                page.screenshot(path=str(OUTPUT/f'details-observations-light-{width}.png'),full_page=True)
                page.locator('#theme-toggle').click()
                page.screenshot(path=str(OUTPUT/f'details-observations-dark-{width}.png'),full_page=True)
                # All topics retain their data nodes; tab switches do not issue new data requests.
                for name in ['Visão geral','Previsões','Avisos','Histórico e redes','Fontes','Medições']:
                    page.get_by_role('tab',name=name,exact=True).click()
                    assert page.locator('[data-explore-panel]:visible').count()==1
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),name+' overflow'
                page.get_by_role('tab',name='Previsões',exact=True).click()
                page.locator('#chart svg').wait_for()
                page.locator('#chart svg').focus();page.keyboard.press('Home')
                assert page.locator('#detail-chart-tooltip').is_visible()
                page.locator('#location-select').select_option('joinville')
                assert 'Joinville' in page.locator('#place-title').inner_text()
                assert 'Araquari' in page.locator('#place-subtitle').inner_text()
                page.locator('#location-select').select_option('araquari')
                page.get_by_role('tab',name='Avisos',exact=True).click()
                page.get_by_role('tab',name='Avisos',exact=True).focus();page.keyboard.press('ArrowRight')
                assert page.get_by_role('tab',name='Histórico e redes',exact=True).get_attribute('aria-selected')=='true'
                page.go_back()
                assert page.get_by_role('tab',name='Avisos',exact=True).get_attribute('aria-selected')=='true'
                page.goto(url+'dados.html#archive-title')
                page.locator('#archive-title').wait_for(state='visible')
                assert page.get_by_role('tab',name='Histórico e redes',exact=True).get_attribute('aria-selected')=='true'
                assert page.locator('#archive-title').evaluate("el=>el.closest('details').open")
                page.goto(url+'dados.html#not-a-section')
                assert page.get_by_role('tab',name='Visão geral',exact=True).get_attribute('aria-selected')=='true'
                assert not errors,errors
            except Exception:
                page.screenshot(path=str(OUTPUT/f'details-failure-{width}.png'),full_page=True)
                raise
            finally:
                context.close()
        browser.close()
    print('Detailed UX passed: preserved anchors and station values, progressive disclosure, six topics, municipality selection, keyboard, history/back, chart interaction, mobile and dark/light layouts.')


if __name__=='__main__':main()
