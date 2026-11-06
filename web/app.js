'use strict';

const state = { overview: null, detail: null, slug: null, metric: 'temperature_c', requestId: 0 };
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
  clearDetails();
  if (place.status !== 'available') return;
  try {
    const detail = await readJson(`./data/places/${slug}.json`);
    if (requestId !== state.requestId) return;
    if (detail.location?.id !== slug || detail.source?.id !== 'open-meteo') throw new Error('Inconsistent location data');
    state.detail = detail;
    renderDetail();
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
