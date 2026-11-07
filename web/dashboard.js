'use strict';
const panel = {data:null, history:null, mode:'forecast', variable:'precipitation_mm', hours:24, loadId:0};
const el = id => document.getElementById(id);
const colors = ['#2f8548','#377fb1','#b27a2b','#8a5a9f','#bf4e48','#458a88'];
const timeZone = 'America/Sao_Paulo';
function num(v, digits=1) { return Number.isFinite(v) ? v.toLocaleString('pt-BR',{maximumFractionDigits:digits,minimumFractionDigits:digits}) : '—'; }
function date(v) { return v && Number.isFinite(Date.parse(v)) ? new Intl.DateTimeFormat('pt-BR',{timeZone,day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(v)) : 'não informado'; }
function fresh(v, hours=3, now=Date.now()) { const t=typeof v==='string'?Date.parse(v):NaN;return Number.isFinite(t)&&now-t>=-600000&&now-t<=hours*3600000; }
function dashboardCurrent(data, now=Date.now()) { return Boolean(data&&fresh(data.generated_at,3,now)&&Number.isFinite(Date.parse(data.valid_until))&&now<Date.parse(data.valid_until)); }
function protocolCurrent(data, now=Date.now()) { return dashboardCurrent(data,now)&&Number.isFinite(Date.parse(data.assessment?.valid_until))&&now<Date.parse(data.assessment.valid_until); }
function node(tag,cls,text) { const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n; }
function safeLink(address) { try { const u=new URL(address,location.href);return u.protocol==='https:'&&((u.origin===location.origin&&/^\/criseclimatica\/references\/pn-(13|14)-2026\.pdf$/.test(u.pathname))||['ciram.epagri.sc.gov.br','www.defesacivil.sc.gov.br','defesacivil.sc.gov.br','alertas2.inmet.gov.br'].includes(u.hostname))&&!u.username&&!u.password?u.href:null; }catch{return null;} }
function officialLink(address,label) { const a=node('a','',label);const href=safeLink(address);if(href){a.href=href;a.target='_blank';a.rel='noopener noreferrer';}return a; }
function updateMetric(id,value,note) { el(id+'-value').textContent=value;el(id+'-note').textContent=note; }
function renderSummary() {
  const data=panel.data, current=dashboardCurrent(data), policy=data?.assessment, validPolicy=protocolCurrent(data);
  el('publication-time').textContent=data?'Publicado '+date(data.generated_at):'Publicação indisponível';
  el('publication-status').hidden=current;
  el('publication-status').textContent=data?'A publicação ou uma referência venceu. O enquadramento e os indicadores atuais foram retirados; isso não indica melhora.':'Não foi possível carregar uma publicação verificável de Araquari. Consulte as fontes oficiais.';
  el('level-dot').className='level-dot '+(validPolicy&&policy.suggested_level?policy.suggested_level:'neutral');
  el('level-title').textContent=!current?'Dados a atualizar':policy?.suggested_level&&validPolicy?policy.title:'Em avaliação';
  el('level-kind').textContent=validPolicy&&policy?.suggested_level?'Sugerido · confirmar':'A verificar';
  el('level-reason').textContent=!current?'As referências atuais não permitem manter uma leitura do nível. Confira novas publicações e os canais oficiais.':policy.reason;
  const evidence=(policy?.evidence||[]).find(n=>n.status==='eligible');
  el('priority-title').textContent=current&&evidence?evidence.title:current?'Conferir avisos prioritários':'Verificar atualização das fontes';
  el('priority-description').textContent=current&&evidence?`${evidence.regions_text||'Abrangência a conferir'} · ${date(evidence.valid_from)} a ${date(evidence.valid_until)}. ${evidence.supports_level?'Trecho explícito sustenta a leitura sugerida.':'O texto disponível requer avaliação do enquadramento.'}`:'A Epagri/Ciram é a referência prioritária. Falta de aviso ou indisponibilidade não comprova normalidade.';
  const complementary=(data?.complementary_notices?.notices||[]).filter(n=>n.lifecycle!=='expired');
  if(current&&data.complementary_notices?.status==='available'&&complementary.length)el('priority-description').textContent+=` Há ${complementary.length} aviso(s) INMET complementar(es); confira validade e abrangência nas evidências.`;
  el('priority-link').href=current&&evidence&&safeLink(evidence.url)?safeLink(evidence.url):'https://ciram.epagri.sc.gov.br/index.php/avisos-meteorologicos/';
  const gauges=data?.gauge_distribution;
  if(current&&gauges?.status==='available') {
    const median=Number.isFinite(gauges.median_mm);
    updateMetric('observed',num(median?gauges.median_mm:gauges.maximum_mm)+' mm',`${median?'Mediana':'Maior leitura'} · ${gauges.station_count} estação(ões) · máx. ${num(gauges.maximum_mm)} mm`);
  } else updateMetric('observed','—','Sem leitura local válida · não é chuva zero');
  const f=data?.forecast, rain=f?.rain, gust=f?.wind?.gust_kmh, heat=f?.heat;
  updateMetric('forecast',current&&rain?.status==='complete'?num(rain.total_mm)+' mm':'—',current&&rain?.status==='complete'?`${date(rain.start_at)} a ${date(rain.end_at)}`:'Janela incompleta ou referência vencida');
  updateMetric('gust',current&&Number.isFinite(gust?.maximum)?num(gust.maximum)+' km/h':'—',current&&gust?.at?date(gust.at):'Sem série completa de 24 h');
  updateMetric('temperature',current&&Number.isFinite(heat?.maximum_c)?num(heat.maximum_c)+' °C':'—',current&&heat?.maximum_at?date(heat.maximum_at):'Sem série completa de 24 h');
  const peak=f?.rain_peaks?.find(p=>p.hours===3), revision=data?.revision;
  let reading=current&&peak?`A chuva prevista se concentra entre ${date(peak.start_at)} e ${date(peak.end_at)}: ${num(peak.total_mm)} mm na maior janela de 3 horas.`:'A distribuição temporal depende de séries completas e recentes; ausência de dados não indica redução do evento.';
  if(current&&revision?.status==='comparable_publications')reading+=` Para os mesmos horários futuros, a chuva passou de ${num(revision.previous_rain_mm)} para ${num(revision.current_rain_mm)} mm entre publicações. Essa revisão não mede precisão.`;
  else if(current)reading+=' A revisão da previsão ainda não tem publicação anterior compatível.';
  el('scenario-reading').textContent=reading;
}
function getChartSeries(data,history,mode,variable,hours,now=Date.now()) {
  if(mode==='forecast') {
    const base=Date.parse(data?.forecast?.start_at),end=base+hours*3600000;
    const fields=variable==='gust_kmh'?['wind_kmh','gust_kmh']:[variable];
    const names={precipitation_mm:'Chuva prevista · acumulado horário',wind_kmh:'Vento previsto',gust_kmh:'Rajada prevista',temperature_c:'Temperatura prevista'};
    return fields.map((field,i)=>({id:field,name:names[field],color:colors[i],field,
      points:(data?.forecast_series||[]).filter(r=>{const t=Date.parse(r.time);return Number.isFinite(t)&&(field==='precipitation_mm'?t>base&&t<=end:t>=base&&t<end);}).map(r=>({time:r.time,value:Number.isFinite(r[field])?r[field]:null})),gapMs:3600001}));
  }
  const field=variable==='precipitation_mm'?'rain_24h_mm':variable;
  const fields=variable==='gust_kmh'?['wind_kmh','gust_kmh']:[field];
  const rows=Array.isArray(history?.records)?history.records:[];
  const grouped=new Map();
  for(const r of rows) {
    const t=Date.parse(r.observed_at);
    if(!Number.isFinite(t)||t>now+600000||t<now-hours*3600000)continue;
    for(const key of fields) {
      if(!Number.isFinite(r[key]))continue;
      const id=r.source+':'+r.station+':'+key;
      if(!grouped.has(id))grouped.set(id,{id,name:`${r.source==='metar'?'METAR':'Cemaden'} ${r.station}${variable==='gust_kmh'?(key==='gust_kmh'?' · rajada':' · vento'):''}`,field:key,points:[],gapMs:4*3600000});
      grouped.get(id).points.push({time:r.observed_at,value:r[key]});
    }
  }
  return [...grouped.values()].sort((a,b)=>a.id.localeCompare(b.id)).map((s,i)=>({...s,color:colors[i%colors.length],points:s.points.sort((a,b)=>Date.parse(a.time)-Date.parse(b.time))}));
}
function svg(tag,attrs={},text) { const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;return n; }
function renderChart() {
  const target=el('plot'),legend=el('chart-legend'),tooltip=el('chart-tooltip');target.replaceChildren();legend.replaceChildren();tooltip.hidden=true;
  const data=panel.data, observed=panel.mode==='observed';
  const series=getChartSeries(data,panel.history,panel.mode,panel.variable,panel.hours);
  const points=series.flatMap(s=>s.points.filter(p=>Number.isFinite(p.value)).map(p=>({...p,series:s})));
  const label=panel.variable==='precipitation_mm'?(observed?'Chuva observada · acumulado móvel de 24 h':'Chuva prevista por hora'):panel.variable==='temperature_c'?'Temperatura':'Vento e rajadas';
  const unit=panel.variable==='temperature_c'?'°C':panel.variable==='precipitation_mm'?'mm':'km/h';
  el('chart-heading').textContent=label;
  if(!points.length){target.append(node('p','empty',observed?'O histórico observado ainda não tem amostras válidas para esta variável e período. Ele será formado a partir das publicações.':'Sem série horária utilizável nesta publicação.'));el('chart-period').textContent='Sem série';el('chart-caption').textContent='Dados ausentes não indicam melhora ou normalidade.';return;}
  const times=points.map(p=>Date.parse(p.time));let minT=Math.min(...times),maxT=Math.max(...times);if(maxT===minT){minT-=1800000;maxT+=1800000;}
  const vals=points.map(p=>p.value);let low=panel.variable==='temperature_c'?Math.min(...vals)-1:0,high=Math.max(...vals);if(high<=low)high=low+1;high+=(high-low)*.13;
  const W=1050,H=230,L=47,R=15,T=15,B=35,w=W-L-R,h=H-T-B;
  const x=t=>L+(t-minT)/(maxT-minT)*w,y=v=>T+h-(v-low)/(high-low)*h;
  const root=svg('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':`${label} (${unit}). Use setas para consultar horários.`,tabindex:0});
  for(let i=0;i<=4;i++){const value=low+(high-low)*i/4;root.append(svg('line',{x1:L,x2:W-R,y1:y(value),y2:y(value),class:'chart-grid'}),svg('text',{x:L-9,y:y(value)+4,'text-anchor':'end',class:'chart-label'},num(value,panel.variable==='precipitation_mm'?1:0)));}
  for(let i=0;i<=4;i++){const t=minT+(maxT-minT)*i/4;root.append(svg('text',{x:x(t),y:H-9,'text-anchor':i===0?'start':i===4?'end':'middle',class:'chart-label'},date(new Date(t).toISOString())));}
  for(const s of series) {
    let path='',last=null;const paths=[];
    for(const p of s.points){const t=Date.parse(p.time);if(!Number.isFinite(p.value)){if(path)paths.push(path);path='';last=null;continue;}if(last!==null&&t-last>s.gapMs){if(path)paths.push(path);path='';}path+=(path?' L':'M')+x(t).toFixed(2)+','+y(p.value).toFixed(2);last=t;}
    if(path)paths.push(path);
    for(const d of paths)root.append(svg('path',{d,fill:'none',stroke:s.color,'stroke-width':2.2,'stroke-linejoin':'round','stroke-linecap':'round'}));
    for(const p of s.points.filter(p=>Number.isFinite(p.value))){const circle=svg('circle',{cx:x(Date.parse(p.time)),cy:y(p.value),r:s.points.length<=8?3.5:2.2,fill:s.color});circle.append(svg('title',{},`${s.name}: ${num(p.value)} ${unit} · ${date(p.time)}`));root.append(circle);}
    if(s.points.some(p=>Number.isFinite(p.value))){const item=node('span','legend-item');const dot=node('i','legend-dot');dot.style.background=s.color;item.append(dot,node('span','',s.name));legend.append(item);}
  }
  const guide=svg('line',{x1:L,x2:L,y1:T,y2:T+h,stroke:'#7b9680','stroke-dasharray':'3 4',visibility:'hidden'});root.append(guide);
  const instants=[...new Set(times)].sort((a,b)=>a-b);let cursor=0;
  function show(t){const nearest=instants.reduce((a,b)=>Math.abs(b-t)<Math.abs(a-t)?b:a,instants[0]);cursor=instants.indexOf(nearest);const rows=series.flatMap(s=>s.points.filter(p=>Date.parse(p.time)===nearest&&Number.isFinite(p.value)).map(p=>`${s.name}: ${num(p.value)} ${unit}`));tooltip.textContent=date(new Date(nearest).toISOString())+' · '+rows.join(' | ');tooltip.hidden=false;guide.setAttribute('x1',x(nearest));guide.setAttribute('x2',x(nearest));guide.setAttribute('visibility','visible');}
  root.addEventListener('pointermove',e=>{const box=root.getBoundingClientRect();const position=(e.clientX-box.left)/box.width*W;show(minT+(position-L)/w*(maxT-minT));});
  root.addEventListener('click',e=>{const box=root.getBoundingClientRect();show(minT+((e.clientX-box.left)/box.width*W-L)/w*(maxT-minT));});
  root.addEventListener('keydown',e=>{if(!['ArrowRight','ArrowLeft','Home','End'].includes(e.key))return;e.preventDefault();cursor=e.key==='Home'?0:e.key==='End'?instants.length-1:Math.max(0,Math.min(instants.length-1,cursor+(e.key==='ArrowRight'?1:-1)));show(instants[cursor]);});
  target.append(root);el('chart-period').textContent=`${date(new Date(Math.min(...times)).toISOString())} — ${date(new Date(Math.max(...times)).toISOString())}`;
  el('chart-caption').textContent=(observed?'Amostras instrumentais por estação; linhas interrompidas em lacunas superiores a 4 h. Acumulados de 24 h não são somados.':'Open-Meteo · modelo para o ponto de referência de Araquari. Chuva em T corresponde à hora anterior; séries incompletas mantêm lacunas.')+' '+(!dashboardCurrent(data)?'Publicação vencida: gráfico apenas como referência anterior. ':'')+'Passe o ponteiro, toque ou use as setas no gráfico.';
}
function paragraph(host,text,cls='') {host.append(node('p',cls,text));}
function openDialog(title,render) {const dialog=el('detail-dialog');el('dialog-title').textContent=title;const body=el('dialog-content');body.replaceChildren();render(body);if(!dialog.open)dialog.showModal();}
function showEvidence() {
  openDialog('Evidências de Araquari',body=>{
    const data=panel.data;if(!data){paragraph(body,'Publicação não disponível.');return;}
    paragraph(body,dashboardCurrent(data)?'Referências da publicação atual.':'Estas referências venceram; não sustentam uma conclusão atual.','notice');
    body.append(node('h3','','Avisos prioritários · Epagri/Ciram'));
    for(const e of data.assessment?.evidence||[]){const card=node('article','evidence-block');card.append(officialLink(e.url,e.title));paragraph(card,`${e.regions_text||'Abrangência não confirmada'} · ${date(e.valid_from)} a ${date(e.valid_until)}`);paragraph(card,`Estado na análise: ${e.status==='eligible'?'território e janela explicitados':e.status==='expired'?'prazo encerrado':'requer verificação'}. ${e.matched_cue?'Trecho usado: “'+e.matched_cue+'”.':'Sem correspondência qualitativa suficiente.'}`);body.append(card);}
    const gauges=data.gauge_distribution;body.append(node('h3','','Chuva observada · estações do município'));
    paragraph(body,`Cemaden · ${gauges?.station_count||0} estação(ões) com janelas de 24 h e horários de fim a até 30 min entre si. ${gauges?.excluded_time_count||0} referência(s) excluída(s) por tempo ou conflito.`);
    if(gauges?.status==='available'){paragraph(body,`Mínima ${num(gauges.minimum_mm)} mm · ${Number.isFinite(gauges.median_mm)?'mediana '+num(gauges.median_mm)+' mm':'mediana não apresentada com menos de 3 estações'} · máxima ${num(gauges.maximum_mm)} mm. Isso descreve pontos de estação, não uma média municipal.`);for(const s of gauges.stations||[])paragraph(body,`${s.code} · ${num(s.rain_24h_mm)} mm · fim da janela: ${date(s.observed_at)}.`);}
    body.append(node('h3','','Previsão e observações próximas'));
    for(const p of data.forecast?.rain_peaks||[])paragraph(body,`Open-Meteo · maior janela de ${p.hours} h: ${num(p.total_mm)} mm, de ${date(p.start_at)} a ${date(p.end_at)}.`);
    for(const r of data.recent_observations||[])paragraph(body,`${r.source} ${r.code} · ${num(r.distance_km)} km do ponto municipal · ${date(r.observed_at)} · temperatura ${num(r.temperature_c)} °C; vento ${num(r.wind_kmh)} km/h; rajada ${num(r.gust_kmh)} km/h. ${Date.now()<Date.parse(r.valid_until)?'':'Referência vencida.'}`);
    body.append(node('h3','','Avisos complementares · INMET'));
    const notices=data.complementary_notices;paragraph(body,`Estado da consulta: ${notices?.status||'indisponível'}. Cores do INMET não são convertidas em níveis deste protocolo.`);
    for(const n of notices?.notices||[])paragraph(body,`${n.type} · ${n.severity} · ${n.window_as_reported||'janela não informada'}. Fuso/validade: ${n.temporal_relation==='unverified_timezone_or_window'?'não conciliados':'conforme a referência original'}.`);
    body.append(node('h3','','Qualidade das fontes'));
    for(const s of data.source_status||[])paragraph(body,`${s.source} · ${s.role} · ${s.status} · referência ${date(s.reference_at)}.`);
    const a=node('a','','Todas as estações e fontes →');a.href='./dados.html';body.append(a);
  });
}
function showProtocol() {
  openDialog('Níveis e referências normativas',body=>{
    const data=panel.data,policy=data?.assessment,ref=data?.protocol;
    paragraph(body,'Referência: PN 13/2026 e PN 14/2026 — ASSINST/REI, de 04/11/2026. Não é um painel oficial nem uma comunicação de funcionamento.');
    if(policy){paragraph(body,protocolCurrent(data)?policy.reason:'O enquadramento desta publicação perdeu validade.','notice');for(const p of policy.pending||[])paragraph(body,p);}
    const grid=node('div','levels-grid');for(const level of ref?.levels||[]){const item=node('article','level-reference');const h=node('h3');h.append(node('span','level-dot '+level.id),node('span','',level.id[0].toUpperCase()+level.id.slice(1)+' · '+level.name));item.append(h);paragraph(item,level.criterion);paragraph(item,level.orientation);paragraph(item,level.reference,'small');grid.append(item);}body.append(grid);
    body.append(node('h3','','Prioridade e competência'));paragraph(body,'Avisos Epagri/Ciram são prioritários; Defesa Civil estadual e municipal e outros órgãos são complementares. A decisão formal e sua vigência competem à Direção-Geral, nos termos da PN 13, arts. 4º, 5º e 13.');
    body.append(node('h3','','Prazos de comunicação · PN 13, art. 12'));
    for(const r of ref?.communication_deadlines||[])paragraph(body,`${r.shift}: ${r.deadline}.`);paragraph(body,ref?.sudden_aggravation||'Emergências permitem comunicação a qualquer momento.');
    body.append(node('h3','','Continuidade acadêmica · PN 14'));
    for(const r of ref?.academic_rules||[])paragraph(body,r);
    for(const d of ref?.documents||[]){const p=node('p');p.append(officialLink(d.url,`Abrir PN ${d.number}/${d.year} · documento de referência ↗`));body.append(p);}
  });
}
function showMethods() {
  openDialog('Métodos e limites da análise',body=>{
    paragraph(body,'Medições, previsões e avisos são produtos distintos. A quantidade de fontes não é uma pontuação de confiança. Médias de municípios ou de estações distantes não determinam o nível.');
    body.append(node('h3','','Chuva observada'));paragraph(body,'Agrupam-se apenas estações retornadas para o IBGE de Araquari, com janelas de 24 h e fim a até 30 min da referência mais recente. A mediana só aparece com ao menos três estações. Mínimo, máximo, quantidade e horários ficam acessíveis; extremos não são apagados pela mediana.');
    body.append(node('h3','','Evolução e revisão'));paragraph(body,'A previsão horária mantém lacunas e distingue vento de rajada. Totais e picos de 24 h exigem série completa. Revisões comparam os mesmos horários futuros e a mesma referência de grade; não são erro do modelo. O histórico observado acumula amostras por estação por sete dias, sem preencher períodos anteriores à sua implantação.');
    const heat=panel.data?.forecast?.heat;if(heat?.status==='complete')paragraph(body,`Temperatura prevista: ${heat.hours_at_or_above} referências horárias ≥ ${heat.reference_c} °C; maior sequência ${heat.longest_sequence_hours}. É uma referência descritiva, não classificação normativa de calor ou sensação térmica.`);
    for(const pair of panel.data?.temperature_context?.pairs||[])paragraph(body,`Comparação exploratória: modelo ${num(pair.model_c)} °C (${date(pair.model_at)}), METAR ${pair.icao} ${num(pair.observed_c)} °C (${date(pair.observed_at)}), ${num(pair.distance_km)} km. Altitude e protocolos não conciliados; não se calcula erro.`);
    body.append(node('h3','','Níveis qualitativos'));paragraph(body,'A PN 13 não contém faixas numéricas para chuva, vento ou temperatura. O enquadramento sugerido usa somente expressões afirmativas de impacto ou perigo em aviso prioritário com abrangência e validade verificáveis. Não há equivalência automática entre cores do INMET e os seis níveis. Decreto, danos locais e funcionamento não são inferidos.');
    paragraph(body,'Referências vencidas retiram o enquadramento e os indicadores atuais. Ausência ou expiração de aviso não comprova melhora, segurança de deslocamento ou autorização para retomada.');
    for(const limit of panel.data?.limitations||[])paragraph(body,limit);
  });
}
async function readJson(path) {const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),15000);try{const response=await fetch(path,{cache:'no-store',signal:controller.signal});if(!response.ok)throw new Error('HTTP '+response.status);return await response.json();}finally{clearTimeout(timer);}}
async function loadDashboard() {
  const id=++panel.loadId;el('refresh').disabled=true;
  try{
    let loaded;
    for(let attempt=0;attempt<2;attempt++){
      const [latest,data,history]=await Promise.all([readJson('./data/latest.json'),readJson('./data/dashboard.json'),readJson('./data/observation_history.json').catch(()=>null)]);
      if(latest.schema_version!==1||latest.fixture_mode||data.fixture_mode||data.schema_version!==1||data.kind!=='araquari_weather_dashboard_not_official_decision'||data.location_id!=='araquari'||data.decision_automated!==false)throw new Error('Invalid dashboard source');
      if(latest.generated_at===data.generated_at){loaded={data,history:history?.kind==='araquari_point_observation_history_not_climatology'&&history?.location_id==='araquari'&&!history.fixture_mode&&history.generated_at===data.generated_at?history:null};break;}
    }
    if(!loaded)throw new Error('Publication mismatch');if(id!==panel.loadId)return;
    panel.data=loaded.data;panel.history=loaded.history;
  }catch(err){if(id!==panel.loadId)return;console.error('Dashboard unavailable:',err.message);panel.data=null;panel.history=null;}
  finally{if(id===panel.loadId){el('refresh').disabled=false;renderSummary();renderChart();}}
}
function selectVariable(variable) {panel.variable=variable;for(const button of document.querySelectorAll('[data-variable]')){const selected=button.dataset.variable===variable;button.classList.toggle('active',selected);button.setAttribute('aria-pressed',String(selected));}renderChart();}
if(typeof module!=='undefined')module.exports={fresh,dashboardCurrent,protocolCurrent,getChartSeries};
if(typeof document!=='undefined'){
  el('refresh').addEventListener('click',loadDashboard);
  for(const b of document.querySelectorAll('[data-variable]'))b.addEventListener('click',()=>selectVariable(b.dataset.variable));
  for(const b of document.querySelectorAll('[data-focus]'))b.addEventListener('click',()=>{selectVariable(b.dataset.focus);el('chart-heading').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});});
  for(const b of document.querySelectorAll('[data-mode]'))b.addEventListener('click',()=>{panel.mode=b.dataset.mode;for(const button of document.querySelectorAll('[data-mode]')){const selected=button===b;button.classList.toggle('active',selected);button.setAttribute('aria-pressed',String(selected));}const long=el('chart-range').querySelector('option[value="240"]');if(long)long.disabled=panel.mode==='observed';if(panel.mode==='observed'&&panel.hours>168){panel.hours=168;el('chart-range').value='168';}renderChart();});
  el('chart-range').addEventListener('change',event=>{panel.hours=Number(event.target.value);renderChart();});
  el('evidence-open').addEventListener('click',showEvidence);el('level-explain').addEventListener('click',showProtocol);el('protocol-open').addEventListener('click',showProtocol);el('methods-open').addEventListener('click',showMethods);el('dialog-close').addEventListener('click',()=>el('detail-dialog').close());
  setInterval(()=>{renderSummary();if(!dashboardCurrent(panel.data)&&el('detail-dialog').open)el('detail-dialog').close();},60000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden){renderSummary();renderChart();if(!dashboardCurrent(panel.data)&&el('detail-dialog').open)el('detail-dialog').close();}});
  loadDashboard();
}
