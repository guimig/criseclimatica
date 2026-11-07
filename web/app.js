'use strict';

const state = { analysis: null, alignment: null, coverage: null, bootId: 0, overview: null, detail: null, stations: null, history: null, alerts: null, observations: null, rain: null, nasa: null, cemaden: null, cemadenSensors: null, cptec: null, defesa: null, archive: null, noticeArchive: null, epagriGeo: null, epagriNotices: null, epagriBulletins: null, regionalQuality: null, slug: null, metric: 'temperature_c', requestId: 0 };
const $ = (id) => document.getElementById(id);
const tz = 'America/Sao_Paulo';
const units = { temperature_c: '\u00b0C', precipitation_mm: 'mm', gust_kmh: 'km/h' };
const descriptors = {
  temperature_c: 'Temperatura prevista',
  precipitation_mm: 'Precipita\u00e7\u00e3o prevista',
  gust_kmh: 'Rajadas previstas'
};

function value(number, fraction = 0) {
  return Number.isFinite(number) ? Number(number).toLocaleString('pt-BR', { maximumFractionDigits: fraction, minimumFractionDigits: fraction }) : '--';
}
function datetime(iso, options = {}) {
  if (!iso || Number.isNaN(Date.parse(iso))) return '--';
  return new Intl.DateTimeFormat('pt-BR', { timeZone: tz, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', ...options }).format(new Date(iso));
}
function freshAt(iso, maxHours = 6, now = Date.now()) {
  const stamp = typeof iso === 'string' ? Date.parse(iso) : NaN;
  const age = now - stamp;
  return Number.isFinite(age) && age >= -10 * 60000 && age <= maxHours * 3600000;
}
function effectiveStatus(status, stamp, maxHours = 6) {
  return ['available', 'cached', 'partial'].includes(status) && !freshAt(stamp, maxHours) ? 'stale' : status;
}
function refreshPublicationStatus() {
  if (!state.overview) return;
  const current = freshAt(state.overview.generated_at, 8);
  const count = state.overview.available_locations;
  const partial = count < state.overview.total_locations;
  setStatus(!current ? 'Publicação desatualizada: confira os horários das fontes' :
    !count ? 'Previsão Open-Meteo indisponível; consulte as outras fontes abaixo' :
    partial ? 'Publicação parcial: confira a cobertura por fonte' : 'Dados de modelo disponíveis',
    !current || partial ? 'warning' : 'ok');
}
function weatherInfo(code) {
  if (!Number.isFinite(code)) return { label: 'Indispon\u00edvel', symbol: '\u25cb' };
  if (code === 0) return { label: 'C\u00e9u limpo', symbol: '\u2600' };
  if (code <= 3) return { label: 'Parcialmente nublado', symbol: '\u26c5' };
  if ([45, 48].includes(code)) return { label: 'N\u00e9voa', symbol: '\u2601' };
  if (code >= 51 && code <= 67) return { label: 'Chuva', symbol: '\u2614' };
  if (code >= 71 && code <= 77) return { label: 'Neve', symbol: '\u2744' };
  if (code >= 80 && code <= 82) return { label: 'Pancadas de chuva', symbol: '\u2614' };
  if (code >= 95) return { label: 'Trovoadas', symbol: '\u26c8' };
  return { label: 'C\u00e9u vari\u00e1vel', symbol: '\u2601' };
}
function child(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function clear(element) { element.replaceChildren(); }
function appendStationCards(target, cards, previewCount = 6) {
  for (const card of cards.slice(0, previewCount)) target.append(card);
  if (cards.length > previewCount) {
    const more = child('details', 'more-stations');
    more.append(child('summary', '', `Ver mais ${cards.length - previewCount} estações (${cards.length} no total)`));
    for (const card of cards.slice(previewCount)) more.append(card);
    target.append(more);
  }
}
async function readJson(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(url, { cache: 'no-store', signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } finally { clearTimeout(timeout); }
}
function setStatus(message, kind) {
  $('system-status').textContent = message;
  $('signal').className = 'signal' + (kind ? ' ' + kind : '');
}
function synthesisCurrent(row, feed = state.analysis) {
  return Boolean(row && freshAt(feed?.generated_at, 3) && Number.isFinite(Date.parse(row.valid_until)) && Date.now() < Date.parse(row.valid_until));
}
function rainDescription(row) {
  const rain = row?.forecast?.rain;
  return row?.forecast?.status === 'available' && rain?.status === 'complete'
    ? `${value(rain.total_mm, 1)} mm previstos · ${datetime(rain.start_at)} a ${datetime(rain.end_at)}`
    : `Previsão de chuva ${row?.forecast?.status === 'stale' ? 'desatualizada' : 'incompleta ou indisponível'}`;
}
function renderSynthesis() {
  const target = $('synthesis-data'), regional = $('regional-synthesis');
  clear(target); clear(regional);
  const feed = state.analysis;
  const primary = feed?.locations?.find(row => row.location_id === 'araquari' && row.role === 'primary_ifc_reference');
  if (!primary) {
    $('synthesis-status').textContent = 'Síntese indisponível';
    target.append(child('p', 'alert-unknown', 'Não há síntese verificável de Araquari nesta publicação. Consulte os dados detalhados e os canais oficiais; dados de outros municípios não substituem essa ausência.'));
    $('synthesis-updated').textContent = 'Sugestões indisponíveis. Ausência de informação não comprova ausência de condições adversas.';
    return;
  }
  const current = synthesisCurrent(primary);
  $('synthesis-status').textContent = !current ? 'Referências vencidas · reavaliar' : primary.status === 'insufficient_evidence' ? 'Evidências insuficientes' : 'Leitura consultiva';
  if (!current) {
    target.append(child('p', 'alert-unknown', 'As referências desta síntese perderam validade. As sugestões foram retiradas; consulte novas atualizações e os canais oficiais. Isso não indica melhora das condições.'));
  } else {
    const grid = child('div', 'synthesis-grid');
    const antecedent = child('article', 'synthesis-card observed-evidence');
    antecedent.append(child('span', 'section-kicker', 'OBSERVAÇÃO · ANTECEDENTES'), child('h3', '', 'Chuva medida em Araquari'));
    const gauges = primary.observed_rain?.stations || [];
    if (primary.observed_rain?.status === 'available' && gauges.length) {
      const with24 = gauges.filter(s => Number.isFinite(s.rain_24h_mm));
      const nonzero = with24.filter(s => s.rain_24h_mm > 0).length;
      antecedent.append(child('p', '', `${gauges.length} estação(ões) com acumulados válidos. ${with24.length ? `${nonzero} de ${with24.length} com chuva medida na janela de 24 h.` : 'Janela de 24 h não disponível.'}`));
      antecedent.append(child('small', '', 'Acumulados por estação, sem soma entre janelas ou média municipal.'));
    } else {
      const status = primary.observed_rain?.status;
      antecedent.append(child('p', '', status === 'stale' ? 'Acumulados desatualizados.' : ['no_recent_data', 'no_valid_recent_readings'].includes(status) ? 'Sem leitura recente válida.' : 'Fonte local indisponível ou sem acesso nesta publicação.'));
      antecedent.append(child('small', '', 'Isso não significa chuva zero.'));
    }
    const forecast = child('article', 'synthesis-card forecast-evidence');
    forecast.append(child('span', 'section-kicker', 'PREVISÃO · OPEN-METEO'), child('h3', '', 'Próximas 24 horas'), child('p', '', rainDescription(primary)));
    const peak = primary.forecast?.rain_peaks?.find(row => row.hours === 3);
    if (peak) forecast.append(child('p', '', `Maior janela de 3 h: ${value(peak.total_mm, 1)} mm · ${datetime(peak.start_at)} a ${datetime(peak.end_at)}.`));
    const gust = primary.forecast?.wind?.gust_kmh;
    if (Number.isFinite(gust?.maximum)) forecast.append(child('p', '', `Maior rajada prevista: ${value(gust.maximum, 1)} km/h · ${datetime(gust.at)}.`));
    const notices = child('article', 'synthesis-card official-evidence');
    notices.append(child('span', 'section-kicker', 'AVISO OFICIAL · INMET'), child('h3', '', 'Referência municipal'));
    const official = primary.official_notices;
    if (official?.status === 'available') {
      notices.append(child('p', '', official.notices?.length ? `${official.notices.length} aviso(s) retornado(s) para Araquari.` : 'Nenhum aviso retornado na consulta; isso não comprova ausência de condições adversas.'));
      for (const notice of (official.notices || []).slice(0, 2)) notices.append(child('p', '', `${notice.type} · ${notice.severity} · ${notice.window_as_reported || 'validade não informada'}. ${notice.temporal_relation === 'overlaps_forecast' ? 'Janela informada coincide com a previsão.' : notice.temporal_relation === 'outside_forecast_window' ? 'Janela informada fora das 24 h analisadas.' : 'Coincidência temporal não verificada.'}`));
    } else notices.append(child('p', '', 'Avisos indisponíveis ou desatualizados. Consulte o INMET e a Defesa Civil.'));
    grid.append(antecedent, forecast, notices); target.append(grid);
    const suggestions = child('div', 'synthesis-suggestions');
    suggestions.append(child('h3', '', 'Possibilidades para avaliação'));
    const list = primary.suggestions || [];
    if (!list.length) suggestions.append(child('p', '', 'As informações disponíveis não sustentam uma sugestão específica. Isso não equivale a uma indicação de segurança.'));
    const ordered = [...list].sort((a, b) => (a.id === 'official_notice' ? -1 : 0) - (b.id === 'official_notice' ? -1 : 0));
    const appendSuggestion = (entry, host) => {
      const item = child('p', 'synthesis-suggestion', entry.text);
      item.append(child('small', '', `${entry.limitation} · Evidência: ${entry.evidence} · ${entry.scope}.`)); host.append(item);
    };
    ordered.slice(0, 3).forEach(s => appendSuggestion(s, suggestions));
    if (ordered.length > 3) {
      const more = child('details', 'synthesis-evidence'); more.append(child('summary', '', 'Outras possibilidades fundamentadas'));
      ordered.slice(3).forEach(s => appendSuggestion(s, more)); suggestions.append(more);
    }
    target.append(suggestions);
  }
  const evidence = child('details', 'synthesis-evidence');
  evidence.append(child('summary', '', 'Evidências, períodos e limitações de Araquari'));
  const rain = primary.observed_rain;
  evidence.append(child('p', 'analysis-foot', `Consulta Cemaden: ${datetime(rain?.checked_at)} · ${rain?.status || 'indisponível'}. Dados abaixo são referências da publicação, sem garantia de atualidade após o vencimento.`));
  for (const gauge of rain?.stations || []) {
    const readings = [1, 3, 6, 12, 24, 48, 72].filter(h => Number.isFinite(gauge[`rain_${h}h_mm`])).map(h => `${h} h: ${value(gauge[`rain_${h}h_mm`], 1)} mm`).join(' · ');
    evidence.append(child('p', '', `Cemaden ${gauge.code} · ${datetime(gauge.observed_at)} · ${readings}.`));
  }
  for (const observation of primary.recent_observations || []) {
    const valid = Date.now() < Date.parse(observation.valid_until);
    evidence.append(child('p', '', `${observation.source} ${observation.code} · ${observation.name || ''} · ${value(observation.distance_km, 1)} km do ponto municipal · ${datetime(observation.observed_at)} · ${valid ? 'referência recente' : 'referência vencida'} · temperatura ${value(observation.temperature_c, 1)} °C; vento ${value(observation.wind_kmh, 1)} km/h; rajada ${value(observation.gust_kmh, 1)} km/h.`));
  }
  evidence.append(child('p', 'analysis-foot', `Modelo coletado: ${datetime(primary.forecast?.collected_at)} · referência: ${datetime(primary.forecast?.reference_at)}. A referência municipal não é a localização exata do campus.`));
  for (const peak of primary.forecast?.rain_peaks || []) evidence.append(child('p', '', `Open-Meteo · maior janela de ${peak.hours} h: ${value(peak.total_mm, 1)} mm · ${datetime(peak.start_at)} a ${datetime(peak.end_at)}.`));
  const wind = primary.forecast?.wind?.wind_kmh;
  if (Number.isFinite(wind?.maximum)) evidence.append(child('p', '', `Open-Meteo · maior vento previsto: ${value(wind.maximum, 1)} km/h · ${datetime(wind.at)}. Vento e rajada são variáveis distintas.`));
  const heat = primary.forecast?.heat;
  if (heat?.status === 'complete') evidence.append(child('p', '', `Open-Meteo · temperatura máxima: ${value(heat.maximum_c, 1)} °C; ${heat.hours_at_or_above} referências horárias ≥ ${heat.reference_c} °C; maior sequência: ${heat.longest_sequence_hours} referências consecutivas${heat.start_at ? `, de ${datetime(heat.start_at)} a ${datetime(heat.end_at)}` : ''}. Referência descritiva, sem classificação oficial de perigo; não é sensação térmica nem medição contínua.`));
  const overlap = primary.forecast?.rain_wind_overlap;
  if (overlap) evidence.append(child('p', '', `Contexto horário Open-Meteo: rajada máxima às ${datetime(overlap.gust_at)}, com ${value(overlap.rain_mm, 1)} mm de chuva prevista entre ${datetime(overlap.rain_start_at)} e ${datetime(overlap.rain_end_at)}. Não é probabilidade de evento conjunto.`));
  const rev = primary.revision;
  if (rev?.status === 'comparable_publications') evidence.append(child('p', '', `Revisão Open-Meteo: publicação anterior de ${datetime(rev.previous_published_at)}. Para o mesmo período de ${datetime(rev.start_at)} a ${datetime(rev.end_at)}, o total passou de ${value(rev.previous_rain_mm, 1)} para ${value(rev.current_rain_mm, 1)} mm (${rev.rain_change_mm > 0 ? '+' : ''}${value(rev.rain_change_mm, 1)} mm). Uma redução prevista não confirma deslocamento seguro. Horário de coleta não é emissão do modelo.`));
  for (const pair of primary.temperature_context?.pairs || []) evidence.append(child('p', '', `Contexto exploratório: Open-Meteo ${value(pair.model_c, 1)} °C (${datetime(pair.model_at)}); METAR ${pair.icao} ${value(pair.observed_c, 1)} °C (${datetime(pair.observed_at)}), a ${value(pair.distance_km, 1)} km e ${pair.gap_minutes} min entre referências. Altitude e protocolos não conciliados; sem cálculo de erro do modelo.`));
  evidence.append(child('p', 'analysis-foot', 'CPTEC e Open-Meteo: os limites dos dias não estão conciliados. NASA POWER e arquivos INMET têm referências históricas ou atrasadas; boletins Epagri são contexto editorial, e catálogos não comprovam medições. Consulte os painéis de cada produto.'));
  for (const limitation of primary.limitations || []) evidence.append(child('p', 'analysis-foot', limitation));
  evidence.append(child('p', 'analysis-foot', 'Referência atual: PN 13/2026 e PN 14/2026 — ASSINST/REI. Seis níveis qualitativos; avisos Epagri/Ciram são prioritários. Não há tabela normativa de chuva ou vento que determine automaticamente o nível. O fim de um aviso não autoriza retomada de atividades.'));
  target.append(evidence);
  const table = child('table', 'synthesis-table');
  const header = child('tr'); ['Município complementar', 'Chuva prevista · janela identificada', 'Avisos na consulta'].forEach(label => header.append(child('th', '', label)));
  const head = child('thead'); head.append(header); table.append(head);
  const body = child('tbody');
  for (const row of feed.locations.filter(row => row.location_id !== 'araquari')) {
    const tr = child('tr');
    const cell = child('td'); const button = child('button', 'regional-link', row.name);
    button.type = 'button'; button.addEventListener('click', () => selectLocation(row.location_id)); cell.append(button);
    tr.append(cell, child('td', '', synthesisCurrent(row, feed) ? rainDescription(row) : 'Referências vencidas · sem conclusão atual'), child('td', '', synthesisCurrent(row, feed) && row.official_notices?.status === 'available' ? String(row.official_notices.notices.length) : 'Não verificáveis'));
    body.append(tr);
  }
  table.append(body); regional.append(table);
  $('synthesis-updated').textContent = `Publicada: ${datetime(feed.generated_at)} · reavaliação necessária até ${datetime(primary.valid_until)}, ou antes se o cenário mudar. Sugestões consultivas; não determinam decisões do IFC.`;
}
function renderTerritory() {
  const container = $('territory-grid');
  clear(container);
  for (const place of state.overview.locations) {
    const btn = child('button', 'territory-card' + (place.id === state.slug ? ' selected' : ''));
    btn.type = 'button';
    btn.setAttribute('aria-pressed', String(place.id === state.slug));
    const top = child('div', 'territory-top');
    top.append(child('span', '', place.name), child('span', '', weatherInfo(place.current?.weather_code).symbol));
    const reading = child('div', 'territory-reading', place.current ? value(place.current.temperature_c) + '\u00b0' : '--');
    const foot = child('div', 'territory-foot', place.status === 'available' ? (freshAt(place.current?.time, 8) ? 'Modelo Open-Meteo' : 'Modelo desatualizado') : 'Dados indispon\u00edveis');
    const group = state.alignment?.groups?.[place.territorial_group];
    if (group) foot.append(child('span', 'territory-group', ' · ' + group));
    btn.append(top, reading, foot);
    btn.addEventListener('click', () => selectLocation(place.id));
    container.append(btn);
  }
  $('territory-count').textContent = `${state.overview.available_locations} de ${state.overview.total_locations} localidades com dados`;
}
function renderDaily(rows) {
  const grid = $('daily-grid');
  clear(grid);
  for (const day of rows || []) {
    const date = new Date(day.time + 'T12:00:00Z');
    const label = new Intl.DateTimeFormat('pt-BR', { timeZone: tz, weekday: 'short', day: '2-digit' }).format(date);
    const box = child('div', 'day');
    box.append(child('span', 'day-name', label), child('span', 'day-icon', weatherInfo(day.weather_code).symbol));
    const temps = child('div', 'day-temp', value(day.temp_max_c) + '\u00b0');
    temps.append(child('span', '', ' / ' + value(day.temp_min_c) + '\u00b0'));
    box.append(temps, child('div', 'day-rain', value(day.precipitation_sum_mm, 1) + ' mm de chuva'));
    grid.append(box);
  }
  if (!grid.childElementCount) grid.append(child('div', 'loading-label', 'Sem previs\u00e3o di\u00e1ria dispon\u00edvel'));
}
const ns = 'http://www.w3.org/2000/svg';
function svg(tag, attributes = {}, text) {
  const element = document.createElementNS(ns, tag);
  Object.entries(attributes).forEach(([key, val]) => element.setAttribute(key, String(val)));
  if (text !== undefined) element.textContent = text;
  return element;
}
function renderChart() {
  const frame=$('chart'),tooltip=$('detail-chart-tooltip');clear(frame);tooltip.hidden=true;
  const rain=state.metric==='precipitation_mm',start=Math.floor(Date.now()/3600000)*3600000,end=start+24*3600000;
  const rows=(state.detail?.hourly||[]).filter(r=>{const t=Date.parse(r.time);return Number.isFinite(t)&&(rain?t>start&&t<=end:t>=start&&t<end);}).sort((a,b)=>Date.parse(a.time)-Date.parse(b.time));
  const points=rows.filter(r=>Number.isFinite(r[state.metric]));
  if(!points.length){frame.append(child('p','loading-label','Sem dados horários válidos para este período.'));return;}
  const width=Math.max(180,Math.round(frame.clientWidth||640)),height=260,left=48,right=16,top=20,bottom=44;
  const innerW=width-left-right,innerH=height-top-bottom;
  const minimum=rain?0:Math.min(...points.map(r=>r[state.metric]));
  const maximum=Math.max(...points.map(r=>r[state.metric]));
  const pad=rain?Math.max(.5,maximum*.15):Math.max(1,(maximum-minimum)*.15);
  const low=rain?0:minimum-pad,high=Math.max(low+1,maximum+pad);
  const x=t=>left+(t-start)/(end-start)*innerW,y=v=>top+innerH-(v-low)/(high-low)*innerH;
  const root=svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'img',tabindex:0,'aria-label':descriptors[state.metric]+' nas próximas 24 horas. Use setas para consultar; clique para fixar a leitura.'});
  for(let n=0;n<=4;n++){const v=low+(high-low)*n/4;root.append(svg('line',{x1:left,x2:width-right,y1:y(v),y2:y(v),class:'chart-grid'}),svg('text',{x:left-8,y:y(v)+4,'text-anchor':'end',class:'chart-label'},value(v,rain?1:0)));}
  root.append(svg('text',{x:left,y:12,class:'chart-label'},units[state.metric]));
  let segment='',last=null;
  for(const row of rows){const t=Date.parse(row.time),v=row[state.metric];if(!Number.isFinite(v)){last=null;continue;}
    if(rain)root.append(svg('rect',{x:x(t-3600000)+1,y:y(v),width:Math.max(1,innerW/24-2),height:Math.max(0,y(0)-y(v)),rx:1,class:'chart-bar'}));
    else {segment+=(last!==null&&t-last===3600000?' L':' M')+x(t)+','+y(v);last=t;}
  }
  if(!rain)root.append(svg('path',{d:segment,class:'chart-curve'}));
  const ticks=width<420?2:4;
  for(let i=0;i<=ticks;i++){const t=start+(end-start)*i/ticks;root.append(svg('text',{x:x(t),y:height-12,'text-anchor':i===0?'start':i===ticks?'end':'middle',class:'chart-label'},new Intl.DateTimeFormat('pt-BR',{timeZone:tz,hour:'2-digit',minute:'2-digit'}).format(new Date(t))));}
  if(typeof ChartInteraction!=='undefined')ChartInteraction.attach(root,{width,left,right,top,bottom:height-bottom,domain:[start,end],times:points.map(r=>Date.parse(r.time)),tooltip,
    lookup(t){const selected=rain?points.find(r=>t>Date.parse(r.time)-3600000&&t<=Date.parse(r.time)):points.reduce((a,b)=>Math.abs(Date.parse(a.time)-t)<Math.abs(Date.parse(b.time)-t)?a:b);
      const eligible=selected&&(rain||Math.abs(Date.parse(selected.time)-t)<=1800000);
      return {text:eligible?`${rain?datetime(new Date(Date.parse(selected.time)-3600000).toISOString())+' a ':''}${datetime(selected.time)}\n${descriptors[state.metric]}: ${value(selected[state.metric],1)} ${units[state.metric]}\nOpen-Meteo · modelo`:'Sem valor para este horário; lacuna não significa zero.',
        marks:eligible?[{x:rain?x(t):x(Date.parse(selected.time)),y:y(selected[state.metric]),color:'var(--green)'}]:[]};}
  });
  else {let cursor=0;root.addEventListener('keydown',event=>{if(!['Home','End','ArrowRight','ArrowLeft'].includes(event.key))return;event.preventDefault();cursor=event.key==='Home'?0:event.key==='End'?points.length-1:Math.max(0,Math.min(points.length-1,cursor+(event.key==='ArrowRight'?1:-1)));tooltip.textContent=`${datetime(points[cursor].time)} · ${value(points[cursor][state.metric],1)} ${units[state.metric]}`;tooltip.hidden=false;});}
  frame.append(root);$('chart-legend').textContent=`${descriptors[state.metric]} (${units[state.metric]}) · Open-Meteo · horários de Brasília`;
}
function renderStations() {
  const target = $('station-grid');
  clear(target);
  const catalog = state.stations;
  const record = catalog?.locations?.find((item) => item.location_id === state.slug);
  const stations = Array.isArray(record?.stations) ? record.stations : [];
  $('station-count').textContent = stations.length ? `${stations.filter(s => s.network_type !== 'convencional').length} automáticas · ${stations.filter(s => s.network_type === 'convencional').length} convencionais` : 'Sem estações disponíveis';
  $('station-updated').textContent = catalog?.retrieved_at ? `INMET: ${datetime(catalog.retrieved_at)} · automáticas ${catalog.catalog_status || 'indisponível'} · convencionais ${catalog.conventional_catalog_status || 'não verificadas'} · somente metadados` : 'Catálogos INMET indisponíveis para consulta automatizada';
  if (!stations.length) { target.append(child('p', 'loading-label', 'Não foi possível identificar estações próximas nesta publicação.')); return; }
  for (const station of stations) {
    const item = child('div', 'station-item');
    const heading = child('div', 'station-main');
    heading.append(child('strong', '', station.name), child('span', '', station.code));
    const distance = child('span', 'station-distance', `${value(station.distance_km, 1)} km`);
    const status = child('span', 'station-status', `Cadastro: ${station.catalog_status || 'não informado'}`);
    const network = station.network_type === 'convencional' ? 'convencional' : 'automática';
    const source = child('span', 'station-status', `Rede ${network}`);
    const external = child('a', 'station-open', 'Ver estação no INMET ↗');
    external.href = station.network_type === 'convencional'
      ? 'https://portal.inmet.gov.br/paginas/catalogoman'
      : (/^A\d{3,4}$/.test(station.code) ? `https://tempo.inmet.gov.br/TabelaEstacoes/${station.code}` : 'https://portal.inmet.gov.br/paginas/catalogoaut');
    external.target = '_blank'; external.rel = 'noopener noreferrer';
    item.append(heading, distance, status, source, external);
    target.append(item);
  }
}
function renderEpagriStations() {
  const target = $('epagri-registry-list'); clear(target);
  const catalog = state.epagriGeo;
  const record = catalog?.locations?.find((entry) => entry.location_id === state.slug);
  const list = Array.isArray(record?.stations) ? record.stations : [];
  $('epagri-registry-count').textContent = list.length ? `${list.length} estações cadastradas no entorno` : 'Sem cadastro disponível';
  $('epagri-registry-updated').textContent = `Epagri/SC · ${catalog?.status || 'indisponível'} · catálogo obtido: ${datetime(catalog?.retrieved_at)}. Nenhuma medição ao vivo é inferida do cadastro.`;
  if (!list.length) {
    target.append(child('p', 'loading-label', 'O cadastro geográfico não retornou estações próximas nesta publicação; isso não significa ausência de estações.'));
    return;
  }
  for (const station of list) {
    const item = child('div', 'station-item');
    const heading = child('div', 'station-main');
    heading.append(child('strong', '', station.name), child('span', '', `ID ${station.code}`));
    item.append(heading, child('span', 'station-distance', `${value(station.distance_km, 1)} km`));
    item.append(child('span', 'station-status', `${station.category || 'Categoria não informada'} · ${station.municipality || 'Município não informado'}`));
    if (station.catalog_status) item.append(child('span', 'station-status', `Situação no cadastro: ${station.catalog_status} (não confirma transmissão)`));
    if (station.responsible) item.append(child('span', 'station-status', `Responsável cadastrado: ${station.responsible}`));
    target.append(item);
  }
}
function renderEpagriNotices() {
  const target = $('epagri-advisory-list'); clear(target);
  const feed = state.epagriNotices;
  const notices = Array.isArray(feed?.notices) ? feed.notices : [];
  $('epagri-advisory-count').textContent = notices.length ? `${notices.length} publicação(ões)` : 'Nenhum aviso carregado';
  $('epagri-advisory-updated').textContent = `Epagri/Ciram · ${feed?.status || 'indisponível'} · consulta: ${datetime(feed?.checked_at)}. Não substitui avisos da Defesa Civil.`;
  if (!feed || !['available', 'cached', 'stale', 'no_recent_notices'].includes(feed.status)) {
    target.append(child('p', 'alert-unknown', 'Não foi possível consultar os avisos meteorológicos publicados pela Epagri/Ciram. Verifique o canal oficial.'));
    return;
  }
  if (feed.status === 'stale') target.append(child('p', 'alert-unknown', 'As publicações abaixo foram recuperadas de uma consulta anterior; não foram verificadas agora.'));
  if (!notices.length) {
    target.append(child('p', 'loading-label', 'Nenhuma publicação recente retornada pelo feed. Isso não significa ausência de risco meteorológico.'));
    return;
  }
  for (const notice of notices.slice(0, 6)) {
    const item = child('article', 'civil-defense-item');
    const link = child('a', 'civil-defense-link', notice.title || 'Aviso meteorológico Epagri/Ciram');
    try {
      const url = new URL(notice.url);
      if (url.protocol === 'https:' && url.hostname === 'ciram.epagri.sc.gov.br') {
        link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
      }
    } catch (_) { /* Unexpected source URL remains unlinked. */ }
    item.append(link);
    const regional = notice.north_coast_scope === 'mentioned' ? 'Litoral Norte citado no texto da fonte' : 'Abrangência no Litoral Norte não confirmada';
    const head = child('p', 'analysis-foot', `Publicado: ${datetime(notice.published_at)} · ${regional}`);
    item.append(head);
    if (notice.valid_from && notice.valid_until && notice.window_status === 'explicit_in_publication') {
      item.append(child('p', 'alert-window', `Período informado no aviso: ${datetime(notice.valid_from)} a ${datetime(notice.valid_until)}. Confira o boletim original.`));
    } else item.append(child('p', 'analysis-foot', 'Período de vigência não identificado automaticamente.'));
    if (notice.regions_text) item.append(child('p', 'analysis-foot', `Regiões indicadas no boletim: ${notice.regions_text}`));
    target.append(item);
  }
}
function renderRegionalQuality() {
  const target = $('regional-quality-data');
  clear(target);
  const data = state.regionalQuality;
  const place = data?.locations?.find((row) => row.location_id === state.slug);
  if (!place?.selected_station) {
    target.append(child('p', 'loading-label', data?.status === 'unavailable' ?
      'A fonte do arquivo INMET está indisponível. Não há medição comprovada nesta consulta.' :
      'Nenhuma estação próxima apresentou um dia completo de chuva no período disponível. Isso não equivale a chuva zero.'));
    $('regional-quality-foot').textContent = 'Consulta de estações pontuais, sem extrapolar valores para o município.';
    return;
  }
  const station = place.selected_station;
  const heading = child('div', 'station-item');
  heading.append(child('strong', '', `${station.name} (${station.code}) · ${value(station.distance_km,1)} km`));
  heading.append(child('p', 'analysis-foot', `Último dia com 24 leituras: ${station.last_complete_day_utc} (UTC) · ${value(station.last_complete_rain_mm,1)} mm medidos nesta estação`));
  const weekly = station.total_7_complete_days_mm;
  heading.append(child('p', 'analysis-foot', Number.isFinite(weekly) ?
    `7 dias completos consecutivos até essa data: ${value(weekly,1)} mm` :
    'Sete dias consecutivos completos não disponíveis; nenhum total semanal calculado.'));
  target.append(heading);
  if (place.nearest_station_missing_rain) {
    target.append(child('p', 'analysis-explainer', 'A estação geograficamente mais próxima não apresentou dias completos com chuva válida. A estação mostrada é a alternativa com dados disponíveis, e não representa a chuva do município.'));
  }
  if (place.spatial_comparison) {
    const pair = place.spatial_comparison;
    target.append(child('p', 'analysis-foot', `Contexto espacial em ${pair.day_utc}: estação ${value(pair.inmet_station_measurement_mm,1)} mm medidos; grade NASA em Araquari ${value(pair.nasa_gridded_estimate_mm,1)} mm estimados. Pontos diferentes: não é validação de modelo.`));
  }
  $('regional-quality-foot').textContent = `Arquivo INMET com atraso de ${station.days_since_complete_observation} dia(s) desde a última medição diária completa · ${place.epagri_catalog_within_30km} cadastro(s) Epagri a até 30 km, não necessariamente em operação.`;
}
function renderEpagriBulletins() {
  const target = $('epagri-bulletins-list');
  clear(target);
  const data = state.epagriBulletins;
  const bulletins = Array.isArray(data?.bulletins) ? data.bulletins : [];
  $('epagri-bulletins-count').textContent = bulletins.length ? `${bulletins.length} publicação(ões)` : 'Sem boletim recente';
  if (data?.status === 'stale') target.append(child('p', 'analysis-explainer', 'Consulta atual indisponível; boletins de uma publicação anterior, sujeitos a desatualização.'));
  if (!bulletins.length) {
    target.append(child('p', 'loading-label', 'Sem boletins recentes acessíveis. Consulte a previsão editorial original; isto não significa ausência de risco.'));
  }
  for (const row of bulletins) {
    const item = child('article', 'defesa-entry');
    const anchor = child('a', 'defesa-entry-link', row.title || 'Boletim regional');
    try {
      const url = new URL(row.url);
      if (url.protocol === 'https:' && url.hostname === 'ciram.epagri.sc.gov.br') {
        anchor.href = url.href; anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
      }
    } catch (_) { /* do not link unverified addresses */ }
    item.append(anchor, child('p', 'analysis-foot', `Publicado em ${datetime(row.published_at)} · previsão regional, não alerta emergencial`));
    if (row.summary) item.append(child('p', 'defesa-summary', row.summary));
    target.append(item);
  }
  $('epagri-bulletins-updated').textContent = data?.retrieved_at ?
    `Fonte Epagri/Ciram consultada: ${datetime(data.retrieved_at)}${data.status === 'stale' ? ' · desatualizada' : ''}` :
    'Fonte indisponível para atualização automática.';
}
function renderCptec() {
  const target = $('cptec-data'); clear(target);
  const data = state.cptec;
  const record = data?.locations?.find((x) => x.location_id === state.slug);
  $('cptec-updated').textContent = `CPTEC/INPE · estado: ${record?.status || 'indisponível'} · consulta: ${datetime(data?.checked_at)}. Consulte a fonte oficial se a previsão estiver indisponível.`;
  if (!record || !Array.isArray(record.days) || !record.days.length || record.status === 'unavailable' || !freshAt(data?.checked_at)) {
    target.append(child('p', 'loading-label', 'Previsão CPTEC indisponível nesta publicação. A previsão Open-Meteo continua independente.'));
    return;
  }
  const intro = child('p', 'analysis-explainer', `Localidade CPTEC de referência: ${record.nearest_cptec_locality || 'não identificada'} · data da atualização: ${record.updated_day || '--'}${record.status === 'stale' ? ' · PREVISÃO DESATUALIZADA' : ''}.`);
  target.append(intro);
  for (const day of record.days.slice(0, 7)) {
    const item = child('div', 'cptec-day');
    const dt = child('strong', '', day.day?.split('-').reverse().join('/') || '--');
    const temp = child('span', '', `Mín. ${value(day.minimum_c, 0)}°C · Máx. ${value(day.maximum_c, 0)}°C`);
    const uv = child('span', '', `UV máx.: ${value(day.uv_index_max, 1)}`);
    item.append(dt, temp, uv);
    const model = state.detail?.daily?.find((row) => row.time === day.day);
    if (model && Number.isFinite(model.temp_max_c) && Number.isFinite(day.maximum_c) && record.status === 'available' && freshAt(state.detail?.collected_at, 8) && freshAt(state.detail?.current?.time, 8)) {
      item.append(child('span', 'model-difference', `Open-Meteo: máx. ${value(model.temp_max_c, 1)}°C no dia UTC. Limites do dia CPTEC não conciliados; valores apenas lado a lado.`));
    }
    target.append(item);
  }
}
function renderArchive() {
  const target = $('archive-data'); clear(target);
  const feed = state.archive;
  const status = feed?.status || 'unavailable';
  const statuses = { available:'Arquivo público consultado', cached:'Arquivo previamente consultado',
    stale:'Últimas observações antigas', unavailable:'Fonte indisponível',
    no_nearby_stations:'Sem estações automáticas próximas no catálogo', fixture_mode:'Somente teste' };
  $('archive-updated').textContent = `INMET · ${statuses[status] || status} · última coleta do ZIP: ${datetime(feed?.retrieved_at)} · última medição do arquivo: ${datetime(feed?.latest_observation_at)}. Não representa precipitação atual.`;
  if (!feed || !['available','cached','stale'].includes(status)) {
    target.append(child('p', 'loading-label', 'Ainda não há dados de arquivo anual verificáveis para as estações próximas. Consulte diretamente o INMET; isso não representa chuva zero.'));
    return;
  }
  const locality = feed.locations?.find((item) => item.location_id === state.slug);
  const nearby = Array.isArray(locality?.stations) ? locality.stations.slice(0, 3) : [];
  if (!nearby.length) {
    target.append(child('p', 'loading-label', 'Nenhuma estação do arquivo anual identificada no entorno desta localidade.'));
    return;
  }
  if (status === 'stale') target.append(child('p', 'alert-unknown', 'Arquivo de observações desatualizado. Nenhum dado apresentado aqui deve ser interpretado como recente.'));
  for (const entry of nearby) {
    const station = feed.stations.find((item) => item.code === entry.code);
    if (!station) continue;
    const card = child('article', 'archive-station');
    const head = child('div', 'observed-heading');
    head.append(child('strong', '', `${station.name} (${station.code})`), child('span', '', `${value(entry.distance_km, 1)} km em linha reta`));
    card.append(head, child('p', 'analysis-foot', `Última observação do arquivo: ${datetime(station.last_observation_at)} · horários e dias em UTC`));
    const table = child('div', 'archive-days');
    for (const day of (station.days || []).slice(0, 7)) {
      const row = child('div', 'archive-day');
      row.append(child('strong', '', day.day_utc?.split('-').reverse().join('/') || '--'));
      const complete = day.rain_measured_hours === 24 && Number.isFinite(day.rain_total_complete_mm);
      const amount = complete ? `${value(day.rain_total_complete_mm, 1)} mm (24/24 h)` :
        `Parcial · ${day.rain_measured_hours || 0}/24 h${Number.isFinite(day.rain_sum_available_hours_mm) ? ` · ${value(day.rain_sum_available_hours_mm, 1)} mm nas horas disponíveis` : ''}`;
      row.append(child('span', complete ? 'archive-complete' : 'archive-incomplete', amount));
      table.append(row);
    }
    if (!table.childElementCount) table.append(child('p', 'loading-label', 'Arquivo sem dias utilizáveis.'));
    card.append(table); target.append(card);
  }
}
function renderDefesa() {
  const target = $('defesa-list'); clear(target);
  const source = state.defesa;
  const posts = Array.isArray(source?.publications) ? source.publications : [];
  const mentioned = posts.filter(p => Array.isArray(p.mentioned_location_ids) && p.mentioned_location_ids.includes(state.slug));
  const statewide = posts.filter(p => p.category === 'previsao_publicada' && !mentioned.includes(p));
  const selected = [...mentioned, ...statewide].slice(0, 9);
  $('defesa-count').textContent = mentioned.length ? `${mentioned.length} publicação(ões) mencionando a localidade` : 'Menção municipal não identificada';
  const failures = (source?.source_diagnostics || []).slice(0, 2).join(' / ');
  $('defesa-updated').textContent = `Defesa Civil SC · consulta: ${datetime(source?.checked_at)} · situação: ${source?.status || 'indisponível'}${failures ? ` · falhas: ${failures}` : ''} · as publicações NÃO confirmam vigência de alertas. Emergência: 199 ou 193.`;
  if (source?.status === 'stale') target.append(child('p', 'alert-unknown', 'A fonte oficial não respondeu nesta atualização. Estas publicações foram preservadas de uma consulta anterior e NÃO comprovam alertas vigentes.'));
  if (!selected.length) {
    target.append(child('p', 'loading-label', source?.status === 'unavailable' ? 'Canal automatizado indisponível. Consulte os links oficiais para alertas e boletins.' : 'Nenhuma publicação recente identificada para este município na amostra acessível. Isso não significa ausência de alertas.'));
    return;
  }
  for (const post of selected) {
    const item = child('article', 'defesa-entry');
    const anchor = child('a', 'defesa-entry-link', post.title || 'Publicação oficial');
    try {
      const address = new URL(post.url);
      if (address.protocol === 'https:' && ['www.defesacivil.sc.gov.br', 'defesacivil.sc.gov.br'].includes(address.hostname)) {
        anchor.href = address.href; anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
      }
    } catch (_) { /* omit invalid link */ }
    const where = mentioned.includes(post) ? 'Menção explícita ao município no resumo' : 'Boletim estadual; abrangência local não verificada';
    const timeText = post.publication_precision === 'calendar_day_from_url_not_exact_time' ? `data aproximada: ${post.published_at?.slice(0, 10).split('-').reverse().join('/')}` : datetime(post.published_at);
    const label = child('span', 'analysis-foot', `${post.category?.replaceAll('_', ' ') || 'Publicação'} · ${timeText} · ${where}`);
    item.append(anchor, label);
    if (post.summary) item.append(child('p', 'defesa-summary', post.summary));
    target.append(item);
  }
}
function renderHistory() {
  const target = $('history-chart');
  clear(target);
  const history = state.history;
  const rows = history?.records?.filter((row) => row.location_id === state.slug && Number.isFinite(row.temperature_c)).slice(-35) || [];
  $('history-count').textContent = `${rows.length} dia${rows.length === 1 ? '' : 's'} registrado${rows.length === 1 ? '' : 's'}`;
  $('history-updated').textContent = rows.length ? `De ${rows[0].day_local} a ${rows[rows.length - 1].day_local} · valores de modelo (não medidos)` : 'O histórico é formado progressivamente a cada nova publicação.';
  if (!rows.length) { target.append(child('p', 'loading-label', 'O histórico começará a aparecer após a primeira publicação com dados.')); return; }
  if (rows.length === 1) {
    target.append(child('p', 'history-single', `${value(rows[0].temperature_c, 1)} °C`));
    target.append(child('p', 'loading-label', `Referência do modelo: ${datetime(rows[0].model_reference_at)}`));
    return;
  }
  const w = 600, h = 180, left = 42, right = 12, top = 14, bottom = 34;
  const vals = rows.map((r) => r.temperature_c);
  let min = Math.floor(Math.min(...vals) - 2), max = Math.ceil(Math.max(...vals) + 2);
  if (max <= min) max = min + 1;
  const x = (i) => left + i * (w - left - right) / (rows.length - 1);
  const y = (v) => top + (h - top - bottom) * (1 - (v - min) / (max - min));
  const root = svg('svg', { viewBox: `0 0 ${w} ${h}`, role: 'img', 'aria-label': `Ultimas ${rows.length} temperaturas estimadas, de ${value(vals[0], 1)} a ${value(vals[vals.length-1], 1)} graus` });
  for (let n = 0; n <= 4; n++) {
    const v = min + n * (max - min) / 4;
    const py = y(v);
    root.append(svg('line', {x1: left, x2: w-right, y1: py, y2: py, class: 'chart-grid'}));
    root.append(svg('text', {x: left-7, y: py+4, 'text-anchor': 'end', class: 'chart-label'}, value(v, 0)));
  }
  root.append(svg('path', {d: rows.map((r, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(r.temperature_c).toFixed(1)}`).join(' '), class: 'chart-curve'}));
  [0, Math.floor((rows.length - 1) / 2), rows.length - 1].forEach((i) => {
    root.append(svg('text', {x: x(i), y: h - 9, 'text-anchor': 'middle', class: 'chart-label'}, rows[i].day_local.slice(5).replace('-', '/')));
  });
  target.append(root);
}
function renderObservations() {
  const target = $('observed-data');
  clear(target);
  const feed = state.observations;
  const record = feed?.locations?.find((item) => item.location_id === state.slug);
  if (!feed || feed.status === 'unavailable') {
    target.append(child('p', 'loading-label', 'Consulta METAR indisponível. Não há medição confirmada para exibir.'));
    $('observed-foot').textContent = 'Fonte: Aviation Weather Center (NOAA) · consulta indisponível';
    return;
  }
  const references = Array.isArray(record?.stations) ? record.stations :
    record?.observation ? [{icao: record.observation.icao, distance_km: record.distance_km, scope: 'nearby_aerodrome'}] : [];
  const cards = [];
  for (const ref of references) {
    const observation = feed.stations?.find((row) => row.icao === ref.icao) ||
      (record?.observation?.icao === ref.icao ? record.observation : null);
    if (!observation || !freshAt(observation.observed_at) || !freshAt(feed.retrieved_at)) continue;
    const card = child('article', 'rain-station');
    const heading = child('div', 'observed-heading');
    heading.append(child('strong', '', `${observation.name} (${observation.icao})`),
      child('span', '', `${value(ref.distance_km, 1)} km em linha reta`));
    card.append(heading);
    if (ref.scope === 'regional_context_only') card.append(child('p', 'alert-unknown', 'Contexto regional: aeródromo a mais de 100 km. Não descreve as condições desta localidade.'));
    const metrics = child('div', 'observed-metrics');
    for (const [label, amount] of [
      ['TEMPERATURA MEDIDA', Number.isFinite(observation.temperature_c) ? `${value(observation.temperature_c, 1)} °C` : '--'],
      ['VENTO MEDIDO', Number.isFinite(observation.wind_kmh) ? `${value(observation.wind_kmh, 1)} km/h` : '--'],
      ['RAJADA MEDIDA', Number.isFinite(observation.gust_kmh) ? `${value(observation.gust_kmh, 1)} km/h` : '--'],
    ]) {
      const tile = child('div', 'observed-metric');
      tile.append(child('span', '', label), child('strong', '', amount));
      metrics.append(tile);
    }
    card.append(metrics, child('p', 'analysis-foot', `Medição no aeródromo: ${datetime(observation.observed_at)} · boletim METAR (NOAA). Não equivale à condição de todo o município.`));
    cards.push(card);
  }
  if (cards.length) appendStationCards(target, cards);
  else target.append(child('p', 'loading-label', 'Nenhum boletim METAR recente no raio regional para esta localidade. Isso não significa ausência de estações ou de risco.'));
  const queried = feed.queried_stations || [];
  const missing = queried.filter((row) => row.status !== 'available').map((row) => row.icao);
  $('observed-foot').textContent = `NOAA · ${cards.length} aeródromo(s) com leitura válida até ${feed.selection?.regional_radius_km || 180} km · consulta: ${datetime(feed.retrieved_at)}${queried.length ? ` · ${queried.length} consultados na rede` : ''}${missing.length ? ` · sem boletim recente: ${missing.join(', ')}` : ''}. METAR não fornece chuva acumulada em mm.`;
}
function renderOfficialAlerts() {
  const target = $('official-alerts');
  clear(target);
  const feed = state.alerts;
  const validTime = feed?.retrieved_at && Number.isFinite(Date.parse(feed.retrieved_at));
  const fresh = validTime && Date.now() - Date.parse(feed.retrieved_at) >= -10 * 60000 && Date.now() - Date.parse(feed.retrieved_at) <= 6 * 3600000;
  if (!feed || feed.status !== 'available' || !fresh) {
    target.append(child('p', 'alert-unknown', 'Não foi possível confirmar a situação atual dos avisos do INMET. Verifique o portal oficial e a Defesa Civil.'));
    $('alert-updated').textContent = 'Situação de avisos não confirmada nesta publicação.';
    return;
  }
  const place = feed.locations?.find((item) => item.location_id === state.slug);
  if (!place || !Array.isArray(place.alerts)) {
    target.append(child('p', 'alert-unknown', 'Não foi possível verificar os avisos deste município.'));
    $('alert-updated').textContent = 'Cobertura municipal não confirmada.';
    return;
  }
  $('alert-updated').textContent = `Consulta INMET: ${datetime(feed.retrieved_at)} · vigência e fuso: conforme a fonte original.`;
  if (!place.alerts.length) {
    target.append(child('p', 'alert-empty', 'Nenhum aviso municipal retornado pelo INMET nesta consulta. Isso não exclui outros alertas ou riscos locais.'));
    return;
  }
  for (const alert of place.alerts) {
    const card = child('section', 'alert-entry');
    const head = child('div', 'alert-entry-heading');
    head.append(child('strong', '', alert.type || 'Aviso meteorológico'), child('span', 'alert-severity', alert.severity || 'Não informada'));
    card.append(head, child('p', 'alert-window', alert.window_as_reported || 'Período não informado'));
    const risk = Array.isArray(alert.risks) ? alert.risks.filter((text) => typeof text === 'string').slice(0, 2) : [];
    const recommendations = Array.isArray(alert.instructions) ? alert.instructions.filter((text) => typeof text === 'string').slice(0, 2) : [];
    if (risk.length) card.append(child('p', 'alert-description', risk.join(' · ')));
    if (recommendations.length) card.append(child('p', 'alert-instructions', `Orientação INMET: ${recommendations.join(' · ')}`));
    target.append(card);
  }
}
function renderRain() {
  const target = $('rain-gauges');
  clear(target);
  const feed = state.rain;
  const status = feed?.status;
  if (!feed || status === 'unavailable') {
    target.append(child('p', 'alert-unknown', 'A consulta pluviométrica do INMET está indisponível. Não é possível confirmar chuva medida nesta publicação.'));
  } else if (status === 'not_configured') {
    target.append(child('p', 'loading-label', 'A consulta de medições INMET depende de autorização. Ainda não foi configurada; previsões de chuva continuam disponíveis no painel do modelo.'));
  } else if (status === 'access_restricted') {
    target.append(child('p', 'alert-unknown', 'O INMET recusou o acesso à API de leituras. Verifique a autorização e a interface disponibilizada pelo órgão; o catálogo de estações, sozinho, não contém chuva medida.'));
  } else if (status === 'no_recent_data') {
    target.append(child('p', 'loading-label', 'As estações consultadas não retornaram leituras recentes válidas. Isso não significa precipitação zero.'));
  } else if (status === 'no_nearby_catalog_stations') {
    target.append(child('p', 'loading-label', 'Não foram identificadas estações selecionáveis no catálogo disponível.'));
  } else if (status !== 'available') {
    target.append(child('p', 'loading-label', 'Nenhuma medição instrumental publicada nesta versão.'));
  } else {
    const local = feed.locations?.find((item) => item.location_id === state.slug);
    const selected = Array.isArray(local?.stations) ? local.stations.slice(0, 4) : [];
    if (!selected.length) {
      target.append(child('p', 'loading-label', 'Nenhuma estação com leituras recentes no entorno desta localidade.'));
    } else {
      for (const nearby of selected) {
        const station = feed.stations?.find((s) => s.code === nearby.code);
        if (!station) continue;
        if (!freshAt(feed.checked_at) || !freshAt(station.observed_at)) {
          target.append(child('p', 'alert-unknown', `Estação ${station.code}: leitura desatualizada (${datetime(station.observed_at)}).`));
          continue;
        }
        const item = child('article', 'rain-station');
        const head = child('div', 'observed-heading');
        head.append(child('strong', '', `${station.name} (${station.code})`), child('span', '', `${value(nearby.distance_km, 1)} km em linha reta`));
        item.append(head);
        const values = child('div', 'observed-metrics');
        const summary = [
          ['ÚLTIMA HORA MEDIDA', Number.isFinite(station.rain_last_hour_mm) ? `${value(station.rain_last_hour_mm, 1)} mm` : 'Sem dado'],
          ['24 LEITURAS HORÁRIAS', station.rain_24h_complete && Number.isFinite(station.rain_last_24_readings_mm) ? `${value(station.rain_last_24_readings_mm, 1)} mm` : 'Cobertura incompleta'],
          ['COBERTURA HORÁRIA', `${station.hourly_coverage_24 || 0}/24 leituras`],
        ];
        for (const [label, val] of summary) {
          const metric = child('div', 'observed-metric');
          metric.append(child('span', '', label), child('strong', '', val));
          values.append(metric);
        }
        item.append(values, child('p', 'analysis-foot', `Medição: ${datetime(station.observed_at)} · dados brutos não validados.`));
        target.append(item);
      }
    }
  }
  const causes = feed?.failure_reasons ? Object.entries(feed.failure_reasons).map(([key, count]) => `${key}: ${count}`).join(' · ') : '';
  $('rain-updated').textContent = `INMET · ${status || 'não consultado'} · ${datetime(feed?.checked_at)}${causes ? ' · ' + causes : ''} · sem representatividade municipal garantida.`;
}
function renderCemaden() {
  const target = $('cemaden-data');
  clear(target);
  const data = state.cemaden;
  const local = data?.locations?.find((place) => place.location_id === state.slug);
  const status = local?.status || data?.status;
  const statusText = {
    not_configured: 'Esta fonte não está habilitada nesta publicação. Não há leitura instrumental disponível; consulte as outras fontes.',
    access_restricted: 'A API PED recusou o token ou o acesso à informação. Necessário validar a autorização no Cemaden.',
    unavailable: 'O serviço Cemaden não respondeu adequadamente nesta publicação. Não é possível confirmar a chuva observada.',
    no_recent_data: 'Consulta concluída: nenhuma leitura recente válida neste município. Isso não significa chuva zero.',
    rate_limited: 'A consulta deste município atingiu o limite da fonte. Não é possível confirmar leituras.',
    fixture_mode: 'Dados de teste: pluviometria instrumental desabilitada.'
  };
  if (!data || statusText[status]) {
    target.append(child('p', status === 'unavailable' || status === 'access_restricted' ? 'alert-unknown' : 'loading-label', statusText[status] || 'Integração Cemaden indisponível.'));
  } else {
    const allRows = Array.isArray(local?.stations) ? local.stations : [];
    const rows = allRows.filter((row) => freshAt(data.checked_at) && freshAt(row.observed_at));
    if (allRows.length && rows.length < allRows.length) target.append(child('p', 'alert-unknown', 'Há leituras desatualizadas, omitidas dos acumulados atuais. Consulte a fonte oficial.'));
    if (!allRows.length) target.append(child('p', 'loading-label', 'Nenhum pluviômetro Cemaden com leitura recente para este município. A ausência de leitura não significa chuva zero.'));
    const cards = [];
    for (const station of rows) {
      const item = child('article', 'rain-station');
      const reference=state.cemadenSensors?.stations?.find(r=>r.code===station.code);
      const name=reference?.name&&reference.name!==station.code?reference.name:'Estação sem nome informado';
      item.append(child('strong','',name),child('small','station-code',`${reference?.municipality||state.overview?.locations?.find(r=>r.id===state.slug)?.name||'Localidade selecionada'} · código ${station.code}`));
      const metrics = child('div', 'observed-metrics');
      const periods = [
        ['1H', station.rain_1h_mm], ['3H', station.rain_3h_mm],
        ['6H', station.rain_6h_mm], ['12H', station.rain_12h_mm],
        ['24H', station.rain_24h_mm], ['48H', station.rain_48h_mm],
        ['72H', station.rain_72h_mm], ['96H', station.rain_96h_mm],
        ['120H', station.rain_120h_mm]
      ];
      const extra=child('details','accumulation-more'),additional=child('div','observed-metrics');
      extra.append(child('summary','','Outros acumulados · 6 a 120 h'));
      for (const [windowHours, val] of periods) {
        const label = `CHUVA MEDIDA ${windowHours}`;
        const tile = child('div', 'observed-metric');
        tile.append(child('span', '', label), child('strong', '', Number.isFinite(val) ? `${value(val, 1)} mm` : 'Sem dado'));
        (['1H','3H','24H'].includes(windowHours)?metrics:additional).append(tile);
      }
      extra.append(additional);
      item.append(metrics,extra, child('p', 'analysis-foot', `Registro da estação: ${datetime(station.observed_at)} · medição bruta.`));
      cards.push(item);
    }
    if (cards.length) target.append(child('p', 'analysis-foot', `${cards.length} pluviômetro(s) com leitura válida neste município.`));
    appendStationCards(target, cards);
  }
  $('cemaden-updated').textContent = `Cemaden · consulta: ${datetime(data?.checked_at)}. DADOS DA REDE OBSERVACIONAL DO CEMADEN/MCTIC. Os acumulados pertencem a cada estação.`;
}
function renderCemadenSensors() {
  const target = $('cemaden-sensors-data');
  clear(target);
  const feed = state.cemadenSensors;
  const status = feed?.status;
  const checkedAtMs = feed?.checked_at ? Date.parse(feed.checked_at) : NaN;
  const hoursOld = Date.now() - checkedAtMs;
  const freshnessConfirmed = Number.isFinite(hoursOld) && hoursOld >= -10 * 60000 && hoursOld <= 6 * 3600000;
  const messages = {
    not_configured: 'Credenciais Cemaden ainda não configuradas. Não há medições nesta publicação.',
    access_restricted: 'A PED recusou acesso às leituras de sensores. A chuva acumulada é uma consulta independente.',
    unavailable: 'A consulta regional de sensores está indisponível ou excedeu um limite de segurança. Nenhuma leitura foi presumida.',
    no_recent_data: 'Nenhuma medição válida das últimas três horas foi identificada perto desta localidade.',
    fixture_mode: 'Dados de teste: sem medições instrumentais.'
  };
  if (!feed || status !== 'available' || !freshnessConfirmed) {
    target.append(child('p', status === 'unavailable' || (status === 'available' && !freshnessConfirmed) ? 'alert-unknown' : 'loading-label',
      status === 'available' && !freshnessConfirmed
        ? 'A última coleta de sensores ficou desatualizada. Consulte a fonte oficial: não é possível confirmar medições atuais.'
        : messages[status] || 'Integração de sensores não disponível.'));
  } else {
    const local = feed.locations?.find((row) => row.location_id === state.slug);
    const nearby = Array.isArray(local?.stations) ? local.stations : [];
    const cards = [];
    if (!nearby.length) target.append(child('p', 'loading-label', messages.no_recent_data));
    for (const match of nearby) {
      const station = feed.stations?.find((item) => item.code === match.code);
      if (!station || !Array.isArray(station.readings)) continue;
      const card = child('article', 'rain-station');
      const heading = child('div', 'observed-heading');
      heading.append(child('strong', '', `${station.name} (${station.code})`),
        child('span', '', `${value(match.distance_km, 1)} km em linha reta`));
      card.append(heading, child('p', 'analysis-foot', `Local informado pela fonte: ${station.municipality}.`));
      const metrics = child('div', 'observed-metrics');
      const validReadings = station.readings.filter((reading) => freshAt(reading.observed_at, 3 + 20 / 60));
      if (validReadings.length < station.readings.length) card.append(child('p', 'alert-unknown', 'Leituras vencidas foram omitidas.'));
      for (const reading of validReadings.slice(0, 8)) {
        const metric = child('div', 'observed-metric');
        const descriptor = `${reading.sensor_name} · sensor ${reading.sensor_id}`;
        metric.append(child('span', '', descriptor),
          child('strong', '', `${value(reading.value, 2)}${reading.unit ? ' ' + reading.unit : ' (unidade não confirmada)'}`),
          child('span', '', datetime(reading.observed_at)));
        metrics.append(metric);
      }
      card.append(metrics);
      cards.push(card);
    }
    if (cards.length) target.append(child('p', 'analysis-foot', `${cards.length} estação(ões) selecionada(s) de ${local?.eligible_station_count ?? nearby.length} com leitura na área · raio de ${feed.selection?.radius_km || 130} km. Não representa cobertura de todo o município.`));
    appendStationCards(target, cards);
  }
  $('cemaden-sensors-updated').textContent = `Cemaden PED · ${status || 'indisponível'} · consulta: ${datetime(feed?.checked_at)} · medições pontuais das últimas 3 horas quando válidas. DADOS DA REDE OBSERVACIONAL DO CEMADEN/MCTIC.`;
}
function renderNasa() {
  const target = $('nasa-data');
  clear(target);
  const feed = state.nasa;
  if (!feed || !['available', 'cached', 'stale'].includes(feed.status) || !Array.isArray(feed.daily) || !feed.daily.length) {
    target.append(child('p', 'loading-label', 'NASA POWER ainda não disponibilizou uma série válida nesta publicação. As previsões Open-Meteo permanecem independentes.'));
    $('nasa-updated').textContent = `NASA POWER · estado: ${feed?.status || 'indisponível'} · verificação: ${datetime(feed?.checked_at)}`;
    return;
  }
  const mostRecent = feed.daily.slice(-7).reverse();
  const table = child('div', 'nasa-daily-list');
  for (const record of mostRecent) {
    const row = child('div', 'nasa-daily-row');
    row.append(child('span', '', record.date_utc.split('-').reverse().join('/')),
      child('strong', '', Number.isFinite(record.rain_estimated_mm_day) ? `${value(record.rain_estimated_mm_day, 1)} mm/dia` : 'Sem chuva estimada'),
      child('span', '', Number.isFinite(record.temperature_estimated_c) ? `${value(record.temperature_estimated_c, 1)} °C (média estimada)` : '--'));
    table.append(row);
  }
  target.append(table);
  if (feed.status === 'stale') target.append(child('p', 'alert-unknown', 'A última consulta NASA falhou: são exibidos valores anteriores, explicitamente desatualizados.'));
  $('nasa-updated').textContent = `NASA POWER · referência: ${feed.point?.name || 'Araquari'} · último dia de dados: ${feed.latest_data_day_utc || '--'} UTC · consulta: ${datetime(feed.retrieved_at)} · ${feed.status}. Não é estação meteorológica.`;
}
function renderSourceHealth() {
  const target = $('source-health');
  clear(target);
  const overview = state.overview;
  const cemadenLocal = state.cemaden?.locations?.find((row) => row.location_id === state.slug);
  const providers = [
    ['Open-Meteo · modelo', overview?.available_locations ? (overview.available_locations === overview.total_locations ? 'available' : 'partial') : 'unavailable'],
    ['INMET · catálogo', state.stations?.catalog_status || 'unavailable'],
    ['INMET · avisos', state.alerts?.status || 'unavailable'],
    ['NOAA · METAR', state.observations?.status || 'unavailable'],
    ['INMET · pluviometria', state.rain?.status || 'unavailable'],
    ['INMET · arquivo anual', state.archive?.status || 'unavailable'],
    ['Cemaden · pluviometria', cemadenLocal?.status || state.cemaden?.status || 'unavailable'],
    ['Cemaden · sensores recentes', state.cemadenSensors?.diagnostic === 'partial_state_coverage' ? 'partial' : state.cemadenSensors?.status || 'unavailable'],
    ['NASA POWER · grade', state.nasa?.status || 'unavailable'],
    ['CPTEC/INPE · previsão', state.cptec?.status || 'unavailable'],
    ['Defesa Civil SC · publicações', state.defesa?.status || 'unavailable'],
    ['Epagri · cadastro de estações', state.epagriGeo?.status || 'unavailable'],
    ['Epagri/Ciram · avisos publicados', state.epagriNotices?.status || 'unavailable'],
    ['Epagri/Ciram · previsão editorial', state.epagriBulletins?.status || 'unavailable'],
    ['INMET · cobertura observada por localidade', state.regionalQuality?.status || 'unavailable'],
    ['INMET · convencionais', state.stations?.conventional_catalog_status || 'unavailable'],
  ];
  const feeds = [overview, state.stations, state.alerts, state.observations, state.rain,
    state.archive, state.cemaden, state.cemadenSensors, state.nasa, state.cptec,
    state.defesa, state.epagriGeo, state.epagriNotices, state.epagriBulletins,
    state.regionalQuality, state.stations];
  const limits = [8, 192, 6, 6, 6, 192, 6, 6, 72, 6, 6, 72, 6, 6, 8, 192];
  const labels = {
    rate_limited:'Limite da fonte atingido', no_recent_report:'Sem boletim recente',
    available:'Disponível', cached:'Última leitura em cache', stale:'Dados anteriores', partial:'Parcial',
    unavailable:'Indisponível', not_configured:'Credencial não configurada',
    access_restricted:'Acesso recusado', no_recent_data:'Sem leituras recentes',
    no_recent_reports:'Sem boletins recentes', no_nearby_catalog_stations:'Sem estações próximas',
    no_recent_publications:'Sem publicações recentes', no_recent_bulletins:'Sem boletins editoriais recentes',
    no_complete_gauge_data:'Sem dia completo medido', not_tested:'Não testado',
    no_nearby_stations:'Sem estações automáticas próximas', fixture_mode:'Teste sintético'
  };
  for (const [index, [name, rawStatus]] of providers.entries()) {
    const feed = feeds[index];
    const stamp = feed?.retrieved_at || feed?.checked_at || feed?.generated_at;
    let status = effectiveStatus(rawStatus, stamp, limits[index]);
    if (index === 6 && status === 'available' && !cemadenLocal?.stations?.some((row) => freshAt(row.observed_at))) status = 'stale';
    if (index === 7 && status === 'available' && !state.cemadenSensors?.stations?.some((row) => row.readings?.some((r) => freshAt(r.observed_at, 3 + 20 / 60)))) status = 'stale';
    const item = child('div', 'source-health-item');
    item.append(child('strong', '', name), child('span', `source-health-status ${['available','cached'].includes(status) ? 'health-ok' : 'health-pending'}`, labels[status] || status));
    if (stamp) item.append(child('small', 'analysis-foot', `Consulta: ${datetime(stamp)}`));
    target.append(item);
  }
}
function renderCoverage() {
  const target = $('coverage-data');
  clear(target);
  const local = state.coverage?.locations?.find((row) => row.location_id === state.slug);
  if (!local) { target.append(child('p', 'loading-label', 'Resumo de cobertura indisponível nesta publicação.')); return; }
  const statuses = { available: 'Disponível', unavailable: 'Falha na consulta', not_configured: 'Não configurado',
    access_restricted: 'Acesso recusado', no_recent_data: 'Sem leitura válida', no_recent_report: 'Sem boletim recente',
    rate_limited: 'Limite atingido', stale: 'Dados desatualizados', fixture_mode: 'Teste sintético' };
  for (const product of local.products) {
    const limit = product.id === 'cemaden-sensors' ? 3 + 20 / 60 : product.id === 'open-meteo' ? 8 : 6;
    let status = effectiveStatus(product.status, product.checked_at, 6);
    status = effectiveStatus(status, product.reference_at, limit);
    const card = child('article', 'coverage-card');
    card.append(child('strong', '', product.name), child('p', 'analysis-foot', statuses[status] || status));
    const count = product.station_count === null ? 'Modelo numérico' : `${product.station_count} estação(ões) com dados na coleta`;
    card.append(child('p', '', count), child('p', '', product.variables.join(' · ') || 'Sem variável disponível'));
    if (product.regional_context_only_count) card.append(child('p', 'analysis-foot', `${product.regional_context_only_count} aeródromo(s) apenas como contexto regional (>100 km).`));
    if (Number.isFinite(product.nearest_distance_km)) card.append(child('p', 'analysis-foot', `Mais próxima: ${value(product.nearest_distance_km, 1)} km em linha reta`));
    card.append(child('p', 'analysis-foot', `Referência mais recente: ${datetime(product.reference_at)} · consulta: ${datetime(product.checked_at)}. A idade varia por leitura; confira os painéis abaixo.`));
    target.append(card);
  }
}
function renderTerritorialAlignment() {
  const target = $('alignment-data');
  clear(target);
  const dataset = state.alignment;
  const local = dataset?.locations?.find((row) => row.location_id === state.slug);
  if (!local) { target.append(child('p', 'loading-label', 'Alinhamento territorial indisponível nesta publicação.')); return; }
  const group = dataset.groups?.[local.territorial_group] || 'Área sem núcleo definido';
  target.append(child('p', '', `${group} · ponto municipal: ${value(local.sample_point.latitude, 4)}, ${value(local.sample_point.longitude, 4)}`));
  const fresh = freshAt(dataset.checked_at, 6);
  target.append(child('p', fresh ? 'analysis-foot' : 'alert-unknown',
    `${local.cemaden_nearby_count} estação(ões) Cemaden e ${local.metar_nearby_count} aeródromo(s) na coleta a até ${dataset.spatial_radius_km} km do ponto municipal. Referência: ${datetime(dataset.checked_at)}${fresh ? '' : ' · levantamento desatualizado'}.`));
  target.append(child('p', 'analysis-foot', `Pluviômetros consultados pelo IBGE municipal: ${local.cemaden_local_rain.station_count}. Essa associação não confirma proximidade física da estação.`));
  if (local.cemaden_state_query_status && local.cemaden_state_query_status !== 'available') target.append(child('p', 'alert-unknown', 'A consulta Cemaden desta UF falhou. A cobertura territorial está incompleta.'));
  const cards = [];
  for (const candidate of local.candidate_triads || []) {
    const card = child('article', 'coverage-card');
    const sensor = local.cemaden_candidates.find((row) => row.code === candidate.cemaden_code);
    const metar = local.metar_candidates.find((row) => row.code === candidate.metar_code);
    const current = fresh && freshAt(local.model.reference_at, 8) && freshAt(sensor?.reference_at, 3+20/60) && freshAt(metar?.reference_at);
    card.append(child('strong', '', `Open-Meteo · Cemaden ${candidate.cemaden_code} · METAR ${candidate.metar_code}`));
    card.append(child('p', '', `Cemaden ao ponto municipal: ${value(sensor?.sample_distance_km, 1)} km · METAR: ${value(metar?.sample_distance_km, 1)} km · entre estações: ${value(candidate.station_distance_km, 1)} km.`));
    if (candidate.model_grid_proximity_verified) card.append(child('p', 'analysis-foot', `Distâncias à referência de grade retornada: Cemaden ${value(sensor?.model_grid_distance_km, 1)} km; METAR ${value(metar?.model_grid_distance_km, 1)} km.`));
    else card.append(child('p', 'analysis-foot', 'Proximidade da grade do modelo ainda não confirmada.'));
    const common = candidate.potential_common_variables.includes('temperature_c') ? 'Temperatura em °C é uma variável potencialmente comum.' : 'Ainda não há variável comum confirmada nas três fontes.';
    card.append(child('p', '', common));
    card.append(child('p', 'analysis-foot', `Diferença entre referências: ${value(candidate.time_gap_minutes)} min · ${candidate.time_window_aligned ? 'até 60 min' : 'exige alinhamento temporal'}.`));
    card.append(child('p', 'alert-unknown', `${current ? 'Candidato geográfico para estudo futuro.' : 'Candidato do levantamento anterior; referências vencidas.'} Altitude das estações, relevo, altura dos sensores e intervalos de medição ainda não foram conciliados. Não é uma comparação de precisão.`));
    cards.push(card);
  }
  if (!cards.length) target.append(child('p', 'loading-label', 'Não foi encontrado um conjunto das três fontes suficientemente próximo e com modelo recente nesta coleta. As fontes continuam disponíveis nos painéis individuais.'));
  appendStationCards(target, cards, 3);
}
function renderNoticeArchive() {
  const target = $('notice-archive-list');
  clear(target);
  const archive = state.noticeArchive;
  if (!archive || !Array.isArray(archive.records)) {
    target.append(child('p', 'loading-label', 'Histórico de avisos não disponível nesta publicação.'));
    $('notice-archive-count').textContent = 'Sem arquivo';
    return;
  }
  const local = archive.records.filter((r) => Array.isArray(r.municipality_ids) && r.municipality_ids.includes(state.slug));
  $('notice-archive-count').textContent = `${local.length} aviso${local.length === 1 ? '' : 's'} arquivado${local.length === 1 ? '' : 's'}`;
  if (!local.length) {
    target.append(child('p', 'loading-label', 'Nenhum aviso registrado para este município no período arquivado.'));
  } else {
    for (const item of local.slice(0, 6)) {
      const card = child('article', 'notice-record');
      const heading = child('div', 'alert-entry-heading');
      heading.append(child('strong', '', item.type || 'Aviso meteorológico'), child('span', 'alert-severity', item.severity || 'Sem classificação'));
      card.append(heading, child('p', 'alert-window', `Período informado: ${item.window_as_reported || 'indisponível'}`));
      card.append(child('p', 'analysis-foot', `Primeiro registro: ${datetime(item.first_seen_at)} · último registro: ${datetime(item.last_seen_at)} · ${item.present_in_latest_successful_feed ? 'constava na última consulta válida' : 'não constava na última consulta válida'}`));
      target.append(card);
    }
  }
  $('notice-archive-foot').textContent = `Arquivo de avisos oficiais · última consolidação: ${datetime(archive.updated_at)} · ${archive.feed_status === 'available' ? 'fonte consultada' : 'fonte indisponível; não inferir encerramento'}. Não comprova ocorrência de desastres.`;
}
function clearDetails() {
  $('detail-chart-tooltip').hidden=true;
  for (const id of ['temp', 'feels', 'humidity', 'wind', 'rain-24', 'rain-now', 'gust-now', 'pressure', 'model-time', 'coordinates', 'source-time']) $(id).textContent = '--';
  $('rain-coverage').textContent = 'Sem janela completa publicada';
  $('rain-interval').textContent = 'Intervalo não informado';
  $('weather').textContent = 'Dados indispon\u00edveis';
  renderDaily([]);
  clear($('chart'));
  $('chart').append(child('span', 'error-message', 'N\u00e3o foi poss\u00edvel carregar os dados desta localidade.'));
}
function renderDetail() {
  const detail = state.detail;
  if (!detail) { clearDetails(); return; }
  const current = detail.current;
  if (!freshAt(detail.collected_at, 8) || !freshAt(current.time, 8)) {
    clearDetails();
    $('weather').textContent = 'Modelo desatualizado';
    $('model-time').textContent = 'Última referência: ' + datetime(current.time);
    return;
  }
  const place = state.overview.locations.find((item) => item.id === state.slug);
  $('temp').textContent = value(current.temperature_c, 1) + '\u00b0C';
  $('feels').textContent = value(current.feels_like_c, 1) + '\u00b0C';
  $('humidity').textContent = value(current.humidity_pct) + '%';
  $('wind').textContent = `${value(current.wind_kmh)} / ${value(current.gust_kmh)}`;
  $('weather').textContent = weatherInfo(current.weather_code).label;
  const window = place?.rain_window;
  $('rain-24').textContent = window?.status === 'complete' ? value(place?.rain_next_24h_mm, 1) + ' mm' : 'Incompleto';
  $('rain-coverage').textContent = window ? `${window.valid_hours}/24 h válidas · ${datetime(window.start_at)} a ${datetime(window.end_at)}${window.status !== 'complete' && Number.isFinite(window.partial_sum_mm) ? ` · soma parcial: ${value(window.partial_sum_mm, 1)} mm` : ''}` : 'Cobertura não informada';
  $('rain-now').textContent = value(current.precipitation_mm, 1) + ' mm';
  $('rain-interval').textContent = Number.isFinite(current.interval_seconds) ? `Intervalo informado: ${value(current.interval_seconds / 60, 1)} min` : 'Intervalo não informado pela fonte';
  $('gust-now').textContent = value(current.gust_kmh, 1) + ' km/h';
  $('pressure').textContent = value(current.pressure_hpa) + ' hPa';
  $('model-time').textContent = 'Modelo: ' + datetime(current.time);
  $('source-time').textContent = datetime(current.time);
  $('coordinates').textContent = `${value(detail.location.latitude, 3)}, ${value(detail.location.longitude, 3)}`;
  renderDaily(detail.daily);
  renderChart();
}
async function selectLocation(slug) {
  if (!/^[a-z0-9-]+$/.test(slug) || !state.overview.locations.some((item) => item.id === slug)) return;
  state.slug = slug;
  state.detail = null;
  const requestId = ++state.requestId;
  const place = state.overview.locations.find((item) => item.id === slug);
  $('place-title').textContent = place.name + ' / ' + place.state;
  $('place-subtitle').textContent = slug === 'araquari' ? 'Referência principal · dados do município selecionado' : 'Consulta complementar · a síntese principal permanece em Araquari';
  $('location-select').value = slug;
  renderSynthesis();
  renderTerritory();
  renderStations();
  renderEpagriStations();
  renderHistory();
  renderObservations();
  renderOfficialAlerts();
  renderRain();
  renderCemaden();
  renderCemadenSensors();
  renderNasa();
  renderCptec();
  renderDefesa();
  renderEpagriNotices();
  renderEpagriBulletins();
  renderArchive();
  renderRegionalQuality();
  renderSourceHealth();
  renderCoverage();
  renderTerritorialAlignment();
  renderNoticeArchive();
  clearDetails();
  if (place.status !== 'available') return;
  try {
    const detail = await readJson(`./data/places/${slug}.json`);
    if (requestId !== state.requestId) return;
    if (detail.location?.id !== slug || detail.source?.id !== 'open-meteo') throw new Error('Inconsistent location data');
    state.detail = detail;
    renderDetail();
    renderCptec();
  } catch (err) {
    if (requestId !== state.requestId) return;
    console.error('Failed to load municipality data:', err);
    clearDetails();
  }
}
async function boot() {
  const bootId = ++state.bootId;
  ++state.requestId;
  setStatus('Consultando dados publicados...', '');
  try {
    const overview = await readJson('./data/latest.json');
    if (!Array.isArray(overview.locations) || overview.schema_version !== 1 || overview.fixture_mode) throw new Error('Invalid or test dataset');
    if (bootId !== state.bootId) return;
    state.overview = overview;
    const [stations, history, alerts, observations, rain, noticeArchive, nasa, cemaden, cemadenSensors, cptec, defesa, archive, epagriGeo, epagriNotices, epagriBulletins, regionalQuality, coverage, alignment, analysis] = await Promise.all([
      readJson('./data/stations.json').catch(() => null),
      readJson('./data/history.json').catch(() => null),
      readJson('./data/alerts.json').catch(() => null),
      readJson('./data/observations.json').catch(() => null),
      readJson('./data/rain_gauges.json').catch(() => null),
      readJson('./data/notice_history.json').catch(() => null),
      readJson('./data/nasa_power.json').catch(() => null),
      readJson('./data/cemaden.json').catch(() => null),
      readJson('./data/cemaden_sensors.json').catch(() => null),
      readJson('./data/cptec.json').catch(() => null),
      readJson('./data/defesa_civil_sc.json').catch(() => null),
      readJson('./data/inmet_archive.json').catch(() => null),
      readJson('./data/epagri_geo.json').catch(() => null),
      readJson('./data/epagri_notices.json').catch(() => null),
      readJson('./data/epagri_bulletins.json').catch(() => null),
      readJson('./data/regional_quality.json').catch(() => null),
      readJson('./data/coverage.json').catch(() => null),
      readJson('./data/territorial_alignment.json').catch(() => null),
      readJson('./data/analysis.json').catch(() => null),
    ]);
    if (bootId !== state.bootId) return;
    state.analysis = analysis?.schema_version === 1 && analysis?.kind === 'meteorological_evidence_and_advisory_not_institutional_decision' && analysis?.primary_location_id === 'araquari' && analysis?.generated_at === overview.generated_at && !analysis?.fixture_mode && analysis?.institutional_decisions_automated === false ? analysis : null;
    renderSynthesis();
    state.alignment = alignment?.kind === 'territorial_source_alignment_not_model_validation' && alignment?.schema_version === 1 ? alignment : null;
    state.coverage = coverage?.kind === 'local_source_coverage_not_municipal_weather_measurement' && coverage?.schema_version === 1 ? coverage : null;
    state.stations = stations?.schema_version === 1 && stations?.kind === 'station_catalog_metadata_not_measurements' ? stations : null;
    state.history = history?.schema_version === 1 && history?.kind === 'daily_last_model_publication_not_station_observation' ? history : null;
    state.alerts = alerts?.schema_version === 1 && alerts?.kind === 'inmet_official_notices_by_municipality' ? alerts : null;
    state.observations = observations?.schema_version === 1 && observations?.kind === 'aerodrome_metar_observations_not_municipal_measurements' ? observations : null;
    state.rain = rain?.schema_version === 1 && rain?.kind === 'inmet_automatic_station_hourly_observed_rain_unvalidated' ? rain : null;
    state.noticeArchive = noticeArchive?.schema_version === 1 && noticeArchive?.kind === 'archive_of_inmet_notices_not_confirmed_weather_events' ? noticeArchive : null;
    state.nasa = nasa?.schema_version === 1 && nasa?.kind === 'nasa_power_daily_gridded_estimate_not_station_observation' ? nasa : null;
    state.cemaden = cemaden?.schema_version === 1 && cemaden?.kind === 'cemaden_recent_observed_station_rainfall_raw' ? cemaden : null;
    state.cemadenSensors = cemadenSensors?.schema_version === 1 && cemadenSensors?.kind === 'cemaden_recent_instrumental_sensor_readings_not_model_forecast' ? cemadenSensors : null;
    state.cptec = cptec?.schema_version === 1 && cptec?.kind === 'cptec_inpe_daily_forecast_nearest_locality_not_station_measurements' ? cptec : null;
    state.defesa = defesa?.schema_version === 1 && defesa?.kind === 'defesa_civil_sc_publications_not_verified_active_alerts' ? defesa : null;
    state.archive = archive?.schema_version === 1 && archive?.kind === 'inmet_annual_zip_delayed_station_measurements_not_real_time' ? archive : null;
    state.epagriGeo = epagriGeo?.schema_version === 1 && epagriGeo?.kind === 'epagri_arcgis_station_registry_not_live_measurements' ? epagriGeo : null;
    state.epagriNotices = epagriNotices?.schema_version === 1 && epagriNotices?.kind === 'epagri_ciram_official_advisories_not_civil_defense_alerts' ? epagriNotices : null;
    state.epagriBulletins = epagriBulletins?.schema_version === 1 && epagriBulletins?.kind === 'epagri_ciram_editorial_forecast_bulletins_not_emergency_alerts' ? epagriBulletins : null;
    state.regionalQuality = regionalQuality?.schema_version === 1 && regionalQuality?.kind === 'regional_gauge_coverage_and_spatial_model_context_not_live_alert' ? regionalQuality : null;
    const select = $('location-select');
    clear(select);
    for (const loc of overview.locations) {
      const option = child('option', '', loc.name + ' / ' + loc.state);
      option.value = loc.id;
      select.append(option);
    }
    select.disabled = false;
    refreshPublicationStatus();
    $('updated-at').textContent = 'Atualizado: ' + datetime(overview.generated_at);
    const featured = overview.locations.find((loc) => loc.id === state.slug) || overview.locations.find((loc) => loc.id === 'araquari') || overview.locations.find((loc) => loc.featured && loc.status === 'available') || overview.locations.find((loc) => loc.status === 'available') || overview.locations[0];
    await selectLocation(featured.id);
  } catch (err) {
    if (bootId !== state.bootId) return;
    console.error('Failed to initialize observatory:', err);
    state.analysis = null;
    renderSynthesis();
    setStatus('N\u00e3o foi poss\u00edvel carregar os dados do observat\u00f3rio', 'warning');
    $('updated-at').textContent = 'Confira a publica\u00e7\u00e3o do site';
  }
}
$('location-select').addEventListener('change', (event) => selectLocation(event.target.value));
$('reload').addEventListener('click', boot);
for (const button of document.querySelectorAll('[data-metric]')) {
  button.addEventListener('click', () => {
    state.metric = button.dataset.metric;
    for (const b of document.querySelectorAll('[data-metric]')) {
      const selected = b === button;
      b.classList.toggle('active', selected);
      b.setAttribute('aria-pressed', String(selected));
    }
    renderDetail();
  });
}
function refreshAges() {
  if (!state.overview) return;
  refreshPublicationStatus();
  renderSynthesis();
  renderTerritory();
  renderDetail();
  renderObservations();
  renderOfficialAlerts();
  renderRain();
  renderCemaden();
  renderCemadenSensors();
  renderSourceHealth();
  renderCoverage();
  renderTerritorialAlignment();
  renderCptec();
}
setInterval(refreshAges, 60000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshAges(); });
boot();


if(typeof document!=='undefined'&&typeof ResizeObserver!=='undefined'){
  let chartWidth=0;
  new ResizeObserver(entries=>{const width=Math.round(entries[0].contentRect.width);if(width>0&&width!==chartWidth){chartWidth=width;requestAnimationFrame(()=>{if(state.detail)renderChart();});}}).observe($('chart'));
}
