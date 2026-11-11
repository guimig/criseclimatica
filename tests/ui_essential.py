"""Real-browser checks for the implemented Essential design and chart cursors."""
import json
from datetime import datetime,timedelta
from ui_dashboard import fixture,server,OUTPUT
from ui_details import datasets
from ui_forecasts import comparison_fixture
from ui_style_system import check_style_system


def check_compact_header(page,width):
    check_style_system(page)
    if width>=1024:
        frame=page.locator('main').bounding_box()
        assert frame['width']<=960 and frame['x']>=48,frame
        assert abs(frame['x']-(width-frame['width'])/2)<1,frame
        for selector in ('.chart-frame:visible','.model-comparison-plot:visible'):
            for chart in page.locator(selector).all():
                assert chart.bounding_box()['width']<=720,chart.bounding_box()
        if page.locator('.metric-grid').count():
            assert page.locator('.comparison-metric').count()==3
            for pair in page.locator('.metric-pair').all():
                values=[n.bounding_box()['y'] for n in pair.locator('strong').all()]
                assert max(values)-min(values)<2,values
    assert page.locator('h1').count()==1
    assert page.locator('.site-brand,.hero-eyebrow').count()==0
    bar=page.locator('.sitebar').bounding_box()
    assert bar['height']<=64, f"Header must fit one compact row at {width}px: {bar}"
    links=page.locator('.site-nav a')
    assert links.all_text_contents()==['Painel','Dados e fontes']
    assert page.locator('.site-nav [aria-current="page"]').count()==1
    button=page.locator('#theme-toggle').bounding_box()
    assert button['height']>=44 and button['width']>=44
    assert button['x']+button['width']<=width
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    # Check actual rendered text contrast in both palettes, including muted navigation.
    assert page.evaluate("""() => {
      const rgb=s=>(s.match(/[0-9.]+/g)||[]).slice(0,3).map(Number);
      const luminance=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
      const bg=luminance(rgb(getComputedStyle(document.querySelector('.sitebar')).backgroundColor));
      return [...document.querySelectorAll('.site-nav a,#theme-toggle')].every(el=>{
        const style=getComputedStyle(el),color=luminance(rgb(style.color));
        const surface=style.backgroundColor==='rgba(0, 0, 0, 0)'?bg:luminance(rgb(style.backgroundColor));
        return (Math.max(color,surface)+.05)/(Math.min(color,surface)+.05)>=4.5;
      });
    }"""), 'Header text must retain readable contrast'


def main():
    from playwright.sync_api import sync_playwright
    home=fixture();comp=comparison_fixture(home['dashboard.json']['generated_at']);home['dashboard.json']['forecast_comparison']=comp
    details=datasets();details['data/forecast_comparison.json']=comp;details['data/latest.json']['generated_at']=comp['generated_at']
    OUTPUT.mkdir(exist_ok=True)
    with server() as url,sync_playwright() as pw:
        browser=pw.chromium.launch()
        for width in (320,390,768,1024,1440,1920):
            context=browser.new_context(viewport={'width':width,'height':1050},has_touch=width<800)
            def route(r):
                path=r.request.url.split('/data/')[-1].split('?')[0]
                data=home.get(path) if '/dados.html' not in (r.request.headers.get('referer') or '') else details.get('data/'+path)
                if path=='forecast_comparison.json':data=comp
                r.fulfill(content_type='application/json',body=json.dumps(data or {}))
            context.route('**/data/**',route)
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                page.goto(url);page.locator('#forecast-plot [data-chart-hit]').wait_for()
                assert page.locator('h1').inner_text()=='Tempo em Araquari'
                assert 'O tempo, com contexto' not in page.locator('body').inner_text()
                assert 'Valores essenciais' not in page.locator('body').inner_text()
                assert page.locator('.forecast-comparison-card').count()==0
                assert page.locator('#rain-window').input_value()=='24'
                assert page.locator('[data-mode]').count()==0
                assert page.locator('.shared-chart-controls').count()==0
                assert page.locator('#chart-range').is_visible()
                for period in ('72','168','240','24'):
                    page.locator('#chart-range').select_option(period)
                    assert page.locator('#observed-panel').is_visible() and page.locator('#forecast-panel').is_visible()
                    assert page.locator('#chart-range').input_value()==period
                    if period=='240':assert 'até 7 dias' in page.locator('#observed-caption').inner_text()
                probe=page.locator('#forecast-plot [data-chart-hit]');probe.scroll_into_view_if_needed();rect=probe.bounding_box()
                page.mouse.move(rect['x']+rect['width']*.2,rect['y']+rect['height']*.4)
                assert page.locator('#forecast-tooltip').is_visible()
                before=page.locator('#forecast-tooltip').inner_text()
                page.mouse.move(rect['x']+rect['width']*.7,rect['y']+rect['height']*.4)
                assert before!=page.locator('#forecast-tooltip').inner_text(), 'Hover must update the time and value'
                popup=page.locator('#forecast-tooltip').bounding_box();assert popup['x']>=0 and popup['x']+popup['width']<=width
                page.mouse.move(1,1)
                page.locator('#observed-variable').select_option('temperature_c')
                assert 'Chuva' in page.locator('#forecast-heading').inner_text()
                page.locator('#observed-variable').select_option('precipitation_mm')
                page.locator('#forecast-variable').select_option('gust_kmh')
                assert '24 h' in page.locator('#observed-heading').inner_text(), 'Forecast variable cannot change observations'
                chart=page.locator('#forecast-plot svg');chart.focus();page.keyboard.press('Home')
                assert page.locator('#forecast-tooltip').is_visible()
                assert 'km/h' in page.locator('#forecast-tooltip').inner_text()
                page.keyboard.press('ArrowRight');assert chart.locator('[data-chart-cursor]').get_attribute('visibility')=='visible'
                page.keyboard.press('Escape');assert not page.locator('#forecast-tooltip').is_visible()
                hit=chart.locator('[data-chart-hit]');hit.scroll_into_view_if_needed();box=hit.bounding_box()
                if width<800:page.touchscreen.tap(box['x']+box['width']*.45,box['y']+box['height']*.4)
                else:page.mouse.click(box['x']+box['width']*.45,box['y']+box['height']*.4)
                assert chart.get_attribute('data-pinned')=='true'
                reading=page.locator('#forecast-tooltip').inner_text();page.mouse.move(1,1)
                assert page.locator('#forecast-tooltip').is_visible()
                assert reading==page.locator('#forecast-tooltip').inner_text()
                chart.focus();page.keyboard.press('Escape');assert chart.get_attribute('data-pinned')=='false'
                page.locator('#forecast-variable').select_option('precipitation_mm')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                check_compact_header(page,width)
                page.screenshot(path=str(OUTPUT/f'essential-home-light-{width}.png'),full_page=True)
                page.locator('#theme-toggle').click();check_compact_header(page,width)
                page.screenshot(path=str(OUTPUT/f'essential-home-dark-{width}.png'),full_page=True)
                # Align default plot starts while the extra filters are closed.
                if width>=1024:
                    a,b=page.locator('#plot').bounding_box(),page.locator('#forecast-plot').bounding_box()
                    assert abs(a['y']-b['y'])<5,(a,b)
                # Reproduce many overlapping 24h windows without publishing synthetic data.
                original=home['observation_history.json']['records']
                stamp=datetime.fromisoformat(home['dashboard.json']['generated_at'].replace('Z','+00:00'))
                home['observation_history.json']['records']=[{**row,'observed_at':(stamp-timedelta(hours=i)).isoformat(),'rain_24h_mm':round(row['rain_24h_mm']+i/10,1)} for row in original for i in range(24)]
                page.reload();page.locator('#plot [data-chart-hit]').wait_for()
                assert page.locator('#plot .rain-interval').count()>=60
                for theme in ('light','dark'):
                    if page.locator('html').get_attribute('data-theme')!=theme:page.locator('#theme-toggle').click()
                    hit=page.locator('#plot [data-chart-hit]');hit.scroll_into_view_if_needed();box=hit.bounding_box()
                    page.mouse.move(box['x']+box['width']*.5,box['y']+box['height']*.4)
                    reading=page.locator('#chart-tooltip').inner_text()
                    for name in ('Rainha','Porto Grande','Centro'):assert reading.count(name+':')==1, reading
                    assert len(reading.splitlines())==5, reading
                    assert page.locator('#plot [data-chart-markers] circle').count()==3
                    if width<800:page.touchscreen.tap(box['x']+box['width']*.5,box['y']+box['height']*.4)
                    else:page.mouse.click(box['x']+box['width']*.5,box['y']+box['height']*.4)
                    popup=page.locator('#chart-tooltip').bounding_box()
                    assert popup['height']<=240,popup
                    assert popup['x']>=0 and popup['x']+popup['width']<=width,popup
                    page.screenshot(path=str(OUTPUT/f'compact-rain-tooltip-{theme}-{width}.png'))
                    page.locator('#plot svg').focus();page.keyboard.press('Escape')
                    page.keyboard.press('Home');before=page.locator('#chart-tooltip').inner_text()
                    page.keyboard.press('End');assert before!=page.locator('#chart-tooltip').inner_text()
                    page.keyboard.press('Escape')
                # The observed KPI must restore the corresponding local, 24h graph in place.
                page.locator('[data-focus="gust_kmh"]').click();before_url=page.url
                page.locator('[data-observed-focus]').click()
                assert page.url==before_url and '/dados.html' not in page.url
                assert page.locator('[data-observed-focus]').evaluate('(node) => node.tagName')=='BUTTON'
                assert page.locator('#observed-panel').is_visible() and page.locator('#forecast-panel').is_visible()
                assert page.locator('#observed-variable').input_value()=='precipitation_mm'
                assert page.locator('#rain-window').input_value()=='24'
                assert page.locator('#rain-scope').input_value()=='local'
                assert page.locator('#plot .station-bar').count()==3
                home['observation_history.json']['records']=original
                page.goto(url+'dados.html#chart-title');page.locator('#chart [data-chart-hit]').wait_for()
                if page.locator('html').get_attribute('data-theme')=='dark':page.locator('#theme-toggle').click()
                assert page.locator('h1').inner_text()=='Dados meteorológicos'
                page.locator('#chart svg').focus();page.keyboard.press('Home')
                assert page.locator('#detail-chart-tooltip').is_visible()
                assert 'Open-Meteo' in page.locator('#detail-chart-tooltip').inner_text()
                page.keyboard.press('Escape')
                assert not page.locator('#detail-chart-tooltip').is_visible()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                check_compact_header(page,width)
                page.screenshot(path=str(OUTPUT/f'essential-details-light-{width}.png'),full_page=True)
                page.locator('#theme-toggle').click();check_compact_header(page,width)
                page.screenshot(path=str(OUTPUT/f'essential-details-dark-{width}.png'),full_page=True)
                page.goto(url+'dados.html#model-comparison');page.locator('#model-comparison [data-chart-hit]').wait_for()
                page.locator('#model-comparison svg').focus();page.keyboard.press('Home')
                assert 'ECMWF' in page.locator('.comparison-tooltip').inner_text()
                assert page.locator('#model-comparison [data-chart-cursor]').count()==1
                if width==390:
                    record=details['data/places/araquari.json'];old=record['collected_at'];record['collected_at']='2000-01-01T00:00:00Z'
                    # A stale model must belong to the same collection as its
                    # summary; mixed-version rejection is tested separately.
                    summary=next(row for row in details['data/latest.json']['locations'] if row['id']=='araquari')
                    old_summary=summary['collected_at'];summary['collected_at']=record['collected_at']
                    page.goto(url+'dados.html#chart-title');page.reload()
                    page.get_by_text('Modelo desatualizado',exact=True).wait_for()
                    page.set_viewport_size({'width':389,'height':1050});page.wait_for_timeout(150)
                    assert page.locator('#chart svg').count()==0, 'Resizing cannot restore stale forecast'
                    record['collected_at']=old
                    summary['collected_at']=old_summary
                assert not errors,errors
            except Exception:
                print('Overflow debug',page.evaluate("[...document.querySelectorAll('body *')].map(el=>({tag:el.tagName,id:el.id,cls:typeof el.className==='string'?el.className:'',right:el.getBoundingClientRect().right,width:el.getBoundingClientRect().width})).filter(el=>el.width>0&&el.right>innerWidth+1).slice(-35)"));page.screenshot(path=str(OUTPUT/f'essential-failure-{width}.png'),full_page=True);raise
            finally:context.close()
        browser.close()
    print('Essential UX passed: compact header, navigation contrast, real data wiring, no slogans, independent variables, hover/touch/keyboard cursor, pin/Escape, shared identity, 320–1920px, desktop width limits and both themes.')

if __name__=='__main__':main()
