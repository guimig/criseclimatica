'use strict';
const panel = {data:null, history:null, mode:'context', variable:'precipitation_mm', hours:24, rainWindow:24, observedVariable:'precipitation_mm', station:'all', scope:'local', observedView:'auto', loadId:0};
const el = id => document.getElementById(id);
const colors = ['#2f8548','#377fb1','#b27a2b','#8a5a9f','#bf4e48','#458a88'];
const timeZone = 'America/Sao_Paulo';
function num(v, digits=1) { return Number.isFinite(v) ? v.toLocaleString('pt-BR',{maximumFractionDigits:digits,minimumFractionDigits:digits}) : '—'; }
function date(v) { return v && Number.isFinite(Date.parse(v)) ? new Intl.DateTimeFormat('pt-BR',{timeZone,day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(v)) : 'não informado'; }
function fresh(v, hours=3, now=Date.now()) { const t=typeof v==='string'?Date.parse(v):NaN;return Number.isFinite(t)&&now-t>=-600000&&now-t<=hours*3600000; }
function dashboardCurrent(data, now=Date.now()) { return Boolean(data&&fresh(data.generated_at,3,now)&&Number.isFinite(Date.parse(data.valid_until))&&now<Date.parse(data.valid_until)); }
function protocolCurrent(data, now=Date.now()) { return dashboardCurrent(data,now)&&Number.isFinite(Date.parse(data.assessment?.valid_until))&&now<Date.parse(data.assessment.valid_until); }
function effectiveAssessment(data,now=Date.now()) {
  const policy=data?.assessment;
  if(protocolCurrent(data,now))return policy;
  const base=policy?.base_assessment;
  if(dashboardCurrent(data,now)&&base&&now<Date.parse(base.valid_until)) {
    return base.suggested_level?base:{...base,monitoring_state:'partial',monitoring_label:'Monitoramento parcial',title:'Monitoramento parcial',reason:'As referências de curta duração venceram. Previsões e outras evidências ainda válidas continuam disponíveis; confira a próxima atualização.'};
  }
  return policy;
}
function node(tag,cls,text) { const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n; }
function safeLink(address) { try { const u=new URL(address,location.href);return u.protocol==='https:'&&((u.origin===location.origin&&/^\/criseclimatica\/references\/pn-(13|14)-2026\.pdf$/.test(u.pathname))||['ciram.epagri.sc.gov.br','www.defesacivil.sc.gov.br','defesacivil.sc.gov.br','alertas2.inmet.gov.br','avisos.inmet.gov.br','portal.inmet.gov.br'].includes(u.hostname))&&!u.username&&!u.password?u.href:null; }catch{return null;} }
function officialLink(address,label) { const a=node('a','',label);const href=safeLink(address);if(href){a.href=href;a.target='_blank';a.rel='noopener noreferrer';}return a; }
function updateMetric(id,value,note) { el(id+'-value').textContent=value;el(id+'-note').textContent=note; }
const riskNames={verde:'Normalidade',azul:'Preparação',amarelo:'Atenção',laranja:'Alerta',vermelho:'Alerta máximo',roxo:'Calamidade'};
const variableNames={rain_1h_mm:'chuva em 1 hora',rain_24h_mm:'chuva em 24 horas',wind_kmh:'vento',gust_kmh:'rajadas de vento'};
function stationName(ref,fallback='Estação sem nome') {
  const raw=typeof ref?.name==='string'?ref.name.trim():'';
  const name=raw&&raw!==ref.station?raw.replace(/^cemaden\s*/i,'').trim():fallback;
  return name||fallback;
}
function signalDescription(signal,data) {
  const observed=signal.kind==='observation',ref=stationReference(data,signal.source==='cemaden'?'cemaden-rain':signal.source,signal.station);
  const where=observed?` em ${stationName(ref,'uma estação próxima')}`:' para Araquari';
  return `${observed?'Medição':'Previsão'} de ${variableNames[signal.variable]||'condição meteorológica'}${where}: ${num(signal.value)} ${signal.unit}, ${date(signal.start_at)}${signal.start_at!==signal.end_at?' a '+date(signal.end_at):''}.`;
}
function signalBrief(signal,data) {
  const observed=signal.kind==='observation',ref=stationReference(data,signal.source==='cemaden'?'cemaden-rain':signal.source,signal.station);
  const subject=variableNames[signal.variable]||'condição meteorológica';
  const plural=signal.variable==='gust_kmh',masculine=signal.variable==='wind_kmh';
  const verb=observed?(plural?'medidas':masculine?'medido':'medida'):(plural?'previstas':masculine?'previsto':'prevista');
  return `${subject[0].toUpperCase()+subject.slice(1)} ${verb}${observed?' em '+stationName(ref,'estação próxima'):''}: ${num(signal.value)} ${signal.unit}.`;
}
function riskPresentation(data,now=Date.now()) {
  if(!dashboardCurrent(data,now))return {color:'neutral',active:null,title:'Atualização necessária',kind:'Dados desatualizados',reason:'A última atualização perdeu validade. Consulte as fontes oficiais enquanto aguarda novos dados.'};
  const policy=effectiveAssessment(data,now),objective=policy?.numeric_support;
  if(!policy||!(now<Date.parse(policy.valid_until)))return {color:'neutral',active:null,title:'Dados insuficientes para classificar',kind:'Leitura parcial',reason:'Não há referências válidas suficientes para distinguir normalidade de uma situação de atenção.'};
  const signals=(objective?.signals||[]).filter(s=>s.band>0).sort((a,b)=>Number(a.period_proxy)-Number(b.period_proxy)||b.band-a.band);
  const highest=signals[0],families=[...new Set(signals.filter(s=>!s.period_proxy).map(s=>s.variable.startsWith('rain_')?'chuva':'vento'))],description=highest?signalDescription(highest,data):'';
  if(policy.suggested_level)return {color:policy.suggested_level,active:policy.suggested_level,title:riskNames[policy.suggested_level]||policy.title,kind:'Nível sugerido · '+policy.suggested_level,
    reason:description||'Um aviso Epagri/Ciram para a região contém informações compatíveis com este nível. Confira o período e a abrangência nos detalhes.'};
  if(policy.monitoring_state==='routine'&&objective?.core_complete&&objective.maximum_band===0&&objective.signals?.length)return {color:'verde',active:'verde',title:'Normalidade nos dados acompanhados',kind:'Referência verde · leitura consultiva',reason:'As fontes necessárias foram consultadas e os dados válidos de chuva e vento estão abaixo das faixas de atenção utilizadas. Nenhum aviso aplicável foi identificado. É uma leitura do painel, não uma declaração institucional.'};
  if(highest)return {color:'amarelo',active:null,title:'Atenção a '+(families.length>1?'chuva e vento':highest.variable.startsWith('rain_')?'chuva':highest.variable==='gust_kmh'?'rajadas de vento':'vento'),kind:'Referência amarela · atenção',reason:signals.slice(0,2).map(signal=>signalDescription(signal,data)).join(' ')};
  if(policy.monitoring_state==='official_context')return {color:'amarelo',active:null,title:'Há aviso meteorológico para conferir',kind:'Referência amarela · conferir aviso',reason:'Uma publicação oficial pode ser relevante para Araquari. A abrangência ou o conteúdo ainda não permite sugerir um nível específico; abra as evidências.'};
  return {color:'neutral',active:null,title:'Dados insuficientes para classificar',kind:'Leitura parcial',reason:'Há informações disponíveis, mas faltam referências válidas para uma leitura completa. Falta de dados não significa normalidade.'};
}
function renderSummary() {
  if(typeof ForecastComparison!=='undefined')ForecastComparison.renderCompact(el('forecast-comparison'),panel.data?.forecast_comparison);
  const data=panel.data, current=dashboardCurrent(data), policy=effectiveAssessment(data), validPolicy=current&&Date.now()<Date.parse(policy?.valid_until);
  el('publication-time').textContent=data?'Painel atualizado em '+date(data.generated_at):'Atualização indisponível';
  el('publication-status').hidden=current;
  el('publication-status').textContent=data?'A publicação ou uma referência venceu. O enquadramento e os indicadores atuais foram retirados; isso não indica melhora.':'Não foi possível carregar uma publicação verificável de Araquari. Consulte as fontes oficiais.';
  const presentation=riskPresentation(data);
  el('level-dot').className='level-dot '+presentation.color;
  el('level-card').dataset.risk=presentation.color;
  el('level-title').textContent=presentation.title;el('level-kind').textContent=presentation.kind;
  el('level-reason').textContent=presentation.reason;
  el('technical-summary').textContent='';el('technical-summary').hidden=true;
  for(const item of document.querySelectorAll('[data-risk-level]')){
    const active=item.dataset.riskLevel===presentation.active;item.classList.toggle('is-active',active);
    if(active)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');
  }
  const evidence=(policy?.evidence||[]).find(n=>n.status==='eligible');
  el('priority-title').textContent=current&&evidence?evidence.title:current?'Conferir avisos prioritários':'Verificar atualização das fontes';
  el('priority-description').textContent=current&&evidence?`${evidence.regions_text||'Abrangência a conferir'} · ${date(evidence.valid_from)} a ${date(evidence.valid_until)}. ${evidence.supports_level?'Trecho explícito sustenta a leitura sugerida.':'O texto disponível requer avaliação do enquadramento.'}`:'A Epagri/Ciram é a referência prioritária. Falta de aviso ou indisponibilidade não comprova normalidade.';
  if(current&&!evidence){
    const source=data.source_status?.find(s=>s.source==='Epagri/Ciram · avisos');
    const sourceReady=['available','cached','no_recent_notices'].includes(source?.status)&&fresh(source?.reference_at,6);
    el('priority-title').textContent=sourceReady?'Fontes oficiais acompanhadas':'Cobertura da fonte prioritária';
    el('priority-description').textContent=sourceReady?'Consulta Epagri/Ciram registrada. Nenhum aviso com abrangência e validade aplicáveis foi confirmado nesta publicação. O acompanhamento continua.':'A referência Epagri/Ciram está ausente ou desatualizada. A leitura técnica das outras fontes continua disponível, com essa limitação identificada.';
  }
  const complementary=(data?.complementary_notices?.notices||[]).filter(n=>n.lifecycle!=='expired');
  if(current&&data.complementary_notices?.status==='available'&&complementary.length)el('priority-description').textContent+=` Há ${complementary.length} aviso(s) INMET complementar(es); confira validade e abrangência nas evidências.`;
  el('priority-link').href=current&&evidence&&safeLink(evidence.url)?safeLink(evidence.url):'https://ciram.epagri.sc.gov.br/index.php/avisos-meteorologicos/';
  const gauges=data?.gauge_distribution;
  if(current&&gauges?.status==='available') {
    const median=Number.isFinite(gauges.median_mm);
    updateMetric('observed',num(median?gauges.median_mm:gauges.maximum_mm)+' mm',`${median?'Mediana':'Maior leitura'} · ${gauges.station_count} estações · maior: ${num(gauges.maximum_mm)} mm`);
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
function stationReference(data,source,station) {
  return [...(data?.station_catalog||[]),...(data?.regional_rain_context?.stations||[])].find(r=>r.source===source&&r.station===station)||{};
}
function getChartSeries(data,history,mode,variable,hours,now=Date.now(),observedRainField='rain_1h_mm') {
  const anchor=Number.isFinite(Date.parse(data?.generated_at))?Date.parse(data.generated_at):now;
  if(mode==='context')return [
    ...getChartSeries(data,history,'observed',variable,hours,anchor,observedRainField).map(s=>({...s,kind:'observation'})),
    ...getChartSeries(data,history,'forecast',variable,hours,anchor).map(s=>({...s,kind:'forecast'}))];
  if(mode==='forecast') {
    const base=Date.parse(data?.forecast?.start_at),end=base+hours*3600000;
    const fields=variable==='gust_kmh'?['wind_kmh','gust_kmh']:[variable];
    const names={precipitation_mm:'Chuva prevista · 1 h',wind_kmh:'Vento previsto',gust_kmh:'Rajada prevista',temperature_c:'Temperatura prevista'};
    return fields.map((field,i)=>({id:field,name:names[field],color:colors[i],field,kind:'forecast',
      points:(data?.forecast_series||[]).filter(r=>{const t=Date.parse(r.time);return Number.isFinite(t)&&(field==='precipitation_mm'?t>base&&t<=end:t>=base&&t<end);})
        .map(r=>({time:r.time,value:Number.isFinite(r[field])?r[field]:null,
          start_at:field==='precipitation_mm'?new Date(Date.parse(r.time)-3600000).toISOString():null})),gapMs:3600001}));
  }
  const field=variable==='precipitation_mm'?(observedRainField||'rain_1h_mm'):variable;
  const fields=variable==='gust_kmh'?['wind_kmh','gust_kmh']:[field];
  const rows=Array.isArray(history?.records)?history.records:[],grouped=new Map();
  for(const r of rows) {
    const t=Date.parse(r.observed_at);
    if(!Number.isFinite(t)||t>anchor||t<anchor-hours*3600000)continue;
    for(const key of fields) {
      if(!Number.isFinite(r[key]))continue;
      const id=r.source+':'+r.station+':'+key,ref=stationReference(data,r.source,r.station);
      const name=stationName(ref,'Estação sem nome');
      if(!grouped.has(id))grouped.set(id,{id,station:r.station,source:r.source,reference:ref,
        name:`${name}${ref.municipality&&String(ref.municipality).trim().toLocaleLowerCase('pt-BR')!=='araquari'?' · '+ref.municipality:''}${variable==='gust_kmh'?(key==='gust_kmh'?' · rajada':' · vento'):''}`,
        field:key,points:[],gapMs:4*3600000,kind:'observation'});
      grouped.get(id).points.push({time:r.observed_at,value:r[key],distance_km:r.distance_km,
        start_at:key.startsWith('rain_')?new Date(t-(key==='rain_24h_mm'?24:1)*3600000).toISOString():null});
    }
  }
  const order=[...new Set([...grouped.values()].map(s=>s.station))].sort();
  return [...grouped.values()].sort((a,b)=>a.id.localeCompare(b.id)).map((s,i)=>({...s,name:s.name.replace('Estação sem nome','Estação '+(order.indexOf(s.station)+1)),color:colors[i%colors.length],points:s.points.sort((a,b)=>Date.parse(a.time)-Date.parse(b.time))}));
}
function comparableReadings(series,anchor,windowHours) {
  const rows=series.filter(s=>s.points.length).map(s=>({series:s,point:s.points[s.points.length-1]}));
  if(!rows.length)return {rows,cohort:[]};
  const latest=Math.max(...rows.map(r=>Date.parse(r.point.time))),age=anchor-latest;
  const cohort=age>=0&&age<=(windowHours===1?1:6)*3600000?rows.filter(r=>Date.parse(r.point.time)===latest):[];
  return {rows,cohort};
}
function svg(tag,attrs={},text) { const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;return n; }
function pointDescription(series,p,unit,anchor) {
  const interval=p.start_at?`${date(p.start_at)} a ${date(p.time)} · acumulado de ${series.field==='rain_24h_mm'?24:1} h`:`Leitura em ${date(p.time)}`;
  const current=series.kind==='forecast'&&p.start_at&&Date.parse(p.start_at)<anchor&&Date.parse(p.time)>anchor?' · inclui a hora em curso':'';
  return `${series.name}: ${num(p.value)} ${unit} · ${interval}${current}`;
}
function chartScale(values,temperature=false) {
  const min=temperature?Math.min(...values)-1:0,max=Math.max(...values),range=Math.max(1,max-min);
  const power=10**Math.floor(Math.log10(range/5)),normalized=range/5/power;
  const step=([1,2,2.5,5,10].find(v=>v>=normalized)||10)*power;
  return {low:Math.floor(min/step)*step,high:Math.max(Math.ceil(max/step)*step,Math.floor(min/step)*step+step),step};
}
function drawStationSnapshot(target,legend,tooltip,series,unit,sharedScale=null) {
  target.replaceChildren();legend.replaceChildren();tooltip.hidden=true;
  const latest=series.filter(s=>s.points.length).map(s=>({s,p:s.points[s.points.length-1]}));
  if(!latest.length){target.append(node('p','empty','Sem leituras de chuva para este recorte. Consulte a cobertura e os horários nos detalhes.'));return;}
  const scale=sharedScale||chartScale(latest.map(r=>r.p.value)),W=Math.max(180,Math.round(target.clientWidth||600)),H=Math.max(230,latest.length*72+40),L=16,R=70,top=14,bottom=30;
  const width=W-L-R,x=v=>L+v/scale.high*width,anchor=Date.parse(panel.data?.generated_at);
  const root=svg('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':`Último acumulado de chuva por estação, em ${unit}. Use setas para consultar os intervalos.`,tabindex:0});
  let cursor=0;
  function show(index){cursor=index;const {s,p}=latest[index];tooltip.textContent=pointDescription(s,p,unit,anchor);tooltip.hidden=false;}
  latest.forEach(({s,p},i)=>{
    const y=top+i*(H-bottom-top)/latest.length,barY=y+44;
    root.append(svg('text',{x:L,y:y+12,class:'snapshot-name'},s.name.split(' · ')[0]),svg('text',{x:L,y:y+31,'text-anchor':'start',class:'snapshot-time'},(s.name.includes(' · ')?s.name.split(' · ').slice(1).join(' · ')+' · ':'')+new Intl.DateTimeFormat('pt-BR',{timeZone,day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(p.time))),
      svg('rect',{x:L,y:barY,width,height:10,rx:5,class:'snapshot-track'}));
    const bar=svg('rect',{x:L,y:barY,width:Math.max(3,x(p.value)-L),height:10,rx:5,fill:s.color,class:'station-bar'});bar.append(svg('title',{},pointDescription(s,p,unit,anchor)));
    const hit=svg('rect',{x:0,y,width:W,height:(H-bottom-top)/latest.length,fill:'transparent',class:'snapshot-hit'});hit.append(svg('title',{},pointDescription(s,p,unit,anchor)));hit.addEventListener('pointermove',()=>show(i));hit.addEventListener('click',()=>show(i));
    root.append(bar,svg('text',{x:x(p.value)+9,y:barY+10,class:'snapshot-value'},num(p.value)+' '+unit),hit);
  });
  root.addEventListener('keydown',e=>{if(!['ArrowRight','ArrowLeft','ArrowUp','ArrowDown','Home','End'].includes(e.key))return;e.preventDefault();show(e.key==='Home'?0:e.key==='End'?latest.length-1:Math.max(0,Math.min(latest.length-1,cursor+(['ArrowRight','ArrowDown'].includes(e.key)?1:-1))));});
  root.addEventListener('pointerleave',()=>{tooltip.hidden=true;});target.append(root);
}
function drawWeatherChart(target,legend,tooltip,series,domain,label,unit,sharedScale=null) {
  target.replaceChildren();legend.replaceChildren();tooltip.hidden=true;
  const points=series.flatMap(s=>s.points.filter(p=>Number.isFinite(p.value)).map(p=>({...p,series:s})));
  if(!points.length){target.append(node('p','empty','Sem amostras válidas para esta variável e período. Ausência de dados não é valor zero.'));return;}
  const rain=series.some(s=>s.field==='precipitation_mm'||s.field?.startsWith('rain_')),anchor=Date.parse(panel.data?.generated_at);
  const scale=sharedScale||chartScale(points.map(p=>p.value),series.some(s=>s.field==='temperature_c')),{low,high}=scale;
  const [minT,maxT]=domain,W=Math.max(180,Math.round(target.clientWidth||600)),H=250,L=45,R=12,T=16,B=42,w=W-L-R,h=H-T-B;
  const x=t=>L+(t-minT)/(maxT-minT)*w,y=v=>T+h-(v-low)/(high-low)*h;
  const root=svg('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':`${label} (${unit}). Horários de Brasília. Use setas para explorar.`,tabindex:0});
  for(let value=low;value<=high+scale.step/100;value+=scale.step){root.append(svg('line',{x1:L,x2:W-R,y1:y(value),y2:y(value),class:'chart-grid'}),svg('text',{x:L-7,y:y(value)+4,'text-anchor':'end',class:'chart-label'},num(value,scale.step<1||scale.step%1?1:0)));}
  const ticks=W<360?2:3;
  for(let i=0;i<=ticks;i++){
    const t=minT+(maxT-minT)*i/ticks,instant=new Date(t),align=i===0?'start':i===ticks?'end':'middle';
    root.append(svg('text',{x:x(t),y:H-23,'text-anchor':align,class:'chart-label'},new Intl.DateTimeFormat('pt-BR',{timeZone,hour:'2-digit',minute:'2-digit'}).format(instant)),
      svg('text',{x:x(t),y:H-8,'text-anchor':align,class:'chart-label'},new Intl.DateTimeFormat('pt-BR',{timeZone,day:'2-digit',month:'2-digit'}).format(instant)));
  }
  for(const s of series) {
    if(rain){
      for(const p of s.points.filter(p=>Number.isFinite(p.value))){
        const start=Math.max(minT,Date.parse(p.start_at)),end=Math.min(maxT,Date.parse(p.time));if(end<=start)continue;
        const title=pointDescription(s,p,unit,anchor),height=Math.max(2,y(0)-y(p.value));
        const bar=svg('rect',{x:x(start),y:p.value===0?y(0)-2:y(p.value),width:Math.max(.5,x(end)-x(start)),height,
          fill:s.color,'fill-opacity':s.kind==='forecast'?.65:.12,stroke:s.color,'stroke-width':1,class:'rain-interval'});
        bar.append(svg('title',{},title));root.append(bar);
        // An observed accumulation occupies its real window, never the gap to the next collection.
        if(s.kind==='observation'){const cap=svg('line',{x1:x(start),x2:x(end),y1:y(p.value),y2:y(p.value),stroke:s.color,'stroke-width':3});cap.append(svg('title',{},title));root.append(cap);}
      }
    }else{
      let path='',last=null;const paths=[];
      for(const p of s.points){const t=Date.parse(p.time);if(!Number.isFinite(p.value)){if(path)paths.push(path);path='';last=null;continue;}if(last!==null&&t-last>s.gapMs){if(path)paths.push(path);path='';}path+=(path?' L':'M')+x(t).toFixed(2)+','+y(p.value).toFixed(2);last=t;}
      if(path)paths.push(path);
      for(const d of paths)root.append(svg('path',{d,fill:'none',stroke:s.color,'stroke-width':2.2,'stroke-dasharray':s.kind==='forecast'?'5 4':'none'}));
      for(const p of s.points.filter(p=>Number.isFinite(p.value))){const circle=svg('circle',{cx:x(Date.parse(p.time)),cy:y(p.value),r:s.points.length<=8?3.5:2.2,fill:s.color});circle.append(svg('title',{},pointDescription(s,p,unit,anchor)));root.append(circle);}
    }
    if(series.length>1&&s.points.some(p=>Number.isFinite(p.value))){const item=node('span','legend-item');const dot=node('i','legend-dot');dot.style.background=s.color;item.append(dot,node('span','',s.name));legend.append(item);}
  }
  if(typeof ChartInteraction!=='undefined'){
    const instants=[...new Set(points.map(p=>Date.parse(p.time)))].sort((a,b)=>a-b);
    ChartInteraction.attach(root,{width:W,left:L,right:R,top:T,bottom:T+h,domain:[minT,maxT],times:instants,tooltip,
      lookup(t,keyboard){
        let selected;
        if(rain)selected=points.filter(p=>Date.parse(p.start_at)<t&&t<=Date.parse(p.time));
        else {const nearest=instants.reduce((a,b)=>Math.abs(b-t)<Math.abs(a-t)?b:a,instants[0]);
          selected=points.filter(p=>Date.parse(p.time)===nearest&&Math.abs(nearest-t)<=p.series.gapMs/2);}
        return {text:selected.length?selected.map(p=>pointDescription(p.series,p,unit,anchor)).join('\n'):'Sem amostra neste horário. Ausência de dados não significa zero.',
          marks:selected.map(p=>({x:rain?x(Math.max(minT,Math.min(t,maxT))):x(Date.parse(p.time)),y:y(p.value),color:p.series.color}))};
      }});target.append(root);return;
  }
  const guide=svg('line',{x1:L,x2:L,y1:T,y2:T+h,stroke:'currentColor','stroke-dasharray':'3 4',visibility:'hidden'});root.append(guide);
  const instants=[...new Set(points.map(p=>Date.parse(p.time)))].sort((a,b)=>a-b);let cursor=0;
  function show(t){const nearest=instants.reduce((a,b)=>Math.abs(b-t)<Math.abs(a-t)?b:a,instants[0]);cursor=instants.indexOf(nearest);tooltip.textContent=points.filter(p=>Date.parse(p.time)===nearest).map(p=>pointDescription(p.series,p,unit,anchor)).join(' | ');tooltip.hidden=false;guide.setAttribute('x1',x(nearest));guide.setAttribute('x2',x(nearest));guide.setAttribute('visibility','visible');}
  function showPointer(e){const box=root.getBoundingClientRect(),position=(e.clientX-box.left)/box.width*W,t=minT+(position-L)/w*(maxT-minT);
    const inside=rain?points.filter(p=>Date.parse(p.start_at)<=t&&t<=Date.parse(p.time)):[];
    if(inside.length){tooltip.textContent=inside.map(p=>pointDescription(p.series,p,unit,anchor)).join(' | ');tooltip.hidden=false;guide.setAttribute('x1',x(t));guide.setAttribute('x2',x(t));guide.setAttribute('visibility','visible');}
    else if(rain){tooltip.textContent='Sem intervalo registrado neste horário; não significa chuva zero.';tooltip.hidden=false;guide.setAttribute('visibility','hidden');}
    else show(t);
  }
  root.addEventListener('pointermove',showPointer);root.addEventListener('click',showPointer);
  root.addEventListener('keydown',e=>{if(!['ArrowRight','ArrowLeft','Home','End'].includes(e.key))return;e.preventDefault();cursor=e.key==='Home'?0:e.key==='End'?instants.length-1:Math.max(0,Math.min(instants.length-1,cursor+(e.key==='ArrowRight'?1:-1)));show(instants[cursor]);});
  root.addEventListener('pointerleave',()=>{tooltip.hidden=true;guide.setAttribute('visibility','hidden');});
  target.append(root);
}
function renderStationDetails(series,anchor) {
  const target=el('station-readings');target.replaceChildren();
  const rain=panel.observedVariable==='precipitation_mm',unit=rain?'mm':panel.observedVariable==='temperature_c'?'°C':'km/h';
  const {rows,cohort}=comparableReadings(series,anchor,panel.rainWindow);
  const summary=el('station-comparison');
  if(!rows.length){summary.textContent='Sem leituras de estação para comparar neste período.';return;}
  summary.textContent=rain&&cohort.length>=2?`${cohort.length} de ${rows.length} estações com a mesma janela de ${panel.rainWindow} h: ${num(Math.min(...cohort.map(r=>r.point.value)))} a ${num(Math.max(...cohort.map(r=>r.point.value)))} mm. Diferenças não comprovam falha do sensor.`:rain?'As últimas leituras não formam um grupo recente com janelas idênticas. Compare horários antes de comparar valores.':'Leituras individuais; vento e rajada são variáveis distintas. Horários próximos não comprovam equivalência espacial.';
  const table=node('table');table.append(node('caption','','Última amostra disponível por estação e variável · horários de Brasília'));
  const head=node('thead'),tr=node('tr');for(const label of ['Estação e localização','Referência espacial','Intervalo / horário','Leitura'])tr.append(node('th','',label));head.append(tr);table.append(head);
  const body=node('tbody');
  for(const {series:s,point:p} of rows){
    const ref=s.reference||{},distance=Number.isFinite(ref.distance_km)?ref.distance_km:p.distance_km;
    const place=ref.municipality||(s.source==='cemaden-rain'?'Araquari · seleção por IBGE':'Localidade não informada');
    const position=Number.isFinite(ref.latitude)&&Number.isFinite(ref.longitude)?`${num(ref.latitude,4)}, ${num(ref.longitude,4)}`:'Coordenadas indisponíveis';
    const age=Math.max(0,(anchor-Date.parse(p.time))/3600000),row=node('tr');
    for(const text of [`${s.name} · código ${s.station} · ${place}`,`${Number.isFinite(distance)?num(distance)+' km do ponto municipal':'Distância não verificada'} · ${position}`,`${p.start_at?date(p.start_at)+' a ':''}${date(p.time)} · ${num(age)} h antes da atualização`,`${num(p.value)} ${unit}${rain?' / '+panel.rainWindow+' h':''}`])row.append(node('td','',text));
    body.append(row);
  }
  table.append(body);target.append(table);
}
function renderChart() {
  const data=panel.data,anchor=Number.isFinite(Date.parse(data?.generated_at))?Date.parse(data.generated_at):Date.now(),rain=panel.observedVariable==='precipitation_mm',forecastRain=panel.variable==='precipitation_mm';
  const palette=document.documentElement.dataset.theme==='dark'?['#79d39a','#82b7ef','#efba74','#c4a0ed','#f47b7f','#78cac9']:colors;
  const nearby=rain&&panel.scope==='nearby',history=nearby?{records:data?.regional_rain_context?.records||[]}:panel.history;
  const allObserved=getChartSeries(data,history,'observed',panel.observedVariable,panel.hours,anchor,`rain_${panel.rainWindow}h_mm`).map((s,i)=>({...s,color:palette[i%palette.length]}));
  const forecast=getChartSeries(data,panel.history,'forecast',panel.variable,panel.hours,anchor).map((s,i)=>({...s,color:palette[(i+1)%palette.length]}));
  const selector=el('station-select');selector.replaceChildren();const all=node('option','','Todas as estações');all.value='all';selector.append(all);
  const keys=new Set();for(const s of allObserved){const key=s.source+':'+s.station;if(keys.has(key))continue;keys.add(key);const option=node('option','',s.name.replace(/ · (vento|rajada)$/,''));option.value=key;selector.append(option);}
  if(panel.station!=='all'&&!keys.has(panel.station))panel.station='all';selector.value=panel.station;
  const observed=allObserved.filter(s=>panel.station==='all'||s.source+':'+s.station===panel.station);
  el('observed-panel').hidden=panel.mode==='forecast';el('forecast-panel').hidden=panel.mode==='observed';
  el('chart-panels').classList.toggle('single-panel',panel.mode!=='context');
  el('rain-window-control').hidden=!rain;el('rain-scope-control').hidden=!rain;el('observed-view-controls').hidden=!rain;el('rain-scope').value=panel.scope;el('rain-window').value=String(panel.rainWindow);
  const variable=rain?'Chuva':panel.observedVariable==='temperature_c'?'Temperatura':'Vento e rajadas',unit=rain?'mm':panel.observedVariable==='temperature_c'?'°C':'km/h',forecastUnit=forecastRain?'mm':panel.variable==='temperature_c'?'°C':'km/h';
  el('chart-heading').textContent='Observações e previsão';
  el('recent-summary').hidden=panel.observedVariable!=='temperature_c';
  el('observed-heading').textContent=rain?`Chuva medida · ${panel.rainWindow} h`:'Observado · '+variable.toLowerCase();
  el('forecast-heading').textContent=forecastRain?'Chuva prevista · por hora':panel.variable==='temperature_c'?'Temperatura prevista':'Vento e rajadas previstos';
  el('chart-period').textContent='Horários de Brasília';
  const base=Number.isFinite(Date.parse(data?.forecast?.start_at))?Date.parse(data.forecast.start_at):Math.floor(anchor/3600000)*3600000;
  const values=[...observed,...forecast].flatMap(s=>s.points.filter(p=>Number.isFinite(p.value)).map(p=>p.value));
  let shared=panel.mode==='context'&&panel.variable===panel.observedVariable&&(!rain||panel.rainWindow===1)&&values.length?chartScale(values,panel.variable==='temperature_c'):null;
  const times=new Set(observed.flatMap(s=>s.points.map(p=>p.time))),view=panel.observedView==='auto'?(times.size<4?'stations':'timeline'):panel.observedView;
  const snapshot=rain&&view==='stations';if(snapshot)shared=null;
  for(const b of document.querySelectorAll('[data-observed-view]')){const selected=b.dataset.observedView===view;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected));}
  if(snapshot)drawStationSnapshot(el('plot'),el('chart-legend'),el('chart-tooltip'),observed,unit,shared);
  else drawWeatherChart(el('plot'),el('chart-legend'),el('chart-tooltip'),observed,[anchor-panel.hours*3600000,anchor],el('observed-heading').textContent,unit,shared);
  el('plot').classList.toggle('snapshot-plot',snapshot);
  drawWeatherChart(el('forecast-plot'),el('forecast-legend'),el('forecast-tooltip'),forecast,[base,base+panel.hours*3600000],el('forecast-heading').textContent,forecastUnit,shared);
  el('observed-period').textContent=snapshot?'Última leitura disponível de cada estação':date(new Date(anchor-panel.hours*3600000).toISOString())+' — '+date(new Date(anchor).toISOString());
  const names=[...new Set(allObserved.map(s=>s.name))];
  el('observed-source').textContent=rain?'Cemaden':'Estações · METAR / Cemaden';
  el('station-coverage').textContent=rain?(nearby?`${names.length} estações do entorno com posição verificada, a até ${data?.regional_rain_context?.radius_km||40} km do ponto de Araquari. Apenas últimas leituras; não entram nos indicadores locais.`:`Araquari · ${names.length} estações de chuva com amostras neste período. Altere a área para consultar o entorno.`):'Medições pontuais de estações próximas, com fontes e distâncias nos detalhes.';
  el('forecast-period').textContent=date(new Date(base).toISOString())+' — '+date(new Date(base+panel.hours*3600000).toISOString());
  el('observed-caption').textContent=rain&&snapshot?`Acumulado de ${panel.rainWindow} h por estação. As leituras podem ter horários diferentes; toque nas barras para conferir.`:rain?(panel.rainWindow===1?'Cada faixa ocupa a hora realmente medida. Espaços sem faixas são períodos sem amostra; o histórico é coletado a cada 3 h.':'Faixas de acumulado móvel de 24 h podem se sobrepor. Não some as faixas nem compare sua altura com chuva prevista de 1 h.'):'Amostras de estação; linhas interrompidas em lacunas superiores a 4 h. Não são médias municipais.';
  el('forecast-caption').textContent=forecastRain?'Cada barra é uma hora de previsão. A primeira pode incluir a hora em curso. Espaços sem dados não significam chuva zero.':'Open-Meteo · modelo para o ponto municipal de Araquari. Linha tracejada; ausência de pontos mantém lacunas.';
  el('chart-caption').textContent=(shared?'Mesma escala vertical; períodos observados e previstos diferentes. ':rain&&forecastRain&&panel.rainWindow===24?'Acumulados diferentes: 24 h observado e 1 h previsto. Não compare diretamente as alturas. ':snapshot?'Gráficos com escalas próprias; confira os valores e períodos. ':'')+(!dashboardCurrent(data)?'Atualização vencida: referência anterior. ':'')+'Toque nos gráficos ou use as setas para consultar os intervalos.';
  renderStationDetails(allObserved,anchor);
  el('station-details').hidden=panel.mode==='forecast';
}
function renderRecent() {
  const anchor=Date.parse(panel.data?.generated_at),rows=(panel.history?.records||[]).filter(r=>{const t=Date.parse(r.observed_at);return t<=anchor+600000&&t>=anchor-86400000;});
  const groups=new Map();for(const r of rows){if(!Number.isFinite(r.temperature_c))continue;const key=stationName(stationReference(panel.data,r.source,r.station),'Estação próxima');if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r);}
  const best=[...groups.entries()].sort((a,b)=>b[1].length-a[1].length||a[0].localeCompare(b[0]))[0];
  el('recent-summary').textContent=best?`Últimas 24 h antes da atualização · ${best[0]}: ${num(Math.min(...best[1].map(r=>r.temperature_c)))} a ${num(Math.max(...best[1].map(r=>r.temperature_c)))} °C em ${best[1].length} amostra(s) nas últimas 24 h. Pontos de estação; não é média municipal.`:rows.length?`Últimas 24 h antes da atualização · ${rows.length} registro(s) de estação nas últimas 24 h. Explore as amostras observadas; o histórico cresce a cada coleta.`:'Histórico observado em formação. Nenhum período anterior foi reconstruído com dados do modelo.';
}
function duration(hours) {return Number.isFinite(hours)?num(hours,1)+' h':'não informada';}
function historyLabel(entry) {return riskNames[entry.state]||{routine:'Sem sinais nas fontes monitoradas',partial:'Dados incompletos',technical_attention:'Sinais de atenção',official_context:'Aviso meteorológico registrado',heightened:'Acompanhamento de alerta'}[entry.state]||entry.label||'Registro de acompanhamento';}
function renderMemory() {
  const target=el('history-strip');target.replaceChildren();const episodes=panel.data?.alert_history?.episodes||[];
  if(!episodes.length){target.append(node('p','small','O histórico de estados será formado a partir desta versão. Avisos já arquivados permanecem nas evidências.'));return;}
  for(const entry of episodes.slice(0,4)){const card=node('article','history-period');const heading=node('strong');heading.append(node('span','level-dot '+(['verde','azul','amarelo','laranja','vermelho','roxo'].includes(entry.state)?entry.state:'neutral')),node('span','',historyLabel(entry)));card.append(heading,node('span','',date(entry.first_seen_at)+' — '+date(entry.last_seen_at)),node('span','',entry.samples<2?'Primeiro registro · duração ainda não medida':`${entry.samples} registros · intervalo ${duration(entry.sampled_span_hours)}`));target.append(card);}
}
function showHistory() {
  openDialog('Histórico de acompanhamento e avisos',body=>{
    paragraph(body,'Os intervalos entre amostras não comprovam alerta contínuo. Ausência de um aviso na coleta seguinte não comprova cancelamento, fim de evento ou segurança.','notice');
    body.append(node('h3','','Estados registrados nas publicações'));
    for(const e of panel.data?.alert_history?.episodes||[])paragraph(body,`${historyLabel(e)}: ${date(e.first_seen_at)} a ${date(e.last_seen_at)} · ${e.samples} amostras · ${duration(e.sampled_span_hours)} entre registros${e.transition_kind==='collection_gap'?' · interrompido por lacuna de coleta':''}.`);
    body.append(node('h3','','Janelas de validade dos avisos · última revisão conhecida'));
    for(const n of panel.data?.alert_history?.notices||[]){const card=node('article','evidence-block');card.append(node('strong','',`${n.source} · ${n.title||n.type||'Aviso'}${n.severity?' · '+n.severity:''}`));paragraph(card,n.window_as_reported||`${date(n.start_at)} a ${date(n.end_at)}`);paragraph(card,`Validade informada: ${duration(n.validity_hours)}${n.duration_kind==='nominal_source_clock_no_timezone'?' nominais, pelos horários da fonte; fuso não conciliado':''}. Não é duração observada do fenômeno.`);paragraph(card,`Primeiro registro: ${date(n.first_seen_at)} · último: ${date(n.last_seen_at)}.`);if(n.url)card.append(officialLink(n.url,'Abrir publicação original ↗'));body.append(card);}
  });
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
function showAssessment() {
  openDialog('Entenda a situação em Araquari',body=>{
    const presentation=riskPresentation(panel.data),policy=effectiveAssessment(panel.data),objective=policy?.numeric_support;
    body.append(node('h3','',presentation.title));paragraph(body,presentation.reason);
    paragraph(body,'As cores seguem os seis níveis da PN 13/2026. O verde descritivo indica normalidade somente nos dados monitorados quando a cobertura necessária está completa e não há sinal de atenção. Não declara oficialmente o nível do campus. Dados ausentes ou vencidos mantêm a leitura sem cor de nível.');
    const signals=(objective?.signals||[]).filter(s=>s.band>0);
    if(signals.length){body.append(node('h3','','O que chamou a atenção'));for(const signal of signals.slice(0,8))paragraph(body,signalDescription(signal,panel.data));}
    body.append(node('h3','','Como ler os termos técnicos'));
    paragraph(body,'Uma leitura acima da referência significa que um valor atingiu uma faixa auxiliar de chuva ou vento. Chuva de 1 h, chuva de 24 h, vento e rajada são medidas diferentes: contar duas leituras não significa dois eventos ou dois alertas independentes.');
    paragraph(body,'Uma comparação temporal reúne observação e modelo para horários próximos e a mesma variável. Sem comparação compatível, não se conclui que a previsão está certa ou errada. Esses cruzamentos são explicados nos métodos, sem uma nota única de risco.');
    const gaps=(panel.data?.source_status||[]).filter(s=>!['available','cached','no_recent_notices'].includes(s.status));
    if(gaps.length){body.append(node('h3','','Fontes com limitações'));for(const gap of gaps)paragraph(body,`${gap.source}: sem cobertura atual completa; referência ${date(gap.reference_at)}.`);}
    paragraph(body,'A Epagri/Ciram é a referência prioritária. As faixas quantitativas auxiliares do INMET não substituem a norma institucional nem determinam suspensão ou retomada de atividades.');
  });
}
function showProtocol() {
  openDialog('Níveis e referências normativas',body=>{
    const data=panel.data,policy=effectiveAssessment(data),ref=data?.protocol;
    paragraph(body,'Referência: PN 13/2026 e PN 14/2026 — ASSINST/REI, de 04/11/2026. Não é um painel oficial nem uma comunicação de funcionamento.');
    if(policy){paragraph(body,dashboardCurrent(data)&&Date.now()<Date.parse(policy.valid_until)?policy.reason:'O enquadramento desta publicação perdeu validade.','notice');for(const p of policy.pending||[])paragraph(body,p);}
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
    if(panel.data?.assessment?.numeric_support&&Date.now()>=Date.parse(panel.data.assessment.numeric_support.valid_until))paragraph(body,'O apoio numérico de curta duração desta publicação venceu. Seus valores abaixo são registros da publicação, não sustentam o enquadramento atual.','notice');
    paragraph(body,'Medições, previsões e avisos são produtos distintos. A quantidade de fontes não é uma pontuação de confiança. Médias de municípios ou de estações distantes não determinam o nível.');
    body.append(node('h3','','Chuva observada'));paragraph(body,'Agrupam-se apenas estações retornadas para o IBGE de Araquari, com janelas de 24 h e fim a até 30 min da referência mais recente. A mediana só aparece com ao menos três estações. Mínimo, máximo, quantidade e horários ficam acessíveis; extremos não são apagados pela mediana.');
    paragraph(body,'Observações e previsão têm gráficos próprios. Chuva observada de 1 h e chuva prevista horária compartilham escala vertical quando exibidas juntas. Acumulados observados de 24 h são uma opção explícita e não são comparados diretamente às barras de 1 h. A comparação entre estações no gráfico exige janelas idênticas e recentes; o cartão de 24 h usa a tolerância de 30 min indicada acima.');
    body.append(node('h3','','Evolução e revisão'));paragraph(body,'A previsão horária mantém lacunas e distingue vento de rajada. Totais e picos de 24 h exigem série completa. Revisões comparam os mesmos horários futuros e a mesma referência de grade; não são erro do modelo. O histórico observado acumula amostras por estação por sete dias, sem preencher períodos anteriores à sua implantação.');
    const heat=panel.data?.forecast?.heat;if(heat?.status==='complete')paragraph(body,`Temperatura prevista: ${heat.hours_at_or_above} referências horárias ≥ ${heat.reference_c} °C; maior sequência ${heat.longest_sequence_hours}. É uma referência descritiva, não classificação normativa de calor ou sensação térmica.`);
    for(const pair of panel.data?.temperature_context?.pairs||[])paragraph(body,`Comparação exploratória: modelo ${num(pair.model_c)} °C (${date(pair.model_at)}), METAR ${pair.icao} ${num(pair.observed_c)} °C (${date(pair.observed_at)}), ${num(pair.distance_km)} km. Altitude e protocolos não conciliados; não se calcula erro.`);
    body.append(node('h3','','Referências quantitativas auxiliares · INMET'));
    paragraph(body,'Faixas técnicas de chuva horária: 20–<30 / 30–60 / >60 mm; vento: 40–<60 / 60–100 / >100 km/h. Valores compartilhados entre faixas usam a superior. Acumulados móveis de 24 h são apenas aproximação comparativa da referência diária (≥50–100 / >100 mm). Temperatura não recebe faixa de risco sem base climatológica adequada.');
    for(const signal of panel.data?.assessment?.numeric_support?.signals||[])paragraph(body,`${signal.source} · ${signal.station} · ${signal.variable}: ${num(signal.value)} ${signal.unit} · referência ${['abaixo das faixas consultadas','potencial','perigo','superior'][signal.band]||'indisponível'} · ${date(signal.start_at)} a ${date(signal.end_at)}${signal.period_proxy?' · janela móvel, referência diária apenas aproximada':''}.`);
    for(const pair of panel.data?.assessment?.numeric_support?.coincidences||[])paragraph(body,`Coincidência contextual ${pair.variable}, estação ${pair.station}: observação ${date(pair.observed_at)} e modelo ${date(pair.model_at)}. Janelas próximas não comprovam equivalência espacial ou precisão.`);
    paragraph(body,'Não há votação nem média entre fontes. Uma referência direta elevada pode sustentar sugestão de atenção; alerta laranja por apoio numérico exige sinais fortes da mesma variável em observação próxima e referência do modelo no mesmo horário. Faixas móveis de 24 h não produzem sozinhas nível sugerido. A evidência prioritária Epagri não é rebaixada por médias menores.');
    for(const url of panel.data?.assessment?.numeric_support?.reference_urls||[])body.append(officialLink(url,'Referência INMET ↗'));
    body.append(node('h3','','Níveis qualitativos'));paragraph(body,'A PN 13 não contém faixas numéricas para chuva, vento ou temperatura. O enquadramento combina avisos prioritários aplicáveis e apoio quantitativo identificado, preservando a separação entre referências técnicas e decisão institucional. Não há equivalência automática entre cores do INMET e os seis níveis. Decreto, danos locais e funcionamento não são inferidos.');
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
  finally{if(id===panel.loadId){el('refresh').disabled=false;renderSummary();renderRecent();renderMemory();renderChart();}}
}
function selectVariable(variable) {panel.variable=variable;if(el('forecast-variable'))el('forecast-variable').value=variable;for(const button of document.querySelectorAll('[data-variable]')){const selected=button.dataset.variable===variable;button.classList.toggle('active',selected);button.setAttribute('aria-pressed',String(selected));}renderChart();}
function selectMode(mode) {
  panel.mode=mode;
  for(const button of document.querySelectorAll('[data-mode]')){const selected=button.dataset.mode===mode;button.classList.toggle('active',selected);button.setAttribute('aria-pressed',String(selected));}
  const long=el('chart-range').querySelector('option[value="240"]');if(long)long.disabled=mode!=='forecast';
  if(mode!=='forecast'&&panel.hours>168){panel.hours=168;el('chart-range').value='168';}renderChart();
}
if(typeof module!=='undefined')module.exports={fresh,dashboardCurrent,protocolCurrent,effectiveAssessment,getChartSeries,comparableReadings,pointDescription,riskPresentation,stationName,chartScale};
if(typeof document!=='undefined'){
  function navigationState(){if(location.hash==='#memory')el('memory').open=true;for(const link of document.querySelectorAll('nav a[href^="#"]')){const active=link.getAttribute('href')===(location.hash||'#main');if(active)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');}}
  window.addEventListener('hashchange',navigationState);navigationState();
  el('refresh').addEventListener('click',loadDashboard);
  for(const b of document.querySelectorAll('[data-variable]'))b.addEventListener('click',()=>selectVariable(b.dataset.variable));
  for(const b of document.querySelectorAll('[data-focus]'))b.addEventListener('click',()=>{panel.hours=24;el('chart-range').value='24';selectMode('forecast');selectVariable(b.dataset.focus);el('chart-heading').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});});
  for(const b of document.querySelectorAll('[data-mode]'))b.addEventListener('click',()=>selectMode(b.dataset.mode));
  el('forecast-variable')?.addEventListener('change',event=>selectVariable(event.target.value));
  el('observed-variable')?.addEventListener('change',event=>{panel.observedVariable=event.target.value;panel.station='all';renderChart();});
  el('chart-range').addEventListener('change',event=>{panel.hours=Number(event.target.value);renderChart();});
  el('rain-scope').addEventListener('change',event=>{panel.scope=event.target.value==='nearby'?'nearby':'local';panel.station='all';renderChart();});
  for(const b of document.querySelectorAll('[data-observed-view]'))b.addEventListener('click',()=>{panel.observedView=b.dataset.observedView;renderChart();});
  el('levels-open').addEventListener('click',showProtocol);
  el('station-select').addEventListener('change',event=>{panel.station=event.target.value;renderChart();});
  el('rain-window').addEventListener('change',event=>{panel.rainWindow=Number(event.target.value)===24?24:1;renderChart();});
  el('history-open').addEventListener('click',showHistory);document.addEventListener('observatorythemechange',renderChart);
  el('evidence-open').addEventListener('click',showEvidence);el('level-explain').addEventListener('click',showAssessment);el('protocol-open').addEventListener('click',showProtocol);el('methods-open').addEventListener('click',showMethods);el('dialog-close').addEventListener('click',()=>el('detail-dialog').close());
  setInterval(()=>{renderSummary();if(!dashboardCurrent(panel.data)&&el('detail-dialog').open)el('detail-dialog').close();},60000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden){renderSummary();renderChart();if(!dashboardCurrent(panel.data)&&el('detail-dialog').open)el('detail-dialog').close();}});
  let chartWidth=0;
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(entries=>{const width=Math.round(entries[0].contentRect.width);if(width>0&&width!==chartWidth){chartWidth=width;requestAnimationFrame(renderChart);}}).observe(el('chart-panels'));
  loadDashboard();
}
