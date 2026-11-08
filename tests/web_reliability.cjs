// Run browser behavior with a small DOM harness; no network or third-party packages.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.textContent = ''; this.className = ''; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; this.textContent = ''; }
  setAttribute() {}
  addEventListener() {}
  get childElementCount() { return this.children.length; }
  get text() { return this.textContent + this.children.map(n => n.text ?? n.textContent ?? String(n)).join(' '); }
}
const elements = new Map();
const document = {
  getElementById(id) { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); },
  createElement(tag) { return new Element(tag); }, createElementNS(ns, tag) { return new Element(tag); },
  querySelectorAll() { return []; }, addEventListener() {}, hidden: false,
};
let clock = Date.parse('2026-11-06T12:30:00Z');
class Clock extends Date { static now() { return clock; } }
const context = vm.createContext({ document, Date: Clock, Intl, console, AbortController,
  setTimeout() { return 1; }, clearTimeout() {}, setInterval() {},
  fetch() { return new Promise(() => {}); } });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8'), context);
const run = code => vm.runInContext(code, context);
const text = id => document.getElementById(id).text;

assert.equal(run("freshAt('2026-11-06T12:00:00Z')"), true);
assert.equal(run("freshAt('2026-11-05T12:00:00Z')"), false);
assert.equal(run("freshAt('2026-11-07T12:00:00Z')"), false);
assert.equal(run("freshAt('invalid')"), false);
assert.equal(run("effectiveStatus('available', '2026-11-05T12:00:00Z')"), 'stale');
assert.equal(run("effectiveStatus('not_configured', null)"), 'not_configured');

run(`state.slug = 'araquari'; state.cemaden = {status:'available',checked_at:'2026-11-06T12:00:00Z',
locations:[{location_id:'araquari',status:'unavailable',diagnostic:'unavailable',stations:[]}]}; renderCemaden();`);
assert.match(text('cemaden-data'), /não respondeu/);
assert.doesNotMatch(text('cemaden-data'), /Nenhum pluviômetro/);

run(`state.cemaden.locations[0] = {location_id:'araquari',status:'available',stations:[
{code:'12345',observed_at:'2026-11-06T12:00:00Z',rain_24h_mm:17}]}; renderCemaden();`);
assert.match(text('cemaden-data'), /17,0 mm/);
clock = Date.parse('2026-11-06T20:00:00Z');
run('renderCemaden();');
assert.match(text('cemaden-data'), /desatualizadas/);
assert.doesNotMatch(text('cemaden-data'), /17,0 mm/);

clock = Date.parse('2026-11-06T12:30:00Z');
run(`state.cemadenSensors = {status:'available',checked_at:'2026-11-06T12:00:00Z',
locations:[{location_id:'araquari',stations:[{code:'12345',distance_km:2}]}],
stations:[{code:'12345',name:'Estação',municipality:'Araquari',readings:[
{sensor_id:60,sensor_name:'Temperatura',unit:'°C',value:25,observed_at:'2026-11-06T08:00:00Z'}]}]};
renderCemadenSensors();`);
assert.match(text('cemaden-sensors-data'), /vencidas/);
assert.doesNotMatch(text('cemaden-sensors-data'), /25,00/);

run(`state.overview = {generated_at:'2026-11-06T12:00:00Z',available_locations:0,total_locations:10,locations:[]};
refreshPublicationStatus();`);
assert.match(text('system-status'), /Open-Meteo indisponível/);
clock = Date.parse('2026-11-07T12:30:00Z');
run('refreshPublicationStatus();');
assert.match(text('system-status'), /desatualizada/);
clock = Date.parse('2026-11-06T12:30:00Z');
run(`state.observations = {status:'available',retrieved_at:'2026-11-06T12:00:00Z',
selection:{regional_radius_km:180},queried_stations:[],
locations:[{location_id:'araquari',status:'available',stations:[
{icao:'SBJV',distance_km:20,scope:'nearby_aerodrome'},
{icao:'SBFL',distance_km:145,scope:'regional_context_only'}]}],
stations:[{icao:'SBJV',name:'Joinville',observed_at:'2026-11-06T12:00:00Z',temperature_c:24},
{icao:'SBFL',name:'Florianópolis',observed_at:'2026-11-06T12:00:00Z',temperature_c:25}]};
renderObservations();`);
assert.match(text('observed-data'), /Joinville/);
assert.match(text('observed-data'), /Florianópolis/);
assert.match(text('observed-data'), /Contexto regional/);
clock = Date.parse('2026-11-07T12:30:00Z');
run('renderObservations();');
assert.doesNotMatch(text('observed-data'), /25,0/);
run(`appendStationCards(document.getElementById('expanded-test'),
Array.from({length:25}, (_, i)=>child('article','', 'Estação '+i)));`);
assert.match(text('expanded-test'), /Estação 24/);
assert.match(text('expanded-test'), /Ver mais 19 estações/);
clock = Date.parse('2026-11-06T12:30:00Z');
run(`state.alignment={checked_at:'2026-11-06T12:00:00Z',spatial_radius_km:25,groups:{'norte-sc':'Norte de SC'},locations:[
{location_id:'araquari',territorial_group:'norte-sc',sample_point:{latitude:-26.375,longitude:-48.721},
model:{reference_at:'2026-11-06T12:00:00Z'},cemaden_local_rain:{station_count:4},cemaden_nearby_count:5,metar_nearby_count:1,
cemaden_candidates:[{code:'12345',sample_distance_km:2,reference_at:'2026-11-06T12:00:00Z'}],
metar_candidates:[{code:'SBJV',sample_distance_km:20,reference_at:'2026-11-06T12:00:00Z'}],
candidate_triads:[{cemaden_code:'12345',metar_code:'SBJV',station_distance_km:18,time_gap_minutes:0,
time_window_aligned:true,model_grid_proximity_verified:false,potential_common_variables:[],comparison_ready:false}]}]};
renderTerritorialAlignment();`);
assert.match(text('alignment-data'), /Ainda não há variável comum confirmada/);
assert.match(text('alignment-data'), /Não é uma comparação de precisão/);
assert.match(text('alignment-data'), /grade do modelo ainda não confirmada/);
clock = Date.parse('2026-11-07T12:30:00Z');
run('renderTerritorialAlignment();');
assert.match(text('alignment-data'), /referências vencidas/);
console.log('Browser reliability scenarios passed: freshness, municipal failure, expired readings, partial publication.');

// The institutional summary must stay on Araquari while another city is selected.
clock = Date.parse('2026-11-06T12:30:00Z');
run(`state.slug = 'joinville'; state.analysis = {
  generated_at:'2026-11-06T12:00:00Z', primary_location_id:'araquari', locations:[
  {location_id:'araquari', name:'Araquari', role:'primary_ifc_reference',status:'evidence_available',valid_until:'2026-11-06T15:00:00Z',
   observed_rain:{status:'no_recent_data',stations:[]},
   forecast:{status:'available',rain:{status:'complete',total_mm:12,start_at:'2026-11-06T12:00:00Z',end_at:'2026-11-07T12:00:00Z'},rain_peaks:[],wind:{}},
   official_notices:{status:'unavailable',notices:[]},
   suggestions:[{id:'rain_timing',text:'Pode ser pertinente avaliar atividades externas.',evidence:'forecast.rain_peaks',scope:'Araquari',limitation:'Condições locais desconhecidas.'}],limitations:[]},
  {location_id:'joinville',name:'Joinville',role:'complementary_regional_context',valid_until:'2026-11-06T15:00:00Z',
   forecast:{status:'available',rain:{status:'complete',total_mm:99,start_at:'2026-11-06T12:00:00Z',end_at:'2026-11-07T12:00:00Z'}},official_notices:{status:'available',notices:[]}}
]}; renderSynthesis();`);
assert.match(text('synthesis-data'), /12,0 mm previstos/);
assert.doesNotMatch(text('synthesis-data'), /99,0 mm previstos/);
assert.match(text('regional-synthesis'), /99,0 mm previstos/);
assert.match(text('synthesis-data'), /Sem leitura recente válida/);
assert.match(text('synthesis-data'), /Pode ser pertinente avaliar atividades externas/);
clock = Date.parse('2026-11-06T15:01:00Z');
run('renderSynthesis();');
assert.match(text('synthesis-data'), /sugestões foram retiradas/);
assert.doesNotMatch(text('synthesis-data'), /Pode ser pertinente avaliar atividades externas/);
assert.doesNotMatch(text('regional-synthesis'), /99,0 mm previstos/);
clock = Date.parse('2026-11-06T12:30:00Z');
run(`state.analysis.locations = state.analysis.locations.filter(row => row.location_id !== 'araquari'); renderSynthesis();`);
assert.match(text('synthesis-data'), /Não há síntese verificável de Araquari/);
assert.doesNotMatch(text('synthesis-data'), /99,0/);
run(`state.slug='araquari'; state.cptec={status:'available',checked_at:'2026-11-06T12:00:00Z',locations:[
 {location_id:'araquari',status:'available',nearest_cptec_locality:'Araquari',days:[{day:'2026-11-06',maximum_c:30,minimum_c:20}]}]};
 state.detail={collected_at:'2026-11-06T12:00:00Z',current:{time:'2026-11-06T12:00:00Z'},daily:[{time:'2026-11-06',temp_max_c:27}]};renderCptec();`);
assert.match(text('cptec-data'), /Limites do dia CPTEC não conciliados/);
assert.doesNotMatch(text('cptec-data'), /Diferença máx/);
console.log('Advisory scenarios passed: Araquari priority, regional complement, expiry, missing primary, daily-period compatibility.');

(async () => {
  clock = Date.parse('2026-11-06T12:30:00Z');
  context.fetch = async url => ({ok:url === './data/latest.json', status:404,
    async json() { return {schema_version:1,generated_at:'2026-11-06T12:00:00Z',available_locations:1,total_locations:2,
      locations:[{id:'araquari',name:'Araquari',state:'SC',status:'unavailable',featured:true},
                 {id:'joinville',name:'Joinville',state:'SC',status:'available',current:{temperature_c:23,time:'2026-11-06T12:00:00Z'}}]}; }});
  run('state.slug = null;');
  await run('boot()');
  assert.equal(run('state.slug'), 'araquari');
  assert.match(text('place-title'), /Araquari/);
  assert.match(text('place-subtitle'), /Referência principal/);
  console.log('Initial selection passed: Araquari stays primary during its model outage.');
  // A CDN may serve a new summary alongside the previous municipal file.
  run("state.overview.locations[0].status='available';state.overview.locations[0].collected_at='2026-11-06T12:00:00Z';");
  const municipal={location:{id:'araquari',latitude:-26.375,longitude:-48.721},source:{id:'open-meteo'},
    collected_at:'2026-11-06T12:00:00Z',current:{time:'2026-11-06T12:00:00Z',temperature_c:24},hourly:[],daily:[]};
  let requests=0;
  context.fetch=async()=>({ok:true,json:async()=>({...municipal,collected_at:++requests===1?'2026-11-06T11:00:00Z':municipal.collected_at})});
  await run("selectLocation('araquari')");
  assert.equal(requests,2);assert.equal(run('state.detail.collected_at'),municipal.collected_at);
  assert.equal(run('state.detailRetry'),false);
  assert.match(text('temp'),/24,0/);
  const expectedErrors=[];context.console={...console,error:(...args)=>expectedErrors.push(args)};
  context.fetch=async()=>{throw Error('simulated offline');};
  await run("selectLocation('araquari')");
  assert.equal(run('state.detail.collected_at'),municipal.collected_at);assert.match(text('temp'),/24,0/);
  assert.equal(run('state.detailRetry'),true);
  run("state.overview.locations[0].collected_at='2026-11-06T13:00:00Z';");
  requests=0;context.fetch=async()=>({ok:true,json:async()=>{requests++;return municipal;}});
  await run("selectLocation('araquari')");
  assert.equal(requests,2);assert.equal(run('state.detail'),null);assert.equal(text('temp'),'--');
  context.fetch=async()=>({ok:true,json:async()=>({...municipal,collected_at:'2026-11-06T13:00:00Z',current:null})});
  await run("selectLocation('araquari')");
  assert.equal(run('state.detail'),null);assert.equal(run('state.detailRetry'),true);
  context.fetch=async()=>({ok:true,json:async()=>({schema_version:1,generated_at:'2026-11-06T11:00:00Z',locations:[]})});
  await run('boot()');
  assert.equal(run('state.overview.generated_at'),'2026-11-06T12:00:00Z');
  context.fetch=async()=>({ok:true,json:async()=>({schema_version:1,generated_at:'2030-01-01T00:00:00Z',locations:[]})});
  await run('boot()');
  assert.equal(run('state.overview.generated_at'),'2026-11-06T12:00:00Z');
  assert.equal(expectedErrors.length,5);
  console.log('Publication consistency passed: municipal version mismatch retry, same-version offline preservation, no mixing of old detail/new summary and no publication rollback.');
})().catch(err => { console.error(err); process.exitCode = 1; });

// Artifact version checks do not substitute for the source's own time limits.
assert.equal(run("publicationMatches({schema_version:1}, {generated_at:'v1'})"),true);
assert.equal(run("publicationMatches({fixture_mode:true}, {generated_at:'v1'})"),false);
assert.equal(run("publicationMatches({publication_at:'v1'}, {generated_at:'v1',publication_at:'v1'})"),true);
assert.equal(run("publicationMatches({publication_at:'v0'}, {generated_at:'v1',publication_at:'v1'})"),false);
assert.equal(run("publicationMatches({}, {generated_at:'v1',publication_at:'v1'})"),false);
