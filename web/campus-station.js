'use strict';
(function () {
  const KIND = 'ifc_araquari_campus_observations_not_risk_criteria';
  const definitions = {
    temperature: ['Temperatura', '°C', -50, 65], humidity: ['Umidade relativa', '%', 0, 100],
    pressure: ['Pressão atmosférica', 'hPa', 800, 1100], rain_daily: ['Chuva acumulada no dia', 'mm', 0, 2000],
    rain_intensity: ['Intensidade da chuva', 'mm/h', 0, 2000], wind_avg: ['Vento médio informado', 'km/h', 0, 400],
    wind_gust: ['Rajada informada', 'km/h', 0, 400], wind_direction_deg: ['Direção do vento', '°', 0, 360]
  };
  const number = value => new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 2}).format(value);
  const date = value => new Intl.DateTimeFormat('pt-BR', {timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'}).format(new Date(value));
  const time = value => new Intl.DateTimeFormat('pt-BR', {timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit'}).format(new Date(value));
  function pointValid(point, key, start, end) {
    const stamp = Date.parse(point?.time), definition = definitions[key];
    return !!definition && Number.isFinite(stamp) && stamp >= start && stamp <= end && stamp <= Date.now() &&
      typeof point.value === 'number' && Number.isFinite(point.value) && point.value >= definition[2] && point.value <= definition[3];
  }
  function validate(feed, publication) {
    if (!feed || feed.schema_version !== 1 || feed.kind !== KIND || feed.location_id !== 'araquari' ||
        feed.risk_criteria !== false || !['available', 'stale', 'no_recent_data', 'unavailable', 'fixture_mode'].includes(feed.status) ||
        feed.publication_at !== publication || !Number.isFinite(Date.parse(feed.checked_at)) ||
        Date.parse(feed.checked_at) > Date.now()+600000 || !feed.metrics || typeof feed.metrics !== 'object') throw new Error('Invalid campus publication');
    return feed;
  }
  // Export pure validation for offline contract tests; the source is never used by the risk engine.
  if (typeof module !== 'undefined') module.exports = {pointValid, validate};
  if (typeof document === 'undefined') return;
  const section = document.getElementById('campus-station');
  if (!section) return;
  const el = id => document.getElementById(id);
  const create = (tag, text, className) => {const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node;};
  const svgNode = (tag, attrs, text) => {const node = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value); if (text) node.textContent = text; return node;};
  let feed = null, failed = false, busy = false, selectedTime = null, selectedKey = null;
  const selection = el('campus-variable');
  for (const [key, definition] of Object.entries(definitions)) {
    if (key !== 'wind_direction_deg') {const option = create('option', definition[0]); option.value = key; selection.append(option);}
  }
  async function json(path) {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 15000);
    try {const response = await fetch(path, {cache: 'no-store', signal: controller.signal}); if (!response.ok) throw new Error('HTTP '+response.status); return await response.json();}
    finally {clearTimeout(timeout);}
  }
  function bounds() {return [Date.parse(feed?.window_start), Math.min(Date.now(), Date.parse(feed?.window_end))];}
  function suspect(key,point) {
    if(!point||point.value!==0||!['temperature','humidity'].includes(key))return false;
    const other=feed?.metrics?.[key==='temperature'?'humidity':'temperature'];
    return [other?.latest,...(other?.series||[])].some(p=>p&&p.time===point.time&&p.value===0);
  }
  function fresh(point) {return point && Date.now()-Date.parse(point.time) <= 90*60000;}
  function render() {
    const status = el('campus-status'), cards = el('campus-values'); cards.replaceChildren();
    if (!feed) {status.textContent = failed ? 'Não foi possível consultar a estação nesta publicação. Nova tentativa automática.' : 'Consultando a estação do campus…'; renderChart(); return;}
    const [start, end] = bounds();
    const current = Object.entries(feed.metrics).some(([key, metric]) => pointValid(metric.latest, key, start, end) && fresh(metric.latest));
    status.textContent = failed ? 'Falha ao buscar a nova publicação. A leitura anterior foi preservada com os horários originais.' :
      current ? 'Observações da estação IFC Araquari · horários de Brasília.' :
      feed.status === 'unavailable' ? 'A consulta à estação falhou nesta coleta. Isso não significa ausência de chuva ou vento.' :
      feed.status === 'fixture_mode' ? 'Sem consulta instrumental nesta simulação.' : 'Sem medição recente válida. O histórico disponível está identificado abaixo.';
    for (const key of ['temperature', 'humidity', 'rain_daily', 'wind_gust', 'pressure', 'rain_intensity']) {
      const point = feed.metrics[key]?.latest, valid = pointValid(point, key, start, end)&&!suspect(key,point);
      const card = create('div', undefined, 'campus-value');
      card.append(create('span', definitions[key][0]), create('strong', valid ? number(point.value)+' '+definitions[key][1] : 'Sem dado'));
      card.append(create('small', valid ? date(point.time)+(fresh(point) ? '' : ' · leitura antiga') : suspect(key,point)?'Temperatura e umidade simultaneamente zeradas; leitura suspeita':'Sem referência válida'));
      cards.append(card);
    }
    el('campus-reference').textContent = 'Consulta: '+date(feed.checked_at)+'. Coleta alvo a cada 30 minutos; sem garantia de transmissão contínua. Integra a síntese local por variável; não define nível institucional.';
    const direction = feed.metrics.wind_direction_deg?.latest, mean = feed.metrics.wind_avg?.latest;
    el('campus-extra').textContent = [pointValid(mean, 'wind_avg', start, end) ? 'Vento médio informado: '+number(mean.value)+' km/h ('+date(mean.time)+').' : '',
      pointValid(direction, 'wind_direction_deg', start, end) ? 'Direção: '+number(direction.value)+'° ('+date(direction.time)+').' : ''].filter(Boolean).join(' ');
    renderChart();
  }
  function renderChart() {
    const target = el('campus-plot'), readout = el('campus-readout'), keepFocus = target.contains(document.activeElement); target.replaceChildren();
    const key = selection.value || 'temperature', metric = feed?.metrics?.[key], [start, end] = bounds();
    const points = (Array.isArray(metric?.series) ? metric.series : []).filter(p => pointValid(p, key, start, end)&&!suspect(key,p)).sort((a,b) => Date.parse(a.time)-Date.parse(b.time)).slice(0,300);
    el('campus-chart-note').textContent = key === 'rain_daily' ? 'Máximo em cada intervalo de 5 minutos. Contador diário informado; pode reiniciar. Não é chuva das últimas 24 h.' :
      metric?.aggregation === 'MAX' ? 'Máximo informado em cada intervalo de 5 minutos.'+(key==='wind_gust'?' O intervalo de medição original da rajada ainda precisa de confirmação.':'') : 'Média das leituras disponíveis em intervalos de 5 minutos. Lacunas não são interpoladas.';
    if(points.length)el('campus-chart-note').textContent += ' '+points.length+' intervalos com dados na janela consultada.';
    if (!points.length) {target.append(create('p', 'Sem série válida nesta publicação.', 'campus-empty')); readout.textContent = 'Nenhum valor selecionado.'; return;}
    const width = Math.max(280, Math.round(target.clientWidth || 700)), height = 220, left = 48, right = width-12, top = 16, bottom = 188;
    let lo = Math.min(...points.map(p => p.value)), hi = Math.max(...points.map(p => p.value));
    if (lo === hi) {lo = Math.max(definitions[key][2], lo-1); hi += 1;}
    const margin = (hi-lo)*0.08; lo = Math.max(definitions[key][2],lo-margin); hi += margin;
    const x = stamp => left+(Date.parse(stamp)-start)/(end-start)*(right-left), y = value => bottom-(value-lo)/(hi-lo)*(bottom-top);
    const svg = svgNode('svg', {viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': definitions[key][0]+' no campus nas últimas 24 horas. Use as setas para consultar valores.', tabindex: '0'});
    for (let index=0; index<=3; index++) {const value=lo+(hi-lo)*index/3, yy=y(value); svg.append(svgNode('line',{x1:left,x2:right,y1:yy,y2:yy,class:'campus-grid'}),svgNode('text',{x:left-6,y:yy+4,'text-anchor':'end',class:'campus-axis'},number(value)));}
    for (let index=0; index<=3; index++) {const stamp=start+(end-start)*index/3, xx=left+(right-left)*index/3; svg.append(svgNode('text',{x:xx,y:211,'text-anchor':index===0?'start':index===3?'end':'middle',class:'campus-axis'},time(stamp)));}
    let path='', previous=null;
    for (const point of points) {const gap = !previous || Date.parse(point.time)-Date.parse(previous.time)>12*60000 || (key==='rain_daily' && point.value<previous.value); path += (gap?'M':'L')+x(point.time).toFixed(1)+','+y(point.value).toFixed(1)+' '; previous=point;}
    svg.append(svgNode('path',{d:path,fill:'none',class:'campus-line'}));
    for(const point of points)svg.append(svgNode('circle',{cx:x(point.time),cy:y(point.value),r:2,class:'campus-sample','aria-hidden':'true'}));
    const cursor = svgNode('line',{x1:0,x2:0,y1:top,y2:bottom,class:'campus-cursor'}), dot=svgNode('circle',{r:4,class:'campus-dot'});
    svg.append(cursor,dot); target.append(svg);
    let selected=selectedKey===key?points.findIndex(p=>p.time===selectedTime):-1; if(selected<0)selected=points.length-1;
    function show(index) {selected=Math.max(0,Math.min(points.length-1,index)); const point=points[selected], xx=x(point.time);selectedTime=point.time;selectedKey=key; cursor.setAttribute('x1',xx);cursor.setAttribute('x2',xx);dot.setAttribute('cx',xx);dot.setAttribute('cy',y(point.value));readout.textContent=date(point.time)+' · '+number(point.value)+' '+definitions[key][1];}
    svg.addEventListener('pointermove', event => {const box=svg.getBoundingClientRect(), xx=(event.clientX-box.left)/box.width*width; let nearest=0; for(let i=1;i<points.length;i++)if(Math.abs(x(points[i].time)-xx)<Math.abs(x(points[nearest].time)-xx))nearest=i;show(nearest);});
    svg.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();show(event.key==='Home'?0:event.key==='End'?points.length-1:selected+(event.key==='ArrowLeft'?-1:1));}});
    show(selected);if(keepFocus)svg.focus();
  }
  async function load(publication) {
    if (busy) return false; busy=true;
    try {
      const latest=publication || await json('./data/latest.json');
      if(latest.schema_version!==1 || latest.fixture_mode || !Number.isFinite(Date.parse(latest.generated_at)) || Date.parse(latest.generated_at)>Date.now()+600000)throw new Error('Invalid manifest');
      if(feed && Date.parse(latest.generated_at)<Date.parse(feed.publication_at))return false;
      const next=validate(await json('./data/campus_station.json'),latest.generated_at);
      feed=next;failed=false;render();return true;
    }catch(error){failed=true;render();return false;}finally{busy=false;}
  }
  selection.addEventListener('change',renderChart);
  let chartWidth=0;
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(entries=>{const width=Math.round(entries[0].contentRect.width);if(width>0&&width!==chartWidth){chartWidth=width;renderChart();}}).observe(el('campus-plot'));
  const refresh=typeof PublicationRefresh!=='undefined'?PublicationRefresh.create({getVersion:()=>feed?.publication_at,readLatest:()=>json('./data/latest.json'),reload:load,needsReload:()=>failed,isVisible:()=>!document.hidden,onError:()=>{failed=true;render();},onSuccess:()=>{failed=false;render();}}):null;
  setInterval(()=>{render();refresh?.check();},60000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden){render();refresh?.check();}});
  window.addEventListener('online',()=>refresh?.check());
  for(const id of ['refresh','reload'])el(id)?.addEventListener('click',()=>load());
  load();
})();
