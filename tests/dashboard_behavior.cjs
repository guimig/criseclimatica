'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {fresh,dashboardCurrent,protocolCurrent,getChartSeries}=require('../web/dashboard.js');
const now=Date.parse('2026-11-06T20:30:00Z');
const data={generated_at:'2026-11-06T20:00:00Z',valid_until:'2026-11-06T23:00:00Z',assessment:{valid_until:'2026-11-06T22:00:00Z'},forecast:{start_at:'2026-11-06T20:00:00Z'},forecast_series:[]};
assert.equal(dashboardCurrent(data,now),true);
assert.equal(protocolCurrent(data,now),true);
assert.equal(protocolCurrent(data,Date.parse('2026-11-06T22:00:01Z')),false);
assert.equal(dashboardCurrent(data,Date.parse('2026-11-07T20:30:00Z')),false);
assert.equal(dashboardCurrent(null,now),false);
assert.equal(fresh('not-a-date',3,now),false);
assert.equal(fresh('2026-11-07T20:00:00Z',3,now),false);
for(let i=0;i<=240;i++)data.forecast_series.push({time:new Date(Date.parse(data.forecast.start_at)+i*3600000).toISOString(),precipitation_mm:i===4?null:1,temperature_c:20,wind_kmh:10,gust_kmh:20});
const rain=getChartSeries(data,null,'forecast','precipitation_mm',24,now)[0];
assert.equal(rain.points.length,24);
assert.equal(rain.points[0].time,'2026-11-06T21:00:00.000Z');
assert.equal(rain.points[3].value,null);
assert.equal(getChartSeries(data,null,'forecast','temperature_c',24,now)[0].points.length,24);
assert.equal(getChartSeries(data,null,'forecast','gust_kmh',72,now).length,2);
const history={records:[{source:'cemaden-rain',station:'A',observed_at:'2026-11-06T20:00:00Z',rain_24h_mm:15},
 {source:'cemaden-rain',station:'B',observed_at:'2026-11-06T20:00:00Z',rain_24h_mm:100},
 {source:'cemaden-rain',station:'A',observed_at:'2026-10-01T20:00:00Z',rain_24h_mm:1000}]};
const observed=getChartSeries(data,history,'observed','precipitation_mm',24,now,'rain_24h_mm');
assert.equal(observed.length,2);assert.equal(observed[0].points.length,1);
assert.equal(observed[0].points[0].value,15);assert.equal(observed[1].points[0].value,100);
assert.equal(getChartSeries(data,history,'observed','temperature_c',24,now).length,0);
const html=fs.readFileSync(path.join(__dirname,'../web/index.html'),'utf8');
const js=fs.readFileSync(path.join(__dirname,'../web/dashboard.js'),'utf8');
const ids=new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]));
for(const match of js.matchAll(/\bel\('([a-z][\w-]*)'\)/g))assert.ok(ids.has(match[1]),`Missing DOM id: ${match[1]}`);
assert.match(html,/Projeto independente/);assert.doesNotMatch(html,/FOCO PRINCIPAL · IFC/);
assert.match(html,/href="\.\/dados.html"/);
assert.match(js,/ArrowRight/);assert.match(js,/pointermove/);assert.match(js,/showModal/);
console.log('Dashboard behavior passed: expiry, primary source, hourly intervals, separate stations, missing values, controls and DOM contract.');
const {preference}=require('../web/theme.js');
assert.equal(preference({getItem(){return 'dark';}},false),'dark');
assert.equal(preference({getItem(){return 'light';}},true),'light');
assert.equal(preference({getItem(){throw new Error('Storage blocked');}},true),'dark');
assert.equal(preference({getItem(){return 'unknown';}},false),'light');
const mixedHistory={records:[{source:'cemaden-rain',station:'A',observed_at:'2026-11-06T19:00:00Z',rain_1h_mm:2,rain_24h_mm:80}]};
const contextSeries=getChartSeries(data,mixedHistory,'context','precipitation_mm',24,now);
assert.equal(contextSeries.find(s=>s.kind==='observation').points[0].value,2);
assert.ok(contextSeries.find(s=>s.kind==='forecast'));
assert.ok(contextSeries.find(s=>s.kind==='forecast').points.every(p=>Date.parse(p.time)>=Date.parse(data.generated_at)));
assert.match(html,/id="theme-toggle"/);assert.match(html,/id="memory"/);
assert.match(js,/Monitoramento parcial/);assert.doesNotMatch(js,/:'Em avaliação'/);
console.log('Theme and retrospective scenarios passed: persisted preference, blocked storage, comparable hourly rain, forecast separation, neutral wording.');
const {effectiveAssessment}=require('../web/dashboard.js');
const short={...data,assessment:{valid_until:'2026-11-06T20:10:00Z',suggested_level:'laranja',base_assessment:{valid_until:'2026-11-06T23:00:00Z',suggested_level:null}}};
assert.equal(dashboardCurrent(short,now),true);
assert.equal(effectiveAssessment(short,now).monitoring_state,'partial');
short.assessment.base_assessment.suggested_level='amarelo';
assert.equal(effectiveAssessment(short,now).suggested_level,'amarelo');
console.log('Short-reference expiry passed: valid forecasts remain available and primary evidence is preserved.');

// Hourly accumulations remain intervals, including the partially elapsed model hour.
const {comparableReadings,pointDescription}=require('../web/dashboard.js');
const irregular={...data,generated_at:'2026-11-06T20:29:00Z'};
const currentHour=getChartSeries(irregular,mixedHistory,'context','precipitation_mm',24,now);
const next=currentHour.find(s=>s.kind==='forecast').points[0];
assert.equal(next.start_at,'2026-11-06T20:00:00.000Z');
assert.equal(next.time,'2026-11-06T21:00:00.000Z');
assert.match(pointDescription(currentHour.find(s=>s.kind==='forecast'),next,'mm',Date.parse(irregular.generated_at)),/hora em curso/);
const hourly=getChartSeries(irregular,mixedHistory,'observed','precipitation_mm',24,now);
assert.equal(hourly[0].points[0].value,2);
assert.equal(hourly[0].points[0].start_at,'2026-11-06T18:00:00.000Z');
assert.equal(getChartSeries(irregular,mixedHistory,'observed','precipitation_mm',24,now,'rain_24h_mm')[0].points[0].value,80);
assert.deepEqual(getChartSeries(null,null,'observed','precipitation_mm',24,now),[]);
const aligned={records:[
 {source:'cemaden-rain',station:'A',observed_at:'2026-11-06T20:20:00Z',rain_1h_mm:0},
 {source:'cemaden-rain',station:'B',observed_at:'2026-11-06T20:20:00Z',rain_1h_mm:8},
 {source:'cemaden-rain',station:'C',observed_at:'2026-11-06T20:10:00Z',rain_1h_mm:3.5},
 {source:'cemaden-rain',station:'D',observed_at:'2026-11-06T21:00:00Z',rain_1h_mm:99}]};
const stationSeries=getChartSeries(irregular,aligned,'observed','precipitation_mm',24,now);
assert.equal(stationSeries.length,3); // future readings are not historical samples
const comparison=comparableReadings(stationSeries,Date.parse(irregular.generated_at),1);
assert.equal(comparison.cohort.length,2);
assert.deepEqual(comparison.cohort.map(r=>r.point.value),[0,8]);
assert.equal(comparableReadings(stationSeries,Date.parse('2026-11-06T22:29:00Z'),1).cohort.length,0);
console.log('Separate chart data passed: hourly windows, in-progress forecast hour, exact comparison cohorts, old/future/missing readings.');

// Exercise the real SVG renderer without network or a browser dependency.
const vm=require('node:vm');
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.attributes={};this.listeners={};this.style={};this.dataset={};this.hidden=false;this.value='';this.textContent='';this.classList={toggle(){}};}
 append(...children){this.children.push(...children);}
 replaceChildren(...children){this.children=children;this.textContent='';}
 setAttribute(k,v){this.attributes[k]=String(v);}
 addEventListener(k,fn){this.listeners[k]=fn;}
 getBoundingClientRect(){return {left:0,width:600};}
}
const elements=new Map([...ids].map(id=>[id,new Element('div')]));
const context=vm.createContext({module:{exports:{}},console,Intl,Date,URL,location:{href:'https://guimig.github.io/criseclimatica/'}});
vm.runInContext(js,context); // No document yet: avoid application boot and network.
context.document={querySelectorAll:()=>[],getElementById:id=>elements.get(id),createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t),documentElement:{dataset:{theme:'dark'}}};
context.fixture=irregular;context.stationHistory=aligned;
vm.runInContext('panel.data=fixture;panel.history=stationHistory;panel.observedView="timeline";renderChart()',context);
function descendants(n){return [n,...n.children.flatMap(descendants)];}
function plotNodes(id,tag){return descendants(elements.get(id)).filter(n=>n.tag===tag);}
assert.equal(elements.get('observed-panel').hidden,false);assert.equal(elements.get('forecast-panel').hidden,false);
assert.equal(plotNodes('plot','svg').length,1);assert.equal(plotNodes('forecast-plot','svg').length,1);
assert.equal(plotNodes('plot','path').length,0); // never connect sparse rain accumulations
assert.equal(plotNodes('plot','rect').length,3);
assert.equal(plotNodes('forecast-plot','rect').length,23); // null is a gap, not a zero bar
assert.match(elements.get('station-comparison').textContent,/2 de 3 estações/);
assert.doesNotMatch(plotNodes('plot','text').map(n=>n.textContent).join(' '),/Publicação/);
assert.equal(plotNodes('plot','text')[0].textContent,plotNodes('forecast-plot','text')[0].textContent);
const observedSvg=plotNodes('plot','svg')[0];
observedSvg.listeners.keydown({key:'Home',preventDefault(){}});
assert.match(elements.get('chart-tooltip').textContent,/acumulado de 1 h/);
observedSvg.listeners.pointermove({clientX:50});
assert.match(elements.get('chart-tooltip').textContent,/Sem intervalo registrado/);
vm.runInContext("panel.station='cemaden-rain:B';renderChart()",context);
assert.equal(plotNodes('plot','rect').length,1);
vm.runInContext("panel.station='all';renderChart();renderChart()",context);
assert.equal(plotNodes('plot','svg').length,1); // repeated rendering stays idempotent
vm.runInContext("panel.mode='forecast';renderChart()",context);
assert.equal(elements.get('observed-panel').hidden,true);
vm.runInContext("panel.mode='context';panel.rainWindow=24;renderChart()",context);
assert.match(elements.get('chart-caption').textContent,/Escalas e acumulados diferentes/);
vm.runInContext("panel.variable='temperature_c';panel.history=null;renderChart()",context);
assert.equal(plotNodes('plot','svg').length,0);assert.equal(plotNodes('forecast-plot','svg').length,1);
vm.runInContext('panel.data=null;panel.history=null;renderChart()',context);
assert.equal(plotNodes('forecast-plot','svg').length,0);
console.log('SVG rendering passed: two panels, real rain intervals, no interpolation, exact cohorts, keyboard, missing-hour tooltip, station filter, repeated/empty renders.');

const {riskPresentation,stationName,chartScale}=require('../web/dashboard.js');
const normal={...data,assessment:{valid_until:data.valid_until,suggested_level:null,monitoring_state:'routine',numeric_support:{core_complete:true,maximum_band:0,signals:[{band:0}]}}};
assert.equal(riskPresentation(normal,now).color,'verde');
assert.match(riskPresentation(normal,now).title,/Normalidade nos dados/);
assert.equal(normal.assessment.suggested_level,null); // descriptive green is not an official classification
assert.equal(riskPresentation({...normal,assessment:{...normal.assessment,numeric_support:{core_complete:false,maximum_band:0}}},now).color,'neutral');
assert.equal(riskPresentation({...normal,assessment:{...normal.assessment,monitoring_state:'partial'}},now).color,'neutral');
assert.equal(riskPresentation(normal,Date.parse('2026-11-10T20:00:00Z')).color,'neutral');
for(const level of ['azul','amarelo','laranja','vermelho','roxo']){
 const result=riskPresentation({...normal,assessment:{...normal.assessment,suggested_level:level}},now);
 assert.equal(result.color,level);assert.equal(result.active,level);
}
const signal={station:'A',source:'cemaden',variable:'rain_1h_mm',value:20.8,unit:'mm',kind:'observation',band:1,start_at:'2026-11-06T19:00:00Z',end_at:'2026-11-06T20:00:00Z'};
const attention={...normal,station_catalog:[{source:'cemaden-rain',station:'A',name:'Porto Grande'}],assessment:{...normal.assessment,monitoring_state:'technical_attention',numeric_support:{core_complete:true,maximum_band:1,signals:[signal],coincidences:[]}}};
const reading=riskPresentation(attention,now);
assert.equal(reading.color,'amarelo');assert.equal(reading.active,null);
assert.match(reading.reason,/Porto Grande/);assert.match(reading.reason,/20,8/);assert.doesNotMatch(reading.reason,/superaç|coincidência/);
assert.equal(stationName({name:'Cemaden Rainha',station:'420130701A'}),'Rainha');
assert.equal(stationName({name:'420130701A',station:'420130701A'},'Estação 1'),'Estação 1');
assert.equal(chartScale([0,20.8]).step,5);assert.ok(chartScale([0,0]).high>0);
context.fixture={...irregular,station_catalog:[{source:'cemaden-rain',station:'A',name:'Rainha',municipality:'Araquari'},{source:'cemaden-rain',station:'B',name:'Porto Grande',municipality:'Araquari'},{source:'cemaden-rain',station:'C',name:'Centro',municipality:'Araquari'}],regional_rain_context:{radius_km:40,stations:[{source:'cemaden-rain',station:'N',name:'Pirabeiraba',municipality:'Joinville'}],records:[{source:'cemaden-rain',station:'N',observed_at:'2026-11-06T20:20:00Z',rain_1h_mm:5}]}};
vm.runInContext('panel.data=fixture;panel.history=stationHistory;panel.mode="context";panel.variable="precipitation_mm";panel.rainWindow=1;panel.observedView="auto";renderChart()',context);
assert.equal(plotNodes('plot','rect').filter(n=>n.attributes.class==='station-bar').length,3);
assert.equal(plotNodes('plot','path').length,0);
assert.match(plotNodes('plot','text').map(n=>n.textContent).join(' '),/Rainha/);
assert.doesNotMatch(plotNodes('plot','text').map(n=>n.textContent).join(' '),/cemaden|4201307/i);
vm.runInContext('panel.scope="nearby";renderChart()',context);
assert.equal(plotNodes('plot','rect').filter(n=>n.attributes.class==='station-bar').length,1);
assert.match(elements.get('station-coverage').textContent,/não entram nos indicadores locais/);
assert.match(plotNodes('plot','text').map(n=>n.textContent).join(' '),/Joinville/);
assert.ok(!plotNodes('plot','text').map(n=>n.textContent).join(' ').includes('Rainha'));
vm.runInContext('panel.scope="local";renderChart()',context);
assert.equal(plotNodes('plot','rect').filter(n=>n.attributes.class==='station-bar').length,3);
assert.match(html,/aria-haspopup="dialog"/);assert.equal([...html.matchAll(/data-risk-level=/g)].length,6);
console.log('UX scenarios passed: descriptive normality vs missing data, six colors, explicit signals, human station names, sparse history, optional verified surroundings and local isolation.');
