"""Regression for rolling totals, long horizons, raw tables and variable expiry.

Fixtures are intercepted locally and are never written to production data.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from ui_dashboard import fixture, server, OUTPUT
from ui_style_system import check_style_system


def dense_fixture():
    data = fixture()
    dashboard = data['dashboard.json']
    now = datetime.fromisoformat(dashboard['generated_at'].replace('Z', '+00:00'))
    iso = lambda t: t.isoformat().replace('+00:00', 'Z')
    base = now.replace(minute=0, second=0, microsecond=0)
    records = []
    for index, station in enumerate(dashboard['station_catalog']):
        for n in range(1600):
            records.append({'source': 'cemaden-rain', 'station': station['station'],
                            'observed_at': iso(now-timedelta(minutes=n*5)),
                            'rain_1h_mm': n % 4, 'rain_24h_mm': 180 if n == 835 else (index+1)*10+n % 7})
    data['observation_history.json']['records'] = records
    dashboard['forecast_series'] = [{'time': iso(base+timedelta(hours=n)),
                                    'precipitation_mm': None if n == 3 else 0 if n == 1 else 1,
                                    'temperature_c': 30 if n == 18 else 21+n % 6,
                                    'wind_kmh': 10, 'gust_kmh': 50 if n == 18 else 20}
                                   for n in range(241)]
    dashboard['forecast']['sources_by_variable'] = {
        key: {'status': 'available', 'valid_until': iso(now+timedelta(hours=2)),
              'reference_at': dashboard['generated_at'], 'id': 'ecmwf_ifs025', 'name': 'ECMWF IFS'}
        for key in ('precipitation_mm', 'temperature_c', 'wind_kmh', 'gust_kmh')}
    dashboard['forecast']['rain']['status'] = 'partial'
    return data


def chart_contrast(page):
    failures = page.evaluate("""() => {
      const rgb=s=>(s.match(/[0-9.]+/g)||[]).slice(0,3).map(Number);
      const lum=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((v,n,i)=>v+n*[.2126,.7152,.0722][i],0);
      const contrast=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
      const background=rgb(getComputedStyle(document.querySelector('.chart-card')).backgroundColor);
      const result=[];
      for(const n of document.querySelectorAll('.weather-chart .chart-label,.weather-chart .chart-unit,.weather-chart .weather-line,.weather-chart .accumulation-line,.weather-chart .rain-interval')){
        const css=getComputedStyle(n),text=n.tagName==='text',ink=rgb(text?css.fill:n.tagName==='rect'?css.fill:css.stroke);
        if(contrast(ink,background)<(text?4.5:3))result.push({tag:n.tagName,contrast:contrast(ink,background)});
        if(text&&parseFloat(css.fontSize)<13)result.push({tag:n.tagName,font:css.fontSize});
      }
      return result;
    }""")
    assert not failures, failures


def check_tooltip_edges(page, width):
    """Moving right must neither shrink the tooltip nor escape the chart panel."""
    page.locator('#forecast-variable').select_option('gust_kmh')
    graph = page.locator('#forecast-plot svg')
    tooltip = page.locator('#forecast-tooltip')
    hit = graph.locator('[data-chart-hit]')
    hit.scroll_into_view_if_needed()

    def geometry():
        return tooltip.evaluate("""node => {
          const tip=node.getBoundingClientRect(), panel=node.parentElement.getBoundingClientRect();
          return {width:tip.width,height:tip.height,left:tip.left,right:tip.right,
            top:tip.top,bottom:tip.bottom,panelLeft:panel.left,panelRight:panel.right,
            panelTop:panel.top,panelBottom:panel.bottom,position:getComputedStyle(node).position};
        }""")

    if width <= 620:
        graph.focus()
        page.keyboard.press('End')
        assert tooltip.is_visible()
        bounds = geometry()
        assert bounds['position'] == 'static', bounds
        assert bounds['width'] >= 0.7 * (bounds['panelRight'] - bounds['panelLeft']), bounds
        assert bounds['left'] >= bounds['panelLeft'] - 1 and bounds['right'] <= bounds['panelRight'] + 1, bounds
    else:
        box = hit.bounding_box()
        assert box, 'Chart hit area must be visible'
        initial = None
        found_reading = False
        heading = page.locator('#forecast-heading').inner_text()
        for fraction in (0.03, 0.5, 0.95, 0.99, 0.97, 0.5, 0.03):
            x = box['x'] + fraction * box['width']
            y = box['y'] + 0.5 * box['height']
            page.mouse.move(x, y)
            assert tooltip.is_visible()
            reading = tooltip.inner_text()
            assert reading.startswith(heading), (width, fraction, reading)
            assert 'km/h' in reading or 'Sem amostra' in reading, (width, fraction, reading)
            found_reading = found_reading or 'km/h' in reading
            bounds = geometry()
            if initial is None:
                initial = bounds['width']
                assert initial >= 200, bounds
            assert abs(bounds['width'] - initial) <= 1, (width, fraction, bounds)
            assert bounds['left'] >= bounds['panelLeft'] - 1 and bounds['right'] <= bounds['panelRight'] + 1, bounds
            assert bounds['top'] >= bounds['panelTop'] - 1 and bounds['bottom'] <= bounds['panelBottom'] + 1, bounds
            if fraction >= 0.95:
                assert bounds['right'] <= x + 1, bounds
        assert found_reading, 'At least one measured forecast value must be accessible by mouse'
        graph.focus()
        page.keyboard.press('End')
        assert tooltip.is_visible()
        page.keyboard.press('Enter')
        assert graph.get_attribute('data-pinned') == 'true'
        assert 'Fixado' in tooltip.inner_text()
    graph.focus()
    page.keyboard.press('Escape')
    assert not tooltip.is_visible()
    page.locator('#forecast-variable').select_option('precipitation_mm')


def main():
    from playwright.sync_api import sync_playwright
    OUTPUT.mkdir(exist_ok=True)
    source = dense_fixture()
    with server() as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in (320, 390, 768, 1024, 1440):
            data = deepcopy(source)
            context = browser.new_context(viewport={'width': width, 'height': 1000}, has_touch=True)
            context.route('**/data/*.json*', lambda route: route.fulfill(content_type='application/json', body=json.dumps(data[route.request.url.split('/')[-1].split('?')[0]])))
            page = context.new_page()
            errors, requests = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append(request.url))
            try:
                page.goto(url)
                page.locator('#plot .accumulation-line').first.wait_for()
                assert page.locator('#plot .rain-interval').count() == 0
                assert page.locator('#forecast-plot .chart-zero').count() == 1
                assert page.locator('#forecast-plot .chart-gap').count() == 1
                assert '23/24' in page.locator('#forecast-status').inner_text()
                count = len(requests)
                for hours in ('72', '168', '240'):
                    page.locator('#chart-range').select_option(hours)
                    assert page.locator('#forecast-plot .rain-interval').count() < int(hours)
                    assert 'blocos de' in page.locator('#forecast-heading').inner_text()
                    assert 'Próximas' in page.locator('#forecast-period').inner_text()
                    assert 'Últimas' in page.locator('#observed-period').inner_text()
                assert len(requests) == count, 'Changing periods must use already loaded data'
                assert 'até 7 dias' in page.locator('#observed-status').inner_text()
                assert page.locator('#plot .chart-gap').count() >= 1
                assert page.locator('#plot svg *').count() < 100, 'Dense rolling rain must not produce thousands of rectangles/markers'
                page.locator('.station-filter summary').click()
                color = page.locator('#chart-legend .legend-item').filter(has_text='Rainha').locator('line').get_attribute('stroke')
                page.locator('#station-select').select_option('cemaden-rain:420130701A')
                assert page.locator('#chart-legend .legend-item').filter(has_text='Rainha').locator('line').get_attribute('stroke') == color
                assert 'Rainha' in page.locator('#observed-filter').inner_text()
                page.locator('#station-select').select_option('all')
                page.locator('.station-filter summary').click()
                page.locator('#observed-chart-data summary').click()
                page.locator('#observed-chart-data tbody tr').first.wait_for()
                assert page.locator('#observed-chart-data tbody tr').count() == 50
                assert '4800 registros' in page.locator('#observed-chart-data').inner_text()
                page.locator('#observed-chart-data button').filter(has_text='Próximos').click()
                assert '51–100' in page.locator('#observed-chart-data').inner_text()
                check_style_system(page)
                page.locator('#observed-chart-data summary').click()
                page.locator('#chart-range').select_option('24')
                graph = page.locator('#plot svg')
                graph.focus()
                page.keyboard.press('End')
                assert 'término da leitura' in page.locator('#chart-tooltip').inner_text()
                assert page.locator('#plot [data-chart-markers] .chart-point-ring').count() == 3
                page.keyboard.press('Enter')
                assert graph.get_attribute('data-pinned') == 'true'
                page.keyboard.press('Escape')
                assert not page.locator('#chart-tooltip').is_visible()
                # The category view shares pin, arrows and Escape.
                page.get_by_role('button', name='Por estação', exact=True).click()
                graph = page.locator('#plot svg')
                graph.focus(); page.keyboard.press('Home'); page.keyboard.press('Enter')
                assert graph.get_attribute('data-pinned') == 'true'
                page.keyboard.press('ArrowDown')
                assert 'Porto Grande' in page.locator('#chart-tooltip').inner_text()
                page.keyboard.press('Escape')
                page.get_by_role('button', name='Ao longo do tempo', exact=True).click()
                for theme in ('light', 'dark'):
                    if page.locator('html').get_attribute('data-theme') != theme:
                        page.locator('#theme-toggle').click()
                    chart_contrast(page)
                    check_style_system(page)
                    check_tooltip_edges(page, width)
                    if width in (390, 1440):
                        page.screenshot(path=str(OUTPUT/f'chart-improvements-{theme}-{width}.png'), full_page=True)
                if width == 1440:
                    # Half the CSS viewport exercises the reflow used at 200% browser zoom.
                    page.set_viewport_size({'width': 720, 'height': 1000})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert not errors, errors
            finally:
                context.close()
        # The IFC remains selectable even without a single complete rolling sum.
        data = deepcopy(source)
        stamp = data['dashboard.json']['generated_at']
        end = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        window = {'hours':24, 'start_at':(end-timedelta(hours=24)).isoformat(), 'end_at':stamp,
                  'expected_minutes':1440, 'covered_minutes':1410, 'validated_minutes':55,
                  'estimated_minutes':1355, 'complete':False, 'value':1.4, 'quality':'partial'}
        data['dashboard.json'].setdefault('synthesis', {}).setdefault('campus_context', {})['rain_reconstruction'] = {
            'windows':[window], 'series':{'rain_24h':[]}, 'authoritative_from':window['start_at']}
        for width in (320, 1440):
            context = browser.new_context(viewport={'width':width,'height':900})
            context.route('**/data/*.json*', lambda route: route.fulfill(content_type='application/json', body=json.dumps(data[route.request.url.split('/')[-1].split('?')[0]])))
            page = context.new_page()
            page.goto(url)
            page.locator('#plot .chart-partial-sample').first.wait_for()
            assert page.locator('#ifc-rain-status').count() == 0
            assert '4 estações' in page.locator('#station-coverage').inner_text()
            assert 'IFC Araquari' in page.locator('#chart-legend').inner_text()
            page.locator('.station-filter summary').click()
            page.locator('#station-select').select_option('ifc:ifc-araquari')
            page.get_by_role('button', name='Por estação', exact=True).click()
            assert page.locator('#plot .station-partial').count() == 1
            assert page.locator('#plot .station-bar').count() == 0
            assert 'parcial 97,9%' in page.locator('#plot').inner_text()
            page.get_by_role('button', name='Ao longo do tempo', exact=True).click()
            assert page.locator('#plot .chart-partial-sample').count() == 1
            assert page.locator('#plot .accumulation-line').count() == 0
            graph = page.locator('#plot svg')
            graph.focus()
            page.keyboard.press('End')
            assert '97,9%' in page.locator('#chart-tooltip').inner_text()
            assert '1,4 mm' in page.locator('#chart-tooltip').inner_text()
            assert 'soma parcial' in page.locator('#chart-tooltip').inner_text()
            assert page.locator('#ifc-rain-status').count() == 0
            page.locator('#rain-window').select_option('1')
            page.get_by_role('button', name='Por estação', exact=True).click()
            assert 'Acumulado indisponível' in page.locator('#plot').inner_text()
            page.locator('#rain-window').select_option('24')
            page.locator('#rain-scope').select_option('nearby')
            assert page.locator('#ifc-rain-status').count() == 0
            assert page.locator('#plot .station-partial').count() == 0
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            context.close()
        # Only the gust source expires: rain and observed samples remain usable.
        data = deepcopy(source)
        now = datetime.now(timezone.utc)
        data['dashboard.json']['forecast']['sources_by_variable']['gust_kmh']['valid_until'] = (now+timedelta(seconds=75)).isoformat()
        data['dashboard.json']['forecast']['sources_by_variable']['wind_kmh']['valid_until'] = (now+timedelta(seconds=5)).isoformat()
        context = browser.new_context(viewport={'width': 390, 'height': 900})
        context.route('**/data/*.json*', lambda route: route.fulfill(content_type='application/json', body=json.dumps(data[route.request.url.split('/')[-1].split('?')[0]])))
        page = context.new_page(); page.clock.install(time=now)
        page.goto(url); page.locator('#forecast-variable').select_option('gust_kmh')
        page.locator('#forecast-plot svg').wait_for()
        page.clock.fast_forward(61000)
        assert page.locator('#forecast-plot svg').count() == 1
        assert page.locator('#forecast-legend .legend-item').count() == 1
        assert page.locator('#forecast-heading').inner_text() == 'Rajadas previstas'
        page.clock.fast_forward(61000)
        assert page.locator('#forecast-plot svg').count() == 0
        assert 'desatualizada' in page.locator('#forecast-plot').inner_text()
        assert page.locator('#plot svg').count() == 1
        page.locator('#forecast-variable').select_option('precipitation_mm')
        assert page.locator('#forecast-plot svg').count() == 1
        context.close(); browser.close()
    print('Chart improvements passed: 320–1440px, rolling endpoints, zero/gaps, complete blocks, stable identity, 4800 raw samples, pagination, keyboard/pinning, tooltip edges in both themes, per-variable expiry, contrast and unchanged requests.')


if __name__ == '__main__':
    main()
