'use strict';
const panel = {data:null, history:null, variable:'precipitation_mm', hours:24, rainWindow:24, observedVariable:'precipitation_mm', station:'all', scope:'local', observedView:'auto', loadId:0,loading:false,fetchError:false};
const el = id => document.getElementById(id);
const colors = ['#2f8548','#377fb1','#b27a2b','#8a5a9f','#bf4e48','#458a88'];
const timeZone = 'America/Sao_Paulo';
function num(v, digits=1) { return Number.isFinite(v) ? v.toLocaleString('pt-BR',{maximumFractionDigits:digits,minimumFractionDigits:digits}) : '—'; }
function date(v) { return v && Number.isFinite(Date.parse(v)) ? new Intl.DateTimeFormat('pt-BR',{timeZone,day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(v)) : 'não informado'; }
function fresh(v, hours=3, now=Date.now()) { const t=typeof v==='string'?Date.parse(v):NaN;return Number.isFinite(t)&&now-t>=-600000&&now-t<=hours*3600000; }
function dashboardCurrent(data, now=Date.now()) { return Boolean(data&&fresh(data.generated_at,3,now)&&Number.isFinite(Date.parse(data.valid_until))&&now<Date.parse(data.valid_until)); }
function protocolCurrent(data, now=Date.now()) { return dashboardCurrent(data,now)&&Number.isFinite(Date.parse(data.assessment?.valid_until))&&now<Date.parse(data.assessment.valid_until); }
function forecastCurrent(data,now=Date.now()) {
  const f=data?.forecast;
  return Boolean(f?.status==='available'&&fresh(f.collected_at,8,now)&&fresh(f.reference_at,8,now));
}
function forecastFieldCurrent(data,field,now=Date.now()) {
  const source=data?.forecast?.sources_by_variable?.[field];
  return source?source.status==='available'&&now<Date.parse(source.valid_until):forecastCurrent(data,now);
}
function currentGauges(data,now=Date.now()) {
  const gauge=data?.gauge_distribution;
  if(gauge?.status!=='available')return null;
  if(!Array.isArray(gauge.stations))return dashboardCurrent(data,now)?gauge:null;
  const stations=gauge.stations.filter(s=>Number.isFinite(s.rain_24h_mm)&&fresh(s.observed_at,6,now));
  if(!stations.length)return null;
  const values=stations.map(s=>s.rain_24h_mm).sort((a,b)=>a-b),mid=Math.floor(values.length/2);
  return {...gauge,stations,station_count:stations.length,maximum_mm:values.at(-1),
    median_mm:values.length>=3?(values.length%2?values[mid]:(values[mid-1]+values[mid])/2):null,
    latest_at:stations.map(s=>s.observed_at).sort().at(-1)};
}
function currentPrimaryAssessment(data,now) {
  const base=data?.assessment?.base_assessment;
  if(!base||now<Date.parse(base.valid_until))return base;
  const source=data.source_status?.find(s=>s.source==='Epagri/Ciram · avisos');
  const sourceReady=['available','cached','no_recent_notices'].includes(source?.status)&&fresh(source.reference_at,6,now);
  const evidence=(base.evidence||[]).map(e=>({...e,status:e.status==='eligible'&&(!sourceReady||!(now<Date.parse(e.valid_until)))?'expired':e.status}));
  const order={azul:1,amarelo:2,laranja:3,vermelho:4};
  const supported=evidence.filter(e=>e.status==='eligible'&&order[e.supports_level]).sort((a,b)=>order[b.supports_level]-order[a.supports_level]);
  return {...base,valid_until:data.valid_until,evidence,suggested_level:supported[0]?.supports_level||null,
    status:supported.length?'suggested_for_review':evidence.some(e=>e.status==='eligible')?'official_advisory_under_review':'insufficient_evidence',
    primary_coverage_expired:!sourceReady,
    reason:sourceReady?'Avisos reavaliados pelos prazos individuais; publicações encerradas não sustentam o nível atual.':'A consulta Epagri/Ciram perdeu validade; as outras referências são avaliadas separadamente.'};
}
function signalCurrent(signal,data,now=Date.now()) {
  if(!dashboardCurrent(data,now))return false;
  if(signal.kind==='observation') {
    const hours=signal.variable==='rain_1h_mm'?1:signal.variable==='rain_24h_mm'?6:2;
    return fresh(signal.end_at,hours,now)&&now<Date.parse(signal.end_at)+hours*3600000;
  }
  // A forecast maximum remains a reference for its published window, including
  // the elapsed part of that window, until the publication itself expires.
  return signal.kind==='forecast'&&Number.isFinite(Date.parse(signal.start_at))&&Number.isFinite(Date.parse(signal.end_at));
}
function effectiveAssessment(data,now=Date.now()) {
  const policy=data?.assessment;
  const objective=policy?.numeric_support;
  const expired=objective?.signals?.filter(s=>!signalCurrent(s,data,now))||[];
  if(protocolCurrent(data,now)&&!expired.length)return policy;
  const base=currentPrimaryAssessment(data,now);
  if(dashboardCurrent(data,now)&&base&&now<Date.parse(base.valid_until)) {
    const signals=(objective?.signals||[]).filter(s=>signalCurrent(s,data,now));
    const coincidences=(objective?.coincidences||[]).filter(c=>signals.some(s=>s.kind==='observation'&&!s.period_proxy&&s.band>0&&s.variable===c.variable&&s.station===c.station&&s.end_at===c.observed_at));
    const direct=signals.filter(s=>s.band>0&&!s.period_proxy);
    const proposal=coincidences.some(c=>c.observed_band>=2&&c.model_band>=2&&c.spatial_match_verified)?'laranja':direct.some(s=>s.band>=2)||coincidences.length?'amarelo':null;
    const levels={verde:0,azul:1,amarelo:2,laranja:3,vermelho:4,roxo:5};
    const numericWins=proposal&&levels[proposal]>(levels[base.suggested_level]??-1);
    const suggested=numericWins?proposal:base.suggested_level;
    const maximum=signals.length?Math.max(...signals.map(s=>s.band)):null;
    const official=base.evidence?.some(e=>e.status==='eligible');
    const pending=base.evidence?.some(e=>e.status==='needs_territorial_or_temporal_check'&&(e.scope!=='not_verified'||!e.regions_text));
    // Expired coverage may retain attention, but cannot establish normality.
    const complete=Boolean(objective?.core_complete&&!expired.length&&!base.primary_coverage_expired&&signals.length);
    const state=suggested?'heightened':maximum>0?'technical_attention':official?'official_context':pending?'partial':complete?'routine':'partial';
    const label=state==='partial'?'Monitoramento parcial':state==='routine'?'Monitoramento de rotina':state==='technical_attention'?'Referências de atenção':'Acompanhamento reforçado';
    return {...base,suggested_level:suggested||null,monitoring_state:state,monitoring_label:label,
      title:suggested?riskNames[suggested]:label,
      basis_kind:numericWins?'complementary_numeric_evidence':suggested?'primary_epagri_advisory':'monitoring_state',
      reason:state==='partial'?'Parte das medições venceu e as referências restantes não permitem uma leitura completa. Consulte as fontes e os horários.':'Leitura recalculada com as referências ainda válidas; medições vencidas foram retiradas.',
      numeric_support:{...objective,valid_until:base.valid_until,signals,coincidences,proposed_level:proposal,maximum_band:maximum,core_complete:complete,expired_signals:expired}};
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
  if(!data)return {color:'neutral',active:null,title:panel.fetchError?'Dados indisponíveis':'Consultando dados',kind:'Carregamento da publicação',reason:'Ainda não foi possível carregar uma publicação verificável. O painel tenta novamente automaticamente; consulte as fontes oficiais enquanto aguarda.'};
  const weather=data.risk_classification&&typeof WeatherSynthesis!=='undefined'?WeatherSynthesis.riskLevel(data.risk_classification,now):null;
  if(weather)return weather;
  if(!dashboardCurrent(data,now))return {color:'neutral',active:null,title:'Atualização necessária',kind:'Dados desatualizados',reason:'A última atualização perdeu validade. Consulte as fontes oficiais enquanto aguarda novos dados.'};
  const policy=effectiveAssessment(data,now),objective=policy?.numeric_support;
  if(!policy||!(now<Date.parse(policy.valid_until)))return {color:'neutral',active:null,title:'Dados insuficientes para classificar',kind:'Leitura parcial',reason:'Não há referências válidas suficientes para distinguir normalidade de uma situação de atenção.'};
  const signals=(objective?.signals||[]).filter(s=>s.band>0).sort((a,b)=>Number(a.period_proxy)-Number(b.period_proxy)||b.band-a.band);
  const highest=signals[0],families=[...new Set(signals.map(s=>s.variable.startsWith('rain_')?'chuva':'vento'))],description=highest?signalDescription(highest,data):'';
  if(policy.suggested_level)return {color:policy.suggested_level,active:policy.suggested_level,title:riskNames[policy.suggested_level]||policy.title,kind:'Nível sugerido · '+policy.suggested_level,
    reason:policy.basis_kind==='complementary_numeric_evidence'?description||policy.reason:'Um aviso Epagri/Ciram para a região contém informações compatíveis com este nível. Confira o período e a abrangência nos detalhes.'};
  if(policy.monitoring_state==='routine'&&objective?.core_complete&&objective.maximum_band===0&&objective.signals?.length)return {color:'verde',active:'verde',title:'Normalidade nos dados acompanhados',kind:'Referência verde · leitura consultiva',reason:'As fontes necessárias foram consultadas e os dados válidos de chuva e vento estão abaixo das faixas de atenção utilizadas. Nenhum aviso aplicável foi identificado. É uma leitura do painel, não uma declaração institucional.'};
  if(highest)return {color:'amarelo',active:null,title:'Atenção a '+(families.length>1?'chuva e vento':highest.variable.startsWith('rain_')?'chuva':highest.variable==='gust_kmh'?'rajadas de vento':'vento'),kind:'Referência amarela · atenção',reason:signals.slice(0,2).map(signal=>signalDescription(signal,data)).join(' ')};
  if(policy.monitoring_state==='official_context')return {color:'amarelo',active:null,title:'Há aviso meteorológico para conferir',kind:'Referência amarela · conferir aviso',reason:'Uma publicação oficial pode ser relevante para Araquari. A abrangência ou o conteúdo ainda não permite sugerir um nível específico; abra as evidências.'};
  return {color:'neutral',active:null,title:'Dados insuficientes para classificar',kind:'Leitura parcial',reason:objective?.expired_signals?.length?policy.reason:'Há informações disponíveis, mas faltam referências válidas para uma leitura completa. Falta de dados não significa normalidade.'};
}
function compactTime(value) {return value&&Number.isFinite(Date.parse(value))?new Intl.DateTimeFormat('pt-BR',{timeZone,hour:'2-digit',minute:'2-digit'}).format(new Date(value)):'';}
function modelRange(data,field,unit) {
  const c=data?.forecast_comparison;
  if(!c||Date.now()>=Date.parse(c.valid_until))return '';
  const metric=c.windows?.find(w=>w.hours===24)?.metrics?.find(m=>m.variable===field);
  return metric?.status==='comparable'?`Modelos: ${num(metric.minimum)}–${num(metric.maximum)} ${unit}`:'';
}
function dailyForecast(data) {
  const parts=Object.fromEntries(new Intl.DateTimeFormat('en',{timeZone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()).map(p=>[p.type,p.value]));
  const today=`${parts.year}-${parts.month}-${parts.day}`;
  return data?.synthesis?.forecast_context?.days?.find(d=>d.source==='INMET'&&d.day===today&&Date.now()<Date.parse(d.valid_until));
}
function renderSummary() {
  const data=panel.data,current=dashboardCurrent(data),presentation=riskPresentation(data);
  el('publication-time').textContent=data?'Atualizado em '+date(data.generated_at):'Atualização indisponível';
  el('publication-status').hidden=current&&!panel.fetchError&&!panel.incompleteHistory;
  el('publication-status').textContent=panel.fetchError?'Falha ao atualizar. Nova tentativa automática.':panel.incompleteHistory?'Histórico temporariamente indisponível.':data?'Coleta atrasada.':'Não foi possível carregar os dados.';
  el('level-dot').className='level-dot '+presentation.color;el('level-card').dataset.risk=presentation.color;
  el('level-title').textContent=riskNames[presentation.color]||presentation.title;
  el('level-kind').textContent=presentation.color==='neutral'?'Dados parciais':data?.risk_classification?.coverage?.forecast_resolution==='mixed_or_qualitative'?'Consultivo · previsão por turnos':'Consultivo';
  el('level-reason').textContent=data?.risk_classification?presentation.reason:!data?'Consultando os dados.':presentation.color==='verde'?'Chuva e vento abaixo das faixas de atenção.':presentation.reason.split('. ')[0]+'.';
  for(const item of document.querySelectorAll('[data-risk-level]')){
    const active=item.dataset.riskLevel===(presentation.active||presentation.color);item.classList.toggle('is-active',active);
    if(active)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');
  }
  renderHomeNotices();
  if(el('detail-dialog').open)renderRiskExplanation();
  const localStats=typeof WeatherSynthesis!=='undefined'?WeatherSynthesis.currentStats(data?.synthesis,'rain_24h_mm'):null;
  const gauges=currentGauges(data),observed=localStats?.median??gauges?.median_mm??gauges?.maximum_mm;
  const count=localStats?.count??gauges?.station_count,maximum=localStats?.max??gauges?.maximum_mm;
  updateMetric('observed',Number.isFinite(observed)?num(observed)+' mm':'—',count?`${count} ${count===1?'estação':'estações'} · maior ${num(maximum)} mm`:'Sem leitura recente');
  const f=data?.forecast,rain=f?.rain,gust=f?.wind?.gust_kmh,heat=f?.heat;
  const rainValid=forecastFieldCurrent(data,'precipitation_mm'),gustValid=forecastFieldCurrent(data,'gust_kmh'),heatValid=forecastFieldCurrent(data,'temperature_c');
  updateMetric('forecast',rainValid&&rain?.status==='complete'?num(rain.total_mm)+' mm':'—',rainValid&&rain?.status==='complete'?modelRange(data,'precipitation_mm','mm')||'Próximas 24 h':'Sem previsão completa');
  updateMetric('gust',gustValid&&Number.isFinite(gust?.maximum)?num(gust.maximum)+' km/h':'—',gustValid?modelRange(data,'gust_kmh','km/h')||compactTime(gust?.at):'Sem previsão completa');
  updateMetric('temperature',heatValid&&Number.isFinite(heat?.maximum_c)?num(heat.maximum_c)+' °C':'—',heatValid?modelRange(data,'temperature_c','°C')||compactTime(heat?.maximum_at):'Sem previsão completa');
  for(const [name,field,unit]of [['wind-observed','gust_kmh','km/h'],['temperature-observed','temperature_c','°C']]){
    if(!el(name+'-value'))continue;
    const stats=typeof WeatherSynthesis!=='undefined'?WeatherSynthesis.currentStats(data?.synthesis,field):null;
    updateMetric(name,stats?num(field==='gust_kmh'?stats.max:stats.median)+' '+unit:'—',stats?`${stats.count} ${stats.count===1?'estação':'estações'} · ${compactTime(stats.members[0].end_at)}`:'Sem leitura recente');
  }
  const daily=dailyForecast(data),label=el('temperature-label');if(label)label.textContent='MÁXIMA · PRÓX. 24 H';
  const tempButton=document.querySelector('[data-focus="temperature_c"]');if(tempButton)tempButton.dataset.daily='false';
  if(!heatValid&&daily&&Number.isFinite(daily.maximum_c)){
    updateMetric('temperature',num(daily.maximum_c)+' °C','INMET · previsão diária');if(label)label.textContent='MÁXIMA · HOJE';if(tempButton)tempButton.dataset.daily='true';
  }
  const brief=el('forecast-brief');if(brief){
    const hour=Number(new Intl.DateTimeFormat('en',{timeZone,hour:'numeric',hourCycle:'h23'}).format(new Date()));
    const order=hour<12?['manha','tarde','noite','dia']:hour<18?['tarde','noite','dia']:['noite','dia'];
    const period=daily?.periods?.filter(p=>order.includes(p.period)).sort((a,b)=>order.indexOf(a.period)-order.indexOf(b.period))[0];
    brief.textContent=period?.summary?`Hoje${{manha:' de manhã',tarde:' à tarde',noite:' à noite',dia:''}[period.period]}: ${period.summary.replace(/[.\s]+$/,'').toLocaleLowerCase('pt-BR')}.`:'';
    brief.hidden=!brief.textContent;
  }
}
function stationReference(data,source,station) {
  if(source==='ifc')return {source,station,name:'IFC Araquari',municipality:'Araquari'};
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
  const rows=Array.isArray(history?.records)?history.records.slice():[],grouped=new Map();
  for(const r of data?.synthesis?.observation_history||[]){if(r.source==='ifc'&&fields.includes(r.variable))rows.push({source:'ifc',station:r.station,observed_at:r.end_at,[r.variable]:r.value});}
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
  const interval=p.start_at?`${date(p.start_at)} a ${date(p.time)} · acumulado de ${series.field==='rain_24h_mm'?24:1} h`:`${series.kind==='forecast'?'Previsão para':'Medição em'} ${date(p.time)}`;
  const current=series.kind==='forecast'&&p.start_at&&Date.parse(p.start_at)<anchor&&Date.parse(p.time)>anchor?' · inclui a hora em curso':'';
  return `${series.kind==='forecast'?'Open-Meteo · ':''}${series.name}: ${num(p.value)} ${unit} · ${interval}${current}`;
}
// Overlapping accumulations remain on the plot, but only the closest ending
// reading of each series belongs in the cursor's description.
function chartReadingsAt(points,t,rain) {
  const valid=points.filter(p=>Number.isFinite(p.value)&&Number.isFinite(Date.parse(p.time)));
  if(!valid.length||!Number.isFinite(t))return [];
  const nearest=rain?null:valid.reduce((a,p)=>Math.abs(Date.parse(p.time)-t)<Math.abs(a-t)?Date.parse(p.time):a,Date.parse(valid[0].time));
  const selected=new Map();
  for(const p of valid) {
    const end=Date.parse(p.time);
    if(rain?!(Date.parse(p.start_at)<t&&t<=end):!(end===nearest&&Math.abs(end-t)<=p.series.gapMs/2))continue;
    const previous=selected.get(p.series);
    if(!previous||Math.abs(end-t)<=Math.abs(Date.parse(previous.time)-t))selected.set(p.series,p);
  }
  return [...selected.values()];
}
function chartReadingText(selected,unit,anchor,limit=4) {
  if(!selected.length)return 'Sem amostra neste horário. Ausência de dados não significa zero.';
  const visible=selected.slice(0,limit),observed=visible.every(p=>p.series.kind==='observation');
  const compactDate=v=>new Intl.DateTimeFormat('pt-BR',{timeZone,day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(v));
  let lines;
  if(observed){
    const field=visible[0].series.field;
    const heading=field?.startsWith('rain_')?`Chuva medida · acumulado de ${field==='rain_24h_mm'?24:1} h`:'Medições · horário de cada leitura';
    const sameTime=new Set(visible.map(p=>Date.parse(p.time))).size===1;
    lines=[heading,...(sameTime?['Leituras: '+compactDate(visible[0].time)]:[]),...visible.map(p=>`${p.series.name}: ${num(p.value)} ${unit}${sameTime?'':' · '+compactDate(p.time)}`)];
  }else lines=visible.map(p=>pointDescription(p.series,p,unit,anchor));
  if(selected.length>visible.length)lines.push(`+${selected.length-visible.length} séries · filtre por estação`);
  return lines.join('\n');
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
  root.append(svg('text',{x:L,y:11,class:'chart-unit'},unit));
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
        const selected=chartReadingsAt(points,t,rain);
        return {text:chartReadingText(selected,unit,anchor),
          marks:selected.slice(0,4).map(p=>({x:rain?x(Math.max(minT,Math.min(t,maxT))):x(Date.parse(p.time)),y:y(p.value),color:p.series.color}))};
      }});target.append(root);return;
  }
  const guide=svg('line',{x1:L,x2:L,y1:T,y2:T+h,stroke:'currentColor','stroke-dasharray':'3 4',visibility:'hidden'});root.append(guide);
  const instants=[...new Set(points.map(p=>Date.parse(p.time)))].sort((a,b)=>a-b);let cursor=0;
  function show(t){
    const nearest=instants.reduce((a,b)=>Math.abs(b-t)<Math.abs(a-t)?b:a,instants[0]);cursor=instants.indexOf(nearest);
    const selected=chartReadingsAt(points,t,rain);
    tooltip.textContent=selected.length?chartReadingText(selected,unit,anchor):rain?'Sem intervalo registrado neste horário; não significa chuva zero.':chartReadingText([],unit,anchor);
    tooltip.hidden=false;guide.setAttribute('x1',x(t));guide.setAttribute('x2',x(t));guide.setAttribute('visibility',selected.length?'visible':'hidden');
  }
  function showPointer(e){const box=root.getBoundingClientRect(),position=(e.clientX-box.left)/box.width*W,t=minT+(position-L)/w*(maxT-minT);show(t);}
  root.addEventListener('pointermove',showPointer);root.addEventListener('click',showPointer);
  root.addEventListener('keydown',e=>{if(!['ArrowRight','ArrowLeft','Home','End'].includes(e.key))return;e.preventDefault();cursor=e.key==='Home'?0:e.key==='End'?instants.length-1:Math.max(0,Math.min(instants.length-1,cursor+(e.key==='ArrowRight'?1:-1)));show(instants[cursor]);});
  root.addEventListener('pointerleave',()=>{tooltip.hidden=true;guide.setAttribute('visibility','hidden');});
  target.append(root);
}
function renderChart() {
  panel.chartExpired=!dashboardCurrent(panel.data);
  const data=panel.data,anchor=Number.isFinite(Date.parse(data?.generated_at))?Date.parse(data.generated_at):Date.now(),rain=panel.observedVariable==='precipitation_mm',forecastRain=panel.variable==='precipitation_mm';
  const palette=document.documentElement.dataset.theme==='dark'?['#79d39a','#82b7ef','#efba74','#c4a0ed','#f47b7f','#78cac9']:colors;
  const nearby=rain&&panel.scope==='nearby',history=nearby?{records:data?.regional_rain_context?.records||[]}:panel.history;
  const allObserved=getChartSeries(data,history,'observed',panel.observedVariable,panel.hours,anchor,`rain_${panel.rainWindow}h_mm`).map((s,i)=>({...s,color:palette[i%palette.length]}));
  const forecast=getChartSeries(data,panel.history,'forecast',panel.variable,panel.hours,anchor).map((s,i)=>({...s,color:palette[(i+1)%palette.length]}));
  const selector=el('station-select');selector.replaceChildren();const all=node('option','','Todas as estações');all.value='all';selector.append(all);
  const keys=new Set();for(const s of allObserved){const key=s.source+':'+s.station;if(keys.has(key))continue;keys.add(key);const option=node('option','',s.name.replace(/ · (vento|rajada)$/,''));option.value=key;selector.append(option);}
  if(panel.station!=='all'&&!keys.has(panel.station))panel.station='all';selector.value=panel.station;
  const observed=allObserved.filter(s=>panel.station==='all'||s.source+':'+s.station===panel.station);
  el('observed-panel').hidden=false;el('forecast-panel').hidden=false;
  el('rain-window-control').hidden=!rain;el('rain-scope-control').hidden=!rain;el('observed-view-controls').hidden=!rain;el('rain-scope').value=panel.scope;el('rain-window').value=String(panel.rainWindow);
  const variable=rain?'Chuva':panel.observedVariable==='temperature_c'?'Temperatura':'Vento e rajadas',unit=rain?'mm':panel.observedVariable==='temperature_c'?'°C':'km/h',forecastUnit=forecastRain?'mm':panel.variable==='temperature_c'?'°C':'km/h';
  el('chart-heading').textContent='Observações e previsão';
  el('recent-summary').hidden=panel.observedVariable!=='temperature_c';
  el('observed-heading').textContent=rain?`Chuva medida · ${panel.rainWindow} h`:'Observado · '+variable.toLowerCase();
  const forecastSource=data?.forecast?.sources_by_variable?.[panel.variable];
  if(el('forecast-source'))el('forecast-source').textContent=(forecastSource?.id==='best_match'?'Previsão horária':forecastSource?.name||'Previsão horária')+(forecastSource?.retained_previous?' · consulta anterior':'');
  el('forecast-heading').textContent=forecastRain?'Chuva prevista · por hora':panel.variable==='temperature_c'?'Temperatura prevista':'Vento e rajadas previstos';
  el('chart-period').textContent='Horários de Brasília';
  const base=Number.isFinite(Date.parse(data?.forecast?.start_at))?Date.parse(data.forecast.start_at):Math.floor(anchor/3600000)*3600000;
  const values=[...observed,...forecast].flatMap(s=>s.points.filter(p=>Number.isFinite(p.value)).map(p=>p.value));
  let shared=panel.variable===panel.observedVariable&&(!rain||panel.rainWindow===1)&&values.length?chartScale(values,panel.variable==='temperature_c'):null;
  const times=new Set(observed.flatMap(s=>s.points.map(p=>p.time))),view=panel.observedView==='auto'?(times.size<4?'stations':'timeline'):panel.observedView;
  const snapshot=rain&&view==='stations';if(snapshot)shared=null;
  for(const b of document.querySelectorAll('[data-observed-view]')){const selected=b.dataset.observedView===view;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected));}
  if(snapshot)drawStationSnapshot(el('plot'),el('chart-legend'),el('chart-tooltip'),observed,unit,shared);
  else drawWeatherChart(el('plot'),el('chart-legend'),el('chart-tooltip'),observed,[anchor-panel.hours*3600000,anchor],el('observed-heading').textContent,unit,shared);
  el('plot').classList.toggle('snapshot-plot',snapshot);
  drawWeatherChart(el('forecast-plot'),el('forecast-legend'),el('forecast-tooltip'),forecast,[base,base+panel.hours*3600000],el('forecast-heading').textContent,forecastUnit,shared);
  el('observed-period').textContent=snapshot?'Última leitura disponível de cada estação':date(new Date(anchor-panel.hours*3600000).toISOString())+' — '+date(new Date(anchor).toISOString());
  const stations=new Set(observed.map(s=>s.source+':'+s.station));
  const sources=[...new Set(observed.map(s=>s.source==='ifc'?'IFC':String(s.source).includes('metar')?'METAR':String(s.source).startsWith('cemaden')?'Cemaden':'Estações'))];
  el('observed-source').textContent=rain?(nearby?'Cemaden · entorno':'Estações de Araquari'):sources.join(' / ')||'Sem leituras';
  el('station-coverage').textContent=`${stations.size} ${stations.size===1?'estação':'estações'} · ${rain?(nearby?'entorno':'Araquari'):'leituras disponíveis'}`;
  el('forecast-period').textContent=date(new Date(base).toISOString())+' — '+date(new Date(base+panel.hours*3600000).toISOString());
  el('observed-caption').textContent=rain?`Acumulado de ${panel.rainWindow} h por estação.`:'Medições por estação.';
  if(panel.hours>168)el('observed-caption').textContent+=' Histórico: até 7 dias.';
  el('forecast-caption').textContent=forecastRain?'Chuva por hora.':'Previsão horária.';
  el('chart-caption').textContent=rain&&forecastRain&&panel.rainWindow===24?'Observado: acumulado de 24 h. Previsto: chuva por hora.':'Toque ou passe o cursor para ver valores.';
  if(panel.chartExpired)el('chart-caption').textContent='Atualização vencida. '+el('chart-caption').textContent;


}
function renderRecent() {
  if(!el('recent-summary'))return;
  const anchor=Date.parse(panel.data?.generated_at),rows=(panel.history?.records||[]).filter(r=>{const t=Date.parse(r.observed_at);return t<=anchor+600000&&t>=anchor-86400000;});
  const groups=new Map();for(const r of rows){if(!Number.isFinite(r.temperature_c))continue;const key=stationName(stationReference(panel.data,r.source,r.station),'Estação próxima');if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r);}
  const best=[...groups.entries()].sort((a,b)=>b[1].length-a[1].length||a[0].localeCompare(b[0]))[0];
  el('recent-summary').textContent=best?`Últimas 24 h: ${num(Math.min(...best[1].map(r=>r.temperature_c)))}–${num(Math.max(...best[1].map(r=>r.temperature_c)))} °C · ${best[0]}`:'';
}
function duration(hours) {return Number.isFinite(hours)?num(hours,1)+' h':'não informada';}
function historyLabel(entry) {return riskNames[entry.state]||{routine:'Sem sinais nas fontes monitoradas',partial:'Dados incompletos',technical_attention:'Sinais de atenção',official_context:'Aviso meteorológico registrado',heightened:'Acompanhamento de alerta'}[entry.state]||entry.label||'Registro de acompanhamento';}
function paragraph(host,text,cls='') {host.append(node('p',cls,text));}
function primaryNotice(data,now=Date.now()) {
  if(!dashboardCurrent(data,now))return null;
  return (effectiveAssessment(data,now)?.evidence||[]).find(n=>n.status==='eligible'&&now<Date.parse(n.valid_until))||null;
}
function inmetNotices(data,now=Date.now()) {
  const feed=data?.inmet_context||data?.complementary_notices;
  if((feed?.status!=='available'&&!feed?.retained_previous)||!fresh(feed.retrieved_at,6,now))return [];
  return (feed.notices||[]).filter(n=>n.lifecycle!=='expired'&&(!n.end_at||now<Date.parse(n.end_at))&&(!feed.retained_previous||(Number.isFinite(Date.parse(n.start_at))&&Number.isFinite(Date.parse(n.end_at))&&Date.parse(n.start_at)<Date.parse(n.end_at))));
}
function inmetContextStatus(data,now=Date.now()) {
  const feed=data?.inmet_context||data?.complementary_notices;
  if(feed?.retained_previous&&inmetNotices(data,now).length)return {title:'Avisos INMET · consulta anterior',description:'A consulta atual falhou. Os avisos abaixo foram preservados com seus horários originais e prazo informado ainda não encerrado; revisão ou cancelamento não confirmados.'};
  if(!data)return {title:'Consultando avisos INMET',description:'Aguardando a consulta de Araquari e entorno.'};
  if(feed?.retrieved_at&&!fresh(feed.retrieved_at,6,now))return {title:'Consulta INMET desatualizada',description:'Não foi possível confirmar a situação atual dos avisos. Consulte o portal oficial.'};
  if(feed?.status!=='available'||!fresh(feed.retrieved_at,6,now))return {title:'Consulta INMET indisponível',description:'Não foi possível verificar os avisos de Araquari e entorno nesta publicação. Indisponibilidade não significa ausência de avisos.'};
  const count=inmetNotices(data,now).length;
  return count?{title:'Avisos para Araquari e entorno',description:`${count} aviso(s) retornado(s). Confira abaixo os municípios abrangidos, o período e as limitações de validade.`}:
    {title:'Nenhum aviso aplicável retornado',description:'A consulta INMET não retornou avisos não encerrados para Araquari e o entorno monitorado. Isso não comprova ausência de risco.'};
}
// Source notices are presented for human review; this selection does not classify risk.
function reportedWindowExpired(text,now) {
  const dates=String(text||'').match(/\d{2}\/\d{2}\/\d{4}/g);
  if(!dates?.length)return false;
  const [d,m,y]=dates.at(-1).split('/');
  const parts=Object.fromEntries(new Intl.DateTimeFormat('en',{timeZone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(now)).map(p=>[p.type,p.value]));
  return `${y}-${m}-${d}`<`${parts.year}-${parts.month}-${parts.day}`;
}
function noticePeriod(notice,now=Date.now()) {
  const start=Date.parse(notice.start_at),end=Date.parse(notice.end_at);
  if(Number.isFinite(start)&&Number.isFinite(end)&&start<end)return `${date(notice.start_at)} a ${date(notice.end_at)} · ${now<start?'início futuro':'em curso'}`;
  return `${notice.window_as_reported||'Período não confirmado'} · validade a confirmar`;
}
function homeNotices(data,now=Date.now()) {
  const rows=[],seen=new Set(),list=value=>Array.isArray(value)?value:[];
  function add(row){const key=row.source+':'+(row.id||row.url||row.title);if(!seen.has(key)){seen.add(key);rows.push(row);}}
  const source=data?.source_status?.find(s=>s.source==='Epagri/Ciram · avisos');
  for(const n of list(data?.assessment?.base_assessment?.evidence||data?.assessment?.evidence)){
    if(!n||typeof n!=='object')continue;
    const regions=String(n.regions_text||'');
    const scoped=['municipality_explicit','regional_reference_not_municipal_confirmation'].includes(n.scope)||(!n.scope&&!/exceto|exceção|menos|não inclui/i.test(regions)&&/Araquari|Litoral Norte|todas as regi|todo o estado/i.test(regions));
    const checked=n.checked_at||source?.reference_at;
    if(!scoped||!['eligible','needs_territorial_or_temporal_check'].includes(n.status)||!fresh(checked,6,now))continue;
    if(Number.isFinite(Date.parse(n.valid_until))&&now>=Date.parse(n.valid_until))continue;
    const url=safeLink(n.url);if(!url)continue;
    add({...n,source:'Epagri/Ciram',title:n.title||'Aviso meteorológico',url,regions:regions||'Araquari e região',start_at:n.valid_from,end_at:n.valid_until,
      summary:n.summary||'',retained_previous:source?.status==='unavailable'});
  }
  const feed=data?.inmet_context||data?.complementary_notices;
  if((feed?.status==='available'||feed?.retained_previous)&&fresh(feed.retrieved_at,6,now))for(const n of list(feed.notices)){
    if(!n||typeof n!=='object')continue;
    const start=Date.parse(n.start_at),end=Date.parse(n.end_at),timed=Number.isFinite(start)&&Number.isFinite(end)&&start<end;
    if(n.lifecycle==='expired'||reportedWindowExpired(n.window_as_reported,now)||(timed&&end<=now)||(feed.retained_previous&&!timed))continue;
    const municipalities=list(n.municipalities).filter(m=>m&&(m.location_id==='araquari'||(Number.isFinite(m.distance_km)&&m.distance_km>=0&&m.distance_km<=40)));
    if(!Array.isArray(n.municipalities)&&n.ibge_code==='4201307')municipalities.push({location_id:'araquari',name:'Araquari'});
    if(!municipalities.length)continue;
    const local=municipalities.some(m=>m.location_id==='araquari');
    const direct=/^\d+$/.test(String(n.id))?'https://alertas2.inmet.gov.br/'+n.id:n.url;
    const url=safeLink(direct);if(!url)continue;
    add({...n,source:'INMET',title:n.type||'Aviso meteorológico',url,
      regions:municipalities.map(m=>m.name||m.location_id).join(', ')+(local?'':' · entorno; Araquari não confirmada'),
      summary:list(n.risks).filter(t=>typeof t==='string').join(' '),retained_previous:n.retained_previous||feed.retained_previous});
  }
  return rows;
}
function renderHomeNotices() {
  const rows=homeNotices(panel.data);
  for(const [id,source]of [['epagri','Epagri/Ciram'],['inmet','INMET']]){
    const notices=rows.filter(n=>n.source===source),disclosure=el(id+'-context'),body=el(id+'-notices');
    disclosure.hidden=!notices.length;if(!notices.length)disclosure.open=false;
    el(id+'-notice-summary').textContent=`Avisos · ${source} (${notices.length})`;
    body.replaceChildren();
    for(const n of notices){
      const card=node('article','home-notice-item');card.append(node('h3','',n.title));
      if(n.severity)paragraph(card,'Severidade: '+n.severity+'.','small');
      paragraph(card,'Abrangência: '+n.regions+'.');paragraph(card,'Período: '+noticePeriod(n)+'.');
      if(n.summary)paragraph(card,String(n.summary).slice(0,650));
      if(n.retained_previous)paragraph(card,'Consulta anterior; atualização da fonte indisponível.','small');
      card.append(officialLink(n.url,'Ler aviso completo ↗'));body.append(card);
    }
  }
}
let riskExplanationKey=null;
function renderRiskExplanation(force=false) {
  const presentation=riskPresentation(panel.data),product=panel.data?.risk_classification;
  const candidates=Array.isArray(product?.candidates)?product.candidates.filter(Boolean):[],requirements=Array.isArray(product?.requirements)?product.requirements.filter(Boolean):[];
  const key=JSON.stringify([panel.data?.generated_at,presentation.color,presentation.reason,candidates.map(c=>Date.now()<Date.parse(c.valid_until)),requirements.map(r=>r.available&&Date.now()<Date.parse(r.valid_until))]);
  if(!force&&key===riskExplanationKey)return;riskExplanationKey=key;
  const body=el('dialog-content');body.replaceChildren();body.append(node('h3','',riskNames[presentation.color]||presentation.title));paragraph(body,presentation.reason);
  const rawLevels=product?.levels||panel.data?.protocol?.levels,levels=Array.isArray(rawLevels)?rawLevels.filter(Boolean):[];
  const criterion=levels.find(l=>l.id===presentation.color)?.criterion;
  if(criterion){body.append(node('h3','','Critério utilizado'));paragraph(body,criterion);}
  const currentCandidates=candidates.filter(c=>c.level===presentation.color&&Date.now()<Date.parse(c.valid_until));
  if(currentCandidates.length){body.append(node('h3','','Evidências atuais'));for(const c of currentCandidates.slice(0,6))paragraph(body,`${c.reason} Referência válida até ${date(c.valid_until)}.`);}
  if(presentation.color==='neutral')for(const r of requirements)if(!r.available||!(Date.now()<Date.parse(r.valid_until)))paragraph(body,r.label+': ausente ou vencida.');
  paragraph(body,'Classificação consultiva. Decisões sobre as atividades cabem à autoridade institucional.','small');
  if(levels.length){const details=node('details','risk-explanation-levels');details.append(node('summary','','Ver os seis níveis'));for(const level of levels){details.append(node('h4','',riskNames[level.id]||level.name));paragraph(details,level.criterion);}body.append(details);}
  const link=node('a','','Ver análise e critérios completos →');link.href='./dados.html#weather-synthesis-detail';body.append(link);
}
function showAssessment() {renderRiskExplanation(true);if(!el('detail-dialog').open)el('detail-dialog').showModal();}

async function readJson(path,retry='') {const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),15000);try{const response=await fetch(retry?path+'?refresh='+encodeURIComponent(retry):path,{cache:'no-store',signal:controller.signal});if(!response.ok)throw new Error('HTTP '+response.status);return await response.json();}finally{clearTimeout(timer);}}
async function loadDashboard() {
  if(panel.loading)return;
  panel.loading=true;
  const id=++panel.loadId;el('refresh').disabled=true;
  try{
    let loaded;
    for(let attempt=0;attempt<2;attempt++){
      // CDN edges can briefly serve different artifacts during a deployment.
      // Retry the whole read with a fresh cache key, keeping all identity checks.
      const retry=attempt?Date.now()+'-'+id:'';
      try{
        const [latest,data,history]=await Promise.all([readJson('./data/latest.json',retry),readJson('./data/dashboard.json',retry),readJson('./data/observation_history.json',retry).catch(()=>null)]);
        if(latest.schema_version!==1||latest.fixture_mode||data.fixture_mode||data.schema_version!==1||data.kind!=='araquari_weather_dashboard_not_official_decision'||data.location_id!=='araquari'||data.decision_automated!==false||!Number.isFinite(Date.parse(data.generated_at))||Date.parse(data.generated_at)>Date.now()+600000)throw new Error('Invalid dashboard source');
        if(latest.publication_at!==undefined&&(latest.publication_at!==latest.generated_at||data.publication_at!==latest.generated_at))throw new Error('Dashboard publication mismatch');
        if(latest.generated_at!==data.generated_at)throw new Error('Publication mismatch');
        loaded={data,history:history?.kind==='araquari_point_observation_history_not_climatology'&&Array.isArray(history.records)&&history?.location_id==='araquari'&&!history.fixture_mode&&history.generated_at===data.generated_at&&(latest.publication_at===undefined||history.publication_at===latest.generated_at)?history:null};break;
      }catch(error){if(attempt===1)throw error;}
    }
    if(!loaded)throw new Error('Publication mismatch');if(id!==panel.loadId)return;
    if(panel.data&&Date.parse(loaded.data.generated_at)<Date.parse(panel.data.generated_at))throw new Error('Older publication received');
    panel.incompleteHistory=!loaded.history;
    if(!loaded.history&&panel.data?.generated_at===loaded.data.generated_at)loaded.history=panel.history;
    panel.data=loaded.data;panel.history=loaded.history;panel.fetchError=false;
    return true;
  }catch(err){if(id!==panel.loadId)return;console.error('Dashboard unavailable:',err.message);panel.fetchError=true;return false;}
  finally{if(id===panel.loadId){panel.loading=false;el('refresh').disabled=false;renderSummary();renderRecent();renderChart();}}
}
function selectVariable(variable) {panel.variable=variable;if(el('forecast-variable'))el('forecast-variable').value=variable;for(const button of document.querySelectorAll('[data-variable]')){const selected=button.dataset.variable===variable;button.classList.toggle('active',selected);button.setAttribute('aria-pressed',String(selected));}renderChart();}
if(typeof module!=='undefined')module.exports={homeNotices,noticePeriod,reportedWindowExpired,primaryNotice,inmetContextStatus,inmetNotices,fresh,dashboardCurrent,protocolCurrent,forecastCurrent,currentGauges,signalCurrent,effectiveAssessment,getChartSeries,comparableReadings,pointDescription,riskPresentation,stationName,chartScale,chartReadingsAt,chartReadingText};
if(typeof document!=='undefined'){
  function navigationState(){for(const link of document.querySelectorAll('nav a[href^="#"]')){const active=link.getAttribute('href')===(location.hash||'#main');if(active)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');}}
  window.addEventListener('hashchange',navigationState);navigationState();
  document.addEventListener('observatorythemechange',renderChart);
  el('refresh').addEventListener('click',loadDashboard);
  el('level-explain').addEventListener('click',showAssessment);
  el('dialog-close').addEventListener('click',()=>el('detail-dialog').close());
  el('detail-dialog').addEventListener('click',event=>{const dialog=el('detail-dialog'),box=dialog.getBoundingClientRect();if(event.target===dialog&&(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom))dialog.close();});
  for(const b of document.querySelectorAll('[data-variable]'))b.addEventListener('click',()=>selectVariable(b.dataset.variable));
  for(const b of document.querySelectorAll('[data-observed-focus]'))b.addEventListener('click',()=>{
    panel.hours=24;panel.rainWindow=24;panel.observedVariable='precipitation_mm';panel.observedView='stations';panel.scope='local';panel.station='all';
    el('chart-range').value='24';el('rain-window').value='24';el('observed-variable').value='precipitation_mm';el('rain-scope').value='local';
    renderChart();
    el('observed-heading').scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
  });
  for(const b of document.querySelectorAll('[data-focus]'))b.addEventListener('click',()=>{if(b.dataset.daily==='true'){location.href='./dados.html#model-comparison';return;}panel.hours=24;el('chart-range').value='24';selectVariable(b.dataset.focus);el('chart-heading').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});});
  for(const b of document.querySelectorAll('[data-observed-variable]'))b.addEventListener('click',()=>{panel.observedVariable=b.dataset.observedVariable;panel.station='all';el('observed-variable').value=panel.observedVariable;renderChart();el('observed-heading').scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});});
  el('forecast-variable')?.addEventListener('change',event=>selectVariable(event.target.value));
  el('observed-variable')?.addEventListener('change',event=>{panel.observedVariable=event.target.value;panel.station='all';renderChart();});
  el('chart-range').addEventListener('change',event=>{panel.hours=[24,72,168,240].includes(Number(event.target.value))?Number(event.target.value):24;renderChart();});
  el('rain-scope').addEventListener('change',event=>{panel.scope=event.target.value==='nearby'?'nearby':'local';panel.station='all';renderChart();});
  for(const b of document.querySelectorAll('[data-observed-view]'))b.addEventListener('click',()=>{panel.observedView=b.dataset.observedView;renderChart();});

  el('station-select').addEventListener('change',event=>{panel.station=event.target.value;renderChart();});
  el('rain-window').addEventListener('change',event=>{panel.rainWindow=Number(event.target.value)===24?24:1;renderChart();});


  const publicationRefresh=typeof PublicationRefresh!=='undefined'?PublicationRefresh.create({
    getVersion:()=>panel.data?.generated_at,needsReload:()=>panel.incompleteHistory||panel.fetchError,readLatest:()=>readJson('./data/latest.json'),
    reload:loadDashboard,isVisible:()=>!document.hidden,
    onSuccess:()=>{panel.fetchError=false;renderSummary();},
    onError:()=>{panel.fetchError=true;renderSummary();}}):null;
  setInterval(()=>{renderSummary();renderRecent();if(panel.chartExpired!==!dashboardCurrent(panel.data))renderChart();publicationRefresh?.check();},60000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden){renderSummary();renderChart();publicationRefresh?.check();}});
  window.addEventListener('online',()=>publicationRefresh?.check());
  let chartWidth=0;
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(entries=>{const width=Math.round(entries[0].contentRect.width);if(width>0&&width!==chartWidth){chartWidth=width;requestAnimationFrame(renderChart);}}).observe(el('chart-panels'));
  loadDashboard();
}
