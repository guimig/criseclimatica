'use strict';

const state = { overview: null, detail: null, stations: null, history: null, alerts: null, observations: null, rain: null, nasa: null, cemaden: null, cptec: null, defesa: null, archive: null, noticeArchive: null, epagriGeo: null, epagriNotices: null, slug: null, metric: 'temperature_c', requestId: 0 };
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
async function readJson(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
function setStatus(message, kind) {
  $('system-status').textContent = message;
  $('signal').className = 'signal' + (kind ? ' ' + kind : '');
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
    const foot = child('div', 'territory-foot', place.status === 'available' ? 'Modelo Open-Meteo' : 'Dados indispon\u00edveis');
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
  const frame = $('chart');
  clear(frame);
  const hourly = state.detail?.hourly || [];
  const now = Date.now();
  const valid = hourly.filter((item) => {
    const time = Date.parse(item.time);
    return Number.isFinite(time) && time >= now - 3600000 && time < now + 24 * 3600000;
  }).slice(0, 24);
  const points = valid.map((item) => item[state.metric]).filter((v) => Number.isFinite(v));
  if (!points.length) { frame.append(child('span', 'loading-label', 'Dados hor\u00e1rios indispon\u00edveis para este per\u00edodo.')); return; }
  const width = 640, height = 220, left = 45, right = 14, top = 14, bottom = 35;
  const innerW = width - left - right, innerH = height - top - bottom;
  const floor = state.metric === 'precipitation_mm' ? 0 : Math.min(...points);
  let ceiling = Math.max(...points);
  if (ceiling === floor) ceiling += 1;
  const gap = state.metric === 'precipitation_mm' ? ceiling * 0.18 : Math.max(1, (ceiling - floor) * 0.15);
  const min = state.metric === 'precipitation_mm' ? 0 : floor - gap;
  const max = ceiling + gap;
  const x = (i) => left + (i / Math.max(1, valid.length - 1)) * innerW;
  const y = (v) => top + innerH - (v - min) / (max - min) * innerH;
  const root = svg('svg', { viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': descriptors[state.metric] + ' nas proximas 24 horas' });
  for (let n = 0; n <= 4; n++) {
    const v = min + (max - min) * n / 4;
    const py = y(v);
    root.append(svg('line', { x1: left, x2: width - right, y1: py, y2: py, class: 'chart-grid' }));
    root.append(svg('text', { x: left - 8, y: py + 4, 'text-anchor': 'end', class: 'chart-label' }, value(v, state.metric === 'precipitation_mm' ? 1 : 0)));
  }
  let segment = '';
  const paths = [];
  valid.forEach((item, index) => {
    const v = item[state.metric];
    if (!Number.isFinite(v)) { if (segment) paths.push(segment); segment = ''; return; }
    const point = `${x(index).toFixed(1)},${y(v).toFixed(1)}`;
    segment += (segment ? ' L' : 'M') + point;
    if (state.metric === 'precipitation_mm') {
      const barWidth = Math.max(5, innerW / Math.max(24, valid.length) * .55);
      root.append(svg('rect', { x: x(index) - barWidth / 2, y: y(v), width: barWidth, height: Math.max(0, y(0) - y(v)), rx: 2, class: 'chart-bar' }));
    }
  });
  if (segment) paths.push(segment);
  if (state.metric !== 'precipitation_mm') {
    paths.forEach((d) => root.append(svg('path', { d, class: 'chart-curve' })));
  }
  valid.forEach((item, i) => {
    if (i % 5 !== 0 && i !== valid.length - 1) return;
    root.append(svg('text', { x: x(i), y: height - 12, 'text-anchor': 'middle', class: 'chart-label' }, datetime(item.time, { hour: '2-digit', minute: '2-digit' }).split(' ').slice(-1)[0]));
  });
  frame.append(root);
  $('chart-legend').textContent = `${descriptors[state.metric]} (${units[state.metric]}) \u2022 fonte Open-Meteo`;
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
function renderCptec() {
  const target = $('cptec-data'); clear(target);
  const data = state.cptec;
  const record = data?.locations?.find((x) => x.location_id === state.slug);
  $('cptec-updated').textContent = `CPTEC/INPE · estado: ${record?.status || 'indisponível'} · consulta: ${datetime(data?.checked_at)}. Consulte a fonte oficial se a previsão estiver indisponível.`;
  if (!record || !Array.isArray(record.days) || !record.days.length || record.status === 'unavailable') {
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
    if (model && Number.isFinite(model.temp_max_c) && Number.isFinite(day.maximum_c) && record.status === 'available') {
      const delta = day.maximum_c - model.temp_max_c;
      item.append(child('span', 'model-difference', `Diferença máx. CPTEC − Open-Meteo: ${delta > 0 ? '+' : ''}${value(delta, 1)}°C`));
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
  const observation = record?.status === 'available' ? record.observation : null;
  const timestamp = observation?.observed_at ? Date.parse(observation.observed_at) : NaN;
  const fresh = Number.isFinite(timestamp) && timestamp <= Date.now() + 10 * 60 * 1000 && Date.now() - timestamp <= 6 * 3600 * 1000;
  if (feed?.status === 'unavailable' || !feed) {
    target.append(child('p', 'loading-label', 'Consulta METAR indisponível. Não há medição confirmada para exibir.'));
    $('observed-foot').textContent = 'Fonte: Aviation Weather Center (NOAA) · consulta indisponível';
    return;
  }
  if (!observation || !fresh) {
    target.append(child('p', 'loading-label', 'Nenhum boletim METAR recente de aeródromo próximo para esta localidade.'));
    $('observed-foot').textContent = `Consulta aeronáutica: ${datetime(feed.retrieved_at)} · sem boletim recente aplicável`;
    return;
  }
  const heading = child('div', 'observed-heading');
  heading.append(child('strong', '', `${observation.name} (${observation.icao})`), child('span', '', `${value(record.distance_km, 1)} km em linha reta`));
  target.append(heading);
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
  target.append(metrics);
  $('observed-foot').textContent = `Medição no aeródromo: ${datetime(observation.observed_at)} · boletim METAR (NOAA). Não equivale à condição de todo o município.`;
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
  const status = data?.status;
  const statusText = {
    not_configured: 'O Cemaden exige token JWT da API PED. Ainda não há credencial autorizada configurada para a coleta automática.',
    access_restricted: 'A API PED recusou o token ou o acesso à informação. Necessário validar a autorização no Cemaden.',
    unavailable: 'O serviço Cemaden não respondeu adequadamente nesta publicação. Não é possível confirmar a chuva observada.',
    no_recent_data: 'A consulta foi concluída, mas não foram encontrados acumulados instrumentais recentes para os municípios cadastrados.',
    fixture_mode: 'Dados de teste: pluviometria instrumental desabilitada.'
  };
  if (!data || statusText[status]) {
    target.append(child('p', status === 'unavailable' || status === 'access_restricted' ? 'alert-unknown' : 'loading-label', statusText[status] || 'Integração Cemaden indisponível.'));
  } else {
    const local = data.locations?.find((place) => place.location_id === state.slug);
    const rows = Array.isArray(local?.stations) ? local.stations : [];
    if (!rows.length) target.append(child('p', 'loading-label', 'Nenhum pluviômetro Cemaden com leitura recente para este município. A ausência de leitura não significa chuva zero.'));
    for (const station of rows.slice(0, 6)) {
      const item = child('article', 'rain-station');
      item.append(child('strong', '', `Estação ${station.code}`));
      const metrics = child('div', 'observed-metrics');
      for (const [label, val] of [['CHUVA MEDIDA 1H', station.rain_1h_mm], ['ACUMULADO MEDIDO 24H', station.rain_24h_mm]]) {
        const tile = child('div', 'observed-metric');
        tile.append(child('span', '', label), child('strong', '', Number.isFinite(val) ? `${value(val, 1)} mm` : 'Sem dado'));
        metrics.append(tile);
      }
      item.append(metrics, child('p', 'analysis-foot', `Registro da estação: ${datetime(station.observed_at)} · medição bruta.`));
      target.append(item);
    }
  }
  $('cemaden-updated').textContent = `Cemaden PED · estado: ${status || 'indisponível'} · consulta: ${datetime(data?.checked_at)}. Credenciais nunca são enviadas ao navegador.`;
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
  const providers = [
    ['Open-Meteo · modelo', overview?.available_locations ? (overview.available_locations === overview.total_locations ? 'available' : 'partial') : 'unavailable'],
    ['INMET · catálogo', state.stations?.catalog_status || 'unavailable'],
    ['INMET · avisos', state.alerts?.status || 'unavailable'],
    ['NOAA · METAR', state.observations?.status || 'unavailable'],
    ['INMET · pluviometria', state.rain?.status || 'unavailable'],
    ['INMET · arquivo anual', state.archive?.status || 'unavailable'],
    ['Cemaden · pluviometria', state.cemaden?.status || 'unavailable'],
    ['NASA POWER · grade', state.nasa?.status || 'unavailable'],
    ['CPTEC/INPE · previsão', state.cptec?.status || 'unavailable'],
    ['Defesa Civil SC · publicações', state.defesa?.status || 'unavailable'],
    ['Epagri · cadastro de estações', state.epagriGeo?.status || 'unavailable'],
    ['Epagri/Ciram · avisos publicados', state.epagriNotices?.status || 'unavailable'],
    ['INMET · convencionais', state.stations?.conventional_catalog_status || 'unavailable'],
  ];
  const labels = {
    available:'Disponível', cached:'Última leitura em cache', stale:'Dados anteriores', partial:'Parcial',
    unavailable:'Indisponível', not_configured:'Credencial não configurada',
    access_restricted:'Acesso recusado', no_recent_data:'Sem leituras recentes',
    no_recent_reports:'Sem boletins recentes', no_nearby_catalog_stations:'Sem estações próximas',
    no_recent_publications:'Sem publicações recentes', not_tested:'Não testado',
    no_nearby_stations:'Sem estações automáticas próximas', fixture_mode:'Teste sintético'
  };
  for (const [name, status] of providers) {
    const item = child('div', 'source-health-item');
    item.append(child('strong', '', name), child('span', `source-health-status ${['available','cached'].includes(status) ? 'health-ok' : 'health-pending'}`, labels[status] || status));
    target.append(item);
  }
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
  for (const id of ['temp', 'feels', 'humidity', 'wind', 'rain-24', 'rain-now', 'gust-now', 'pressure', 'model-time', 'coordinates', 'source-time']) $(id).textContent = '--';
  $('weather').textContent = 'Dados indispon\u00edveis';
  renderDaily([]);
  clear($('chart'));
  $('chart').append(child('span', 'error-message', 'N\u00e3o foi poss\u00edvel carregar os dados desta localidade.'));
}
function renderDetail() {
  const detail = state.detail;
  if (!detail) { clearDetails(); return; }
  const current = detail.current;
  const place = state.overview.locations.find((item) => item.id === state.slug);
  $('temp').textContent = value(current.temperature_c, 1) + '\u00b0C';
  $('feels').textContent = value(current.feels_like_c, 1) + '\u00b0C';
  $('humidity').textContent = value(current.humidity_pct) + '%';
  $('wind').textContent = `${value(current.wind_kmh)} / ${value(current.gust_kmh)}`;
  $('weather').textContent = weatherInfo(current.weather_code).label;
  $('rain-24').textContent = value(place?.rain_next_24h_mm, 1) + ' mm';
  $('rain-now').textContent = value(current.precipitation_mm, 1) + ' mm';
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
  $('place-subtitle').textContent = 'Ponto de refer\u00eancia para o modelo meteorol\u00f3gico';
  $('location-select').value = slug;
  renderTerritory();
  renderStations();
  renderEpagriStations();
  renderHistory();
  renderObservations();
  renderOfficialAlerts();
  renderRain();
  renderCemaden();
  renderNasa();
  renderCptec();
  renderDefesa();
  renderEpagriNotices();
  renderArchive();
  renderSourceHealth();
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
  setStatus('Consultando dados publicados...', '');
  try {
    const overview = await readJson('./data/latest.json');
    if (!Array.isArray(overview.locations) || overview.schema_version !== 1 || overview.fixture_mode) throw new Error('Invalid or test dataset');
    state.overview = overview;
    const [stations, history, alerts, observations, rain, noticeArchive, nasa, cemaden, cptec, defesa, archive, epagriGeo, epagriNotices] = await Promise.all([
      readJson('./data/stations.json').catch(() => null),
      readJson('./data/history.json').catch(() => null),
      readJson('./data/alerts.json').catch(() => null),
      readJson('./data/observations.json').catch(() => null),
      readJson('./data/rain_gauges.json').catch(() => null),
      readJson('./data/notice_history.json').catch(() => null),
      readJson('./data/nasa_power.json').catch(() => null),
      readJson('./data/cemaden.json').catch(() => null),
      readJson('./data/cptec.json').catch(() => null),
      readJson('./data/defesa_civil_sc.json').catch(() => null),
      readJson('./data/inmet_archive.json').catch(() => null),
      readJson('./data/epagri_geo.json').catch(() => null),
      readJson('./data/epagri_notices.json').catch(() => null),
    ]);
    state.stations = stations?.schema_version === 1 && stations?.kind === 'station_catalog_metadata_not_measurements' ? stations : null;
    state.history = history?.schema_version === 1 && history?.kind === 'daily_last_model_publication_not_station_observation' ? history : null;
    state.alerts = alerts?.schema_version === 1 && alerts?.kind === 'inmet_official_notices_by_municipality' ? alerts : null;
    state.observations = observations?.schema_version === 1 && observations?.kind === 'aerodrome_metar_observations_not_municipal_measurements' ? observations : null;
    state.rain = rain?.schema_version === 1 && rain?.kind === 'inmet_automatic_station_hourly_observed_rain_unvalidated' ? rain : null;
    state.noticeArchive = noticeArchive?.schema_version === 1 && noticeArchive?.kind === 'archive_of_inmet_notices_not_confirmed_weather_events' ? noticeArchive : null;
    state.nasa = nasa?.schema_version === 1 && nasa?.kind === 'nasa_power_daily_gridded_estimate_not_station_observation' ? nasa : null;
    state.cemaden = cemaden?.schema_version === 1 && cemaden?.kind === 'cemaden_recent_observed_station_rainfall_raw' ? cemaden : null;
    state.cptec = cptec?.schema_version === 1 && cptec?.kind === 'cptec_inpe_daily_forecast_nearest_locality_not_station_measurements' ? cptec : null;
    state.defesa = defesa?.schema_version === 1 && defesa?.kind === 'defesa_civil_sc_publications_not_verified_active_alerts' ? defesa : null;
    state.archive = archive?.schema_version === 1 && archive?.kind === 'inmet_annual_zip_delayed_station_measurements_not_real_time' ? archive : null;
    state.epagriGeo = epagriGeo?.schema_version === 1 && epagriGeo?.kind === 'epagri_arcgis_station_registry_not_live_measurements' ? epagriGeo : null;
    state.epagriNotices = epagriNotices?.schema_version === 1 && epagriNotices?.kind === 'epagri_ciram_official_advisories_not_civil_defense_alerts' ? epagriNotices : null;
    const select = $('location-select');
    clear(select);
    for (const loc of overview.locations) {
      const option = child('option', '', loc.name + ' / ' + loc.state);
      option.value = loc.id;
      select.append(option);
    }
    select.disabled = false;
    const outdated = Date.now() - Date.parse(overview.generated_at) > 8 * 3600000;
    const partial = overview.available_locations < overview.total_locations;
    setStatus(outdated ? 'Dados publicados est\u00e3o desatualizados' : partial ? 'Atualiza\u00e7\u00e3o parcial: algumas localidades indispon\u00edveis' : 'Dados de modelo dispon\u00edveis', outdated || partial ? 'warning' : 'ok');
    $('updated-at').textContent = 'Atualizado: ' + datetime(overview.generated_at);
    const featured = overview.locations.find((loc) => loc.id === state.slug && loc.status === 'available') || overview.locations.find((loc) => loc.featured && loc.status === 'available') || overview.locations.find((loc) => loc.status === 'available') || overview.locations[0];
    await selectLocation(featured.id);
  } catch (err) {
    console.error('Failed to initialize observatory:', err);
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
    renderChart();
  });
}
boot();
