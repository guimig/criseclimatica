'use strict';
const panel = {data:null, history:null, variable:'precipitation_mm', hours:24, rainWindow:24, observedVariable:'precipitation_mm', station:'all', scope:'local', observedView:'auto', loadId:0,loading:false,fetchError:false};
const el = id => document.getElementById(id);
const chartUtils=typeof WeatherCharts!=='undefined'?WeatherCharts:typeof require==='function'?require('./chart-utils.js'):null;
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
  const evidence=(base.evidence||[]).map(e=>({...e,status:e.status==='eligible'&&!(now<Date.parse(e.valid_until))?'expired':e.status}));
  const order={azul:1,amarelo:2,laranja:3,vermelho:4};
  const supported=evidence.filter(e=>e.status==='eligible'&&order[e.supports_level]).sort((a,b)=>order[b.supports_level]-order[a.supports_level]);
  const pendingUntil=evidence.filter(e=>e.status==='eligible').map(e=>Date.parse(e.valid_until)).filter(Number.isFinite);
  return {...base,valid_until:new Date(Math.max(Date.parse(data.valid_until)||0,...pendingUntil,now+1000)).toISOString(),evidence,suggested_level:supported[0]?.supports_level||null,
    status:supported.length?'suggested_for_review':evidence.some(e=>e.status==='eligible')?'official_advisory_under_review':'insufficient_evidence',
    primary_coverage_expired:!sourceReady,
    reason:sourceReady?'Avisos reavaliados pelos prazos individuais.':'Avisos preservados até o término oficial; a situação de revisão/cancelamento pode não estar reconfirmada.'};
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
// The legacy INMET host and API IDs are not reliable human-readable permalinks.
const INMET_PUBLIC_PORTAL='https://avisos.inmet.gov.br/';
function inmetReadableLink(address) {
  const link=safeLink(address);
  if(!link)return null;
  const host=new URL(link).hostname;
  return ['avisos.inmet.gov.br','alertas2.inmet.gov.br'].includes(host)?INMET_PUBLIC_PORTAL:null;
}
function noticeTextItems(value) {
  return Array.isArray(value)?value.filter(s=>typeof s==='string'&&s.trim()).slice(0,5).map(s=>s.trim().slice(0,1100)):[];
}
function addInmetReadableDetails(card,notice) {
  const risks=noticeTextItems(notice.risks);
  if(!risks.length&&typeof notice.summary==='string'&&notice.summary.trim())risks.push(notice.summary.trim().slice(0,1100));
  const instructions=noticeTextItems(notice.instructions);
  const disclosure=node('details','inmet-readable-details');
  disclosure.append(node('summary','','Ler riscos e orientações do aviso'));
  const body=node('div','inmet-readable-body');
  for(const [heading,lines] of [['Riscos potenciais informados pelo INMET',risks],['Instruções informadas pelo INMET',instructions]]){
    body.append(node('h4','',heading));
    if(lines.length){const list=node('ul','inmet-readable-list');for(const line of lines)list.append(node('li','',line));body.append(list);}
    else paragraph(body,'Informações detalhadas não disponibilizadas neste registro.','small');
  }
  const technicalId=String(notice.id||'');
  if(/^[a-zA-Z0-9_-]{1,50}$/.test(technicalId))paragraph(body,'Identificador na base consultada: '+technicalId+'.','small');
  paragraph(body,'O botão de consulta abre a lista oficial do INMET; localize o aviso pelo fenômeno, período e município. O identificador da API pode diferir do endereço público.','small');
  disclosure.append(body);card.append(disclosure);
}
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
  if(!dashboardCurrent(data,now)){
    const active=(data.risk_classification?.candidates||[]).filter(c=>['applicable_official_notice','qualitative_epagri_evidence'].includes(c.basis)&&now<Date.parse(c.valid_until));
    const base=currentPrimaryAssessment(data,now);
    for(const e of base?.evidence||[])if(e.status==='eligible'&&now<Date.parse(e.valid_until)&&e.supports_level)
      active.push({level:e.supports_level,valid_until:e.valid_until,basis:'qualitative_epagri_evidence'});
    const rank={verde:0,azul:1,amarelo:2,laranja:3,vermelho:4,roxo:5};
    active.sort((a,b)=>(rank[b.level]??-1)-(rank[a.level]??-1));
    if(active.length&&rank[active[0].level]>=1)return {color:active[0].level,active:active[0].level,
      title:riskNames[active[0].level],kind:'Aviso oficial vigente · consulta não reconfirmada',
      reason:'O aviso permanece em seu período oficial. A atualização das demais medições ou a existência de revisão/cancelamento ainda não foram confirmadas.'};
    const local=(data.inmet_context?.notices||[]).some(n=>n.municipalities?.some(m=>m.location_id==='araquari')&&now<Date.parse(n.end_at));
    if(local)return {color:'amarelo',active:null,title:'Aviso oficial vigente para Araquari',
      kind:'Aviso preservado · consulta não reconfirmada',reason:'A validade do aviso INMET não depende da atualização dos demais dados. Confira a fonte oficial para revisões.'};
    return {color:'neutral',active:null,title:'Atualização necessária',kind:'Dados desatualizados',reason:'A última atualização perdeu validade. Consulte as fontes oficiais enquanto aguarda novos dados.'};
  }
  const weather=data.risk_classification&&typeof WeatherSynthesis!=='undefined'?WeatherSynthesis.riskLevel(data.risk_classification,now):null;
  if(weather)return weather;
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
  const days=data?.synthesis?.forecast_context?.days||[];
  return ['INMET','CPTEC/INPE'].map(source=>days.find(d=>d.source===source&&d.day===today&&Date.now()<Date.parse(d.valid_until))).find(Boolean);
}
function renderSummary() {
  const data=panel.data,current=dashboardCurrent(data),presentation=riskPresentation(data);
  el('publication-time').textContent=data?'Atualizado em '+date(data.generated_at):'Atualização indisponível';
  el('publication-status').hidden=current&&!panel.fetchError&&!panel.incompleteHistory;
  el('publication-status').textContent=panel.fetchError?'Falha ao atualizar. Nova tentativa automática.':panel.incompleteHistory?'Histórico temporariamente indisponível.':data?'Coleta atrasada.':'Não foi possível carregar os dados.';
  el('level-dot').className='level-dot '+presentation.color;el('level-card').dataset.risk=presentation.color;
  el('level-title').textContent=riskNames[presentation.color]||presentation.title;
  el('level-kind').textContent=presentation.color==='neutral'?'Dados parciais':data?.risk_classification?.coverage?.regional_reference_used?'Consultivo · referência regional':data?.risk_classification?.coverage?.forecast_resolution==='mixed_or_qualitative'?'Consultivo · previsão por turnos':'Consultivo';
  el('level-reason').textContent=data?.risk_classification?presentation.reason:!data?'Consultando os dados.':presentation.color==='verde'?'Chuva e vento abaixo das faixas de atenção.':presentation.reason.split('. ')[0]+'.';
  for(const item of document.querySelectorAll('[data-risk-level]')){
    const active=item.dataset.riskLevel===(presentation.active||presentation.color);item.classList.toggle('is-active',active);
    if(active)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');
  }
  renderBorderingAlerts();
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
    const peak=field==='gust_kmh'?(data?.synthesis?.signals||[]).filter(r=>r.support==='five_minute_peak'&&r.variable===field&&Date.now()<Date.parse(r.valid_until)).sort((a,b)=>b.value-a.value)[0]:null;
    updateMetric(name,stats?num(field==='gust_kmh'?stats.max:stats.median)+' '+unit:'—',(stats?`${stats.count} ${stats.count===1?'estação':'estações'} · ${compactTime(stats.members[0].end_at)}`:'Sem leitura recente')+(peak?' · pico IFC: '+num(peak.value)+' km/h':''));

  }
  const daily=dailyForecast(data),label=el('temperature-label');if(label)label.textContent='MÁXIMA · PRÓX. 24 H';
  const tempButton=document.querySelector('[data-focus="temperature_c"]');if(tempButton){tempButton.dataset.daily='false';tempButton.dataset.dailyTarget='#model-comparison';}
  if(!heatValid&&daily&&Number.isFinite(daily.maximum_c)){
    updateMetric('temperature',num(daily.maximum_c)+' °C',daily.source+' · previsão diária');if(label)label.textContent='MÁXIMA · HOJE';if(tempButton){tempButton.dataset.daily='true';tempButton.dataset.dailyTarget=daily.source==='INMET'?'#model-comparison':'#weather-synthesis-detail';}
  }
  const brief=el('forecast-brief');if(brief){
    const hour=Number(new Intl.DateTimeFormat('en',{timeZone,hour:'numeric',hourCycle:'h23'}).format(new Date()));
    const order=hour<12?['manha','tarde','noite','dia']:hour<18?['tarde','noite','dia']:['noite','dia'];
    const period=daily?.periods?.filter(p=>order.includes(p.period)).sort((a,b)=>order.indexOf(a.period)-order.indexOf(b.period))[0];
    brief.textContent=period?.summary?`Hoje${{manha:' de manhã',tarde:' à tarde',noite:' à noite',dia:''}[period.period]}: ${period.summary.replace(/[.\s]+$/,'').toLocaleLowerCase('pt-BR')}${daily.source==='CPTEC/INPE'?' (CPTEC/INPE)':''}.`:'';
    brief.hidden=!brief.textContent;
  }
}
function stationReference(data,source,station) {
  if(source==='ifc')return {source,station,name:'IFC Araquari',municipality:'Araquari'};
  return [...(data?.station_catalog||[]),...(data?.regional_rain_context?.stations||[])].find(r=>r.source===source&&r.station===station)||{};
}
function getChartSeries(data,history,mode,variable,hours,now=Date.now(),observedRainField='rain_1h_mm',includeCampus=true) {
  const anchor=Number.isFinite(Date.parse(data?.generated_at))?Date.parse(data.generated_at):now;
  if(mode==='context')return [
    ...getChartSeries(data,history,'observed',variable,hours,anchor,observedRainField,includeCampus).map(s=>({...s,kind:'observation'})),
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
  const mapping={temperature_c:'temperature',wind_kmh:'wind_avg',gust_kmh:'wind_gust',rain_1h_mm:'rain_1h'};
  if(includeCampus){
    const earliest=new Map();
    for(const field of fields){
      const dense=data?.synthesis?.campus_history?.series?.[mapping[field]]||[];
      if(dense.length)earliest.set(field,Date.parse(dense[0].time));
      for(const r of dense)rows.push({source:'ifc',station:'ifc-araquari',observed_at:r.time,[field]:r.value,
        intervalMinutes:r.interval_minutes,count:r.count,approximate:field==='rain_1h_mm'});
    }
    for(const r of data?.synthesis?.observation_history||[]){
      if(r.source==='ifc'&&fields.includes(r.variable)&&(!earliest.has(r.variable)||Date.parse(r.end_at)<earliest.get(r.variable)))
        rows.push({source:'ifc',station:r.station,observed_at:r.end_at,[r.variable]:r.value,intervalMinutes:30,
          approximate:r.variable==='rain_1h_mm'});
    }
  }
  for(const r of rows) {
    if(!includeCampus&&r.source==='ifc')continue;
    const t=Date.parse(r.observed_at);
    if(!Number.isFinite(t)||t>anchor||t<anchor-hours*3600000)continue;
    for(const key of fields) {
      if(!Number.isFinite(r[key]))continue;
      const id=r.source+':'+r.station+':'+key,ref=stationReference(data,r.source,r.station);
      const name=stationName(ref,'Estação sem nome');
      if(!grouped.has(id))grouped.set(id,{id,station:r.station,source:r.source,reference:ref,
        name:`${name}${ref.municipality&&String(ref.municipality).trim().toLocaleLowerCase('pt-BR')!=='araquari'?' · '+ref.municipality:''}${variable==='gust_kmh'?(key==='gust_kmh'?' · rajada':' · vento'):''}`,
        field:key,identity:r.source+':'+r.station,points:[],gapMs:r.source==='ifc'?2160000:r.source==='metar'?5400000:3600000,kind:'observation'});
      grouped.get(id).points.push({time:r.observed_at,value:r[key],distance_km:r.distance_km,
        gapMs:r.intervalMinutes?Math.round(r.intervalMinutes*1.2*60000):undefined,
        qualifier:r.approximate?'intervalo aproximado':r.count?`${r.intervalMinutes} min${r.intervalMinutes===30?' · '+r.count+'/6 intervalos':''}`:undefined,
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
  return `${series.kind==='forecast'?'Open-Meteo · ':''}${series.name}: ${num(p.value)} ${unit} · ${interval}${current}${p.qualifier?' · '+p.qualifier:''}`;
}
function chartScale(values,temperature=false) {return chartUtils.scale(values,temperature);}
function drawStationSnapshot(target,legend,tooltip,series,unit) {
  target.replaceChildren();legend.replaceChildren();tooltip.hidden=true;
  const latest=series.filter(s=>s.points.length).map(s=>({s,p:s.points[s.points.length-1]}));
  if(!latest.length){target.append(node('p','empty','Sem leituras de chuva para este recorte. Consulte a cobertura e os horários.'));return;}
  const scale=chartScale(latest.map(r=>r.p.value)),W=Math.max(180,Math.round(target.clientWidth||600)),H=Math.max(250,latest.length*78+28),L=12,R=90,top=4;
  const width=W-L-R,x=v=>L+v/scale.high*width,anchor=Date.parse(panel.data?.generated_at),rowHeight=(H-28)/latest.length;
  const root=svg('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':`Último acumulado de chuva por estação, em ${unit}. Use as setas para consultar; Enter fixa e Escape libera.`,tabindex:0});
  latest.forEach(({s,p},i)=>{
    const y=top+i*rowHeight,barY=y+48,name=s.name.length>28?s.name.slice(0,27)+'…':s.name;
    root.append(svg('text',{x:L,y:y+15,class:'snapshot-name'},name),svg('text',{x:L,y:y+35,class:'snapshot-time'},chartUtils.date(p.time)),
      svg('rect',{x:L,y:barY,width,height:10,rx:4,class:'snapshot-track'}));
    const bar=svg('rect',{x:L,y:barY,width:Math.max(0,x(p.value)-L),height:10,rx:4,fill:s.color,class:'station-bar'});bar.append(svg('title',{},pointDescription(s,p,unit,anchor)));
    root.append(bar,svg('text',{x:W-2,y:barY+10,'text-anchor':'end',class:'snapshot-value'},num(p.value)+' '+unit));
  });
  if(typeof ChartInteraction!=='undefined')ChartInteraction.attach(root,{axis:'y',width:W,left:0,right:0,top:top+rowHeight/2,bottom:top+(latest.length-.5)*rowHeight,
    domain:[0,Math.max(1,latest.length-1)],times:latest.map((_,i)=>i),tooltip,lookup(t){const {s,p}=latest[Math.max(0,Math.min(latest.length-1,Math.round(t)))];return {text:pointDescription(s,p,unit,anchor),marks:[]};}});
  target.append(root);
}
function drawWeatherChart(target,legend,tooltip,series,domain,label,unit,sharedScale=null,options={}) {
  return chartUtils.render(target,legend,tooltip,series,{domain,label,unit,sharedScale,...options});
}
function chartValidity() {return ['precipitation_mm','wind_kmh','gust_kmh','temperature_c'].map(field=>forecastFieldCurrent(panel.data,field)).join(':');}
function chartRangeLabel(hours) {return hours===168?'7 dias':hours===240?'10 dias':hours+' h';}
function chartDescription(series,unit,cumulative=false) {
  const points=series.flatMap(s=>s.points.filter(p=>Number.isFinite(p.value)).map(p=>({...p,series:s})));
  if(!points.length)return '';
  const peak=points.reduce((a,b)=>a.value>=b.value?a:b);
  const prefix=cumulative?'Maior acumulado amostrado':'Maior valor no recorte';
  return `${prefix}: ${num(peak.value)} ${unit} · ${peak.series.name} · ${chartUtils.date(peak.time)}.`;
}
function renderChart() {
  panel.chartExpired=!dashboardCurrent(panel.data);panel.chartValidity=chartValidity();
  const data=panel.data,anchor=Number.isFinite(Date.parse(data?.generated_at))?Date.parse(data.generated_at):Date.now(),rain=panel.observedVariable==='precipitation_mm',forecastRain=panel.variable==='precipitation_mm';
  const nearby=rain&&panel.scope==='nearby',history=nearby?{records:data?.regional_rain_context?.records||[]}:panel.history;
  const dark=document.documentElement.dataset.theme==='dark';
  const allObserved=getChartSeries(data,history,'observed',panel.observedVariable,panel.hours,anchor,`rain_${panel.rainWindow}h_mm`,!nearby).map(s=>({...s,...chartUtils.identity(s.source+':'+s.station,s.field,dark)}));
  const validForecast=forecastFieldCurrent(data,panel.variable);
  const forecast=validForecast?getChartSeries(data,panel.history,'forecast',panel.variable,panel.hours,anchor).filter(s=>forecastFieldCurrent(data,s.field)).map(s=>{
    const source=data?.forecast?.sources_by_variable?.[s.field];
    return {...s,identity:source?.id||s.id,name:s.name+(source?.name?' · '+source.name:'')};
  }):[];
  const selector=el('station-select');selector.replaceChildren();const all=node('option','','Todas as estações');all.value='all';selector.append(all);
  const keys=new Set();for(const s of allObserved){const key=s.source+':'+s.station;if(keys.has(key))continue;keys.add(key);const option=node('option','',s.name.replace(/ · (vento|rajada)$/, ''));option.value=key;selector.append(option);}
  if(panel.station!=='all'&&!keys.has(panel.station))panel.station='all';selector.value=panel.station;
  const observed=allObserved.filter(s=>panel.station==='all'||s.source+':'+s.station===panel.station);
  el('observed-panel').hidden=false;el('forecast-panel').hidden=false;
  el('rain-window-control').hidden=!rain;el('rain-scope-control').hidden=!rain;el('observed-view-controls').hidden=!rain;el('rain-scope').value=panel.scope;el('rain-window').value=String(panel.rainWindow);
  const variable=rain?'Chuva':panel.observedVariable==='temperature_c'?'Temperatura':'Vento e rajadas',unit=rain?'mm':panel.observedVariable==='temperature_c'?'°C':'km/h',forecastUnit=forecastRain?'mm':panel.variable==='temperature_c'?'°C':'km/h';
  el('chart-heading').textContent='Observações e previsão';el('recent-summary').hidden=panel.observedVariable!=='temperature_c';
  el('observed-heading').textContent=rain?`Chuva medida · acumulado de ${panel.rainWindow} h`:'Observado · '+variable.toLowerCase();
  const forecastSource=data?.forecast?.sources_by_variable?.[panel.variable];
  if(el('forecast-source'))el('forecast-source').textContent=(forecastSource?.id==='best_match'?'Previsão horária':forecastSource?.name||'Previsão horária')+(forecastSource?.retained_previous?' · consulta anterior':'');
  el('forecast-heading').textContent=forecastRain?'Chuva prevista · por hora':panel.variable==='temperature_c'?'Temperatura prevista':forecast.some(s=>s.field==='wind_kmh')?'Vento e rajadas previstos':'Rajadas previstas';
  el('chart-period').textContent='Horários de Brasília';
  const base=Number.isFinite(Date.parse(data?.forecast?.start_at))?Date.parse(data.forecast.start_at):Math.floor(anchor/3600000)*3600000;
  const values=[...observed,...forecast].flatMap(s=>s.points.filter(p=>Number.isFinite(p.value)).map(p=>p.value));
  // Rain may be grouped on long horizons; share only the ungrouped hourly scale.
  let shared=panel.variable===panel.observedVariable&&(!rain||(panel.rainWindow===1&&panel.hours===24))&&values.length?chartScale(values,panel.variable==='temperature_c'):null;
  const times=new Set(observed.flatMap(s=>s.points.map(p=>p.time))),view=panel.observedView==='auto'?(times.size<4?'stations':'timeline'):panel.observedView;
  const snapshot=rain&&view==='stations';if(snapshot)shared=null;
  for(const b of document.querySelectorAll('[data-observed-view]')){const selected=b.dataset.observedView===view;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected));}
  const observedTitle=el('observed-heading').textContent;
  const observedForTable=snapshot?observed.map(s=>({...s,points:s.points.slice(-1)})):observed;
  if(snapshot){drawStationSnapshot(el('plot'),el('chart-legend'),el('chart-tooltip'),observed,unit);chartUtils.dataTable(el('observed-chart-data'),observedForTable,{label:observedTitle,unit,cumulativeHours:panel.rainWindow});}
  else drawWeatherChart(el('plot'),el('chart-legend'),el('chart-tooltip'),observed,[anchor-panel.hours*3600000,anchor],observedTitle,unit,shared,{cumulativeHours:rain?panel.rainWindow:0,tableHost:el('observed-chart-data')});
  el('plot').classList.toggle('snapshot-plot',snapshot);
  const result=drawWeatherChart(el('forecast-plot'),el('forecast-legend'),el('forecast-tooltip'),forecast,[base,base+panel.hours*3600000],el('forecast-heading').textContent,forecastUnit,shared,
    {forecast:true,tableHost:el('forecast-chart-data'),emptyText:validForecast?'Sem intervalos completos para esta variável e período. Lacunas não significam zero.':'Previsão horária indisponível ou desatualizada. Consulte as fontes.'});
  if(forecastRain&&result.block>1)el('forecast-heading').textContent=`Chuva prevista · blocos de ${result.block} h`;
  el('observed-period').textContent=snapshot?'Última leitura disponível de cada estação':`Últimas ${chartRangeLabel(panel.hours)} · ${date(new Date(anchor-panel.hours*3600000).toISOString())} — ${date(new Date(anchor).toISOString())}`;
  const stations=new Set(observed.map(s=>s.source+':'+s.station));
  const sources=[...new Set(observed.map(s=>s.source==='ifc'?'IFC':String(s.source).includes('metar')?'METAR':String(s.source).startsWith('cemaden')?'Cemaden':'Estações'))];
  el('observed-source').textContent=rain?(nearby?'Cemaden · entorno':'Estações de Araquari'):sources.join(' / ')||'Sem leituras';
  const filter=panel.station==='all'?'todas as estações':selector.options?.[selector.selectedIndex]?.textContent||'estação selecionada';
  el('observed-filter').textContent=`${nearby?'Entorno · até 40 km':rain?'Araquari':'Estações disponíveis'} · ${filter}`;
  el('station-coverage').textContent=`${stations.size} ${stations.size===1?'estação':'estações'} · ${rain?(nearby?'entorno':'Araquari'):'leituras disponíveis'}`;
  el('forecast-period').textContent=`Próximas ${chartRangeLabel(panel.hours)} · ${date(new Date(base).toISOString())} — ${date(new Date(base+panel.hours*3600000).toISOString())}`;
  const endpoints=observed.flatMap(s=>s.points.map(p=>Date.parse(p.time))).filter(Number.isFinite),last=endpoints.length?new Date(Math.max(...endpoints)).toISOString():null;
  el('observed-status').textContent=(last?'Última amostra: '+date(last)+'. ':'Sem amostras. ')+(panel.hours>168?'Histórico disponível: até 7 dias.':'');
  const reference=forecastSource?.reference_at||data?.forecast?.reference_at||data?.forecast?.collected_at;
  el('forecast-status').textContent=validForecast?`${result.coverage} Referência da previsão: ${date(reference)}.`:'Sem previsão horária vigente.';
  el('observed-caption').textContent=rain?(snapshot?`Acumulado de ${panel.rainWindow} h por estação.`:`Cada ponto representa as ${panel.rainWindow} h anteriores ao horário da leitura. Janelas móveis não se somam; cinza indica falta de amostras.`):'Leituras por estação. Traço contínuo: vento; tracejado: rajada.';
  if(observed.some(s=>s.source==='ifc'))el('observed-caption').textContent+=' IFC: referências de 5 min nas últimas 24 h; histórico anterior resumido em 30 min.'+(rain?' Chuva de 1 h derivada do contador é aproximada.':'');
  el('forecast-caption').textContent=forecastRain?(result.block>1?`Somente blocos completos de ${result.block} h recebem barras. Os valores horários originais estão na tabela.`:'Barras de 1 h. Marcas na base representam zero; faixas cinza indicam lacunas.'):'Previsão horária. Interrupções indicam ausência de amostras.';
  el('observed-chart-summary').textContent=chartDescription(observedForTable,unit,rain);
  el('forecast-chart-summary').textContent=chartDescription(result.series,forecastUnit,forecastRain);
  el('chart-caption').textContent=rain&&forecastRain&&panel.rainWindow===24?'Observado: acumulado móvel de 24 h. Previsto: intervalos sem sobreposição. Escalas próprias.':'Medições e previsão têm fontes e períodos próprios.';
  if(panel.chartExpired)el('chart-caption').textContent='Publicação desatualizada. '+el('chart-caption').textContent;
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
  return ((currentPrimaryAssessment(data,now)||data?.assessment)?.evidence||[]).find(n=>n.status==='eligible'&&now<Date.parse(n.valid_until))||null;
}
function inmetNotices(data,now=Date.now()) {
  const feed=data?.inmet_context||data?.complementary_notices;
  if(feed?.status!=='available'&&!feed?.retained_previous)return [];
  const current=fresh(feed.retrieved_at,6,now);
  return (feed.notices||[]).filter(n=>n.lifecycle!=='expired'&&(!n.end_at||now<Date.parse(n.end_at))&&((Number.isFinite(Date.parse(n.start_at))&&Number.isFinite(Date.parse(n.end_at))&&Date.parse(n.start_at)<Date.parse(n.end_at))||current)&&(!feed.retained_previous||(Number.isFinite(Date.parse(n.start_at))&&Number.isFinite(Date.parse(n.end_at))&&Date.parse(n.start_at)<Date.parse(n.end_at))));
}
function inmetContextStatus(data,now=Date.now()) {
  const feed=data?.inmet_context||data?.complementary_notices;
  if(feed?.retained_previous&&inmetNotices(data,now).length)return {title:'Avisos INMET · consulta anterior',description:'A consulta atual falhou. Os avisos abaixo foram preservados com seus horários originais e prazo informado ainda não encerrado; revisão ou cancelamento não confirmados.'};
  if(!data)return {title:'Consultando avisos INMET',description:'Aguardando a consulta de Araquari e entorno.'};
  if(feed?.retrieved_at&&!fresh(feed.retrieved_at,6,now)&&inmetNotices(data,now).length)return {title:'Avisos INMET · consulta anterior',description:'Avisos preservados até o fim oficial; revisões/cancelamentos ainda não reconfirmados.'};
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
  // Never repeat a featured official INMET notice in the collapsible list.
  const bordering=borderingNotices(data,now,1);
  const featuredIds=new Set(bordering.filter(n=>n.severity_rank>=2).map(n=>n.id));
  function add(row){const key=row.source+':'+(row.id||row.url||row.title);if(!seen.has(key)){seen.add(key);rows.push(row);}}
  const source=data?.source_status?.find(s=>s.source==='Epagri/Ciram · avisos');
  for(const n of list(data?.assessment?.base_assessment?.evidence||data?.assessment?.evidence)){
    if(!n||typeof n!=='object')continue;
    const regions=String(n.regions_text||'');
    const scoped=['municipality_explicit','regional_reference_not_municipal_confirmation','territory_needs_review'].includes(n.scope);
    const checked=n.checked_at||source?.reference_at;
    if(!scoped||!['eligible','needs_territorial_or_temporal_check'].includes(n.status))continue;
    if(Number.isFinite(Date.parse(n.valid_until))&&now>=Date.parse(n.valid_until))continue;
    const url=safeLink(n.url);if(!url)continue;
    add({...n,source:'Epagri/Ciram',title:n.title||'Aviso meteorológico',url,regions:regions||'Araquari e região',start_at:n.valid_from,end_at:n.valid_until,
      summary:n.summary||'',retained_previous:source?.status==='unavailable'});
  }
  const feed=data?.inmet_context||data?.complementary_notices;
  if(feed?.status==='available'||feed?.retained_previous)for(const n of list(feed.notices)){
    if(!n||typeof n!=='object'||featuredIds.has(String(n.id)))continue;
    const start=Date.parse(n.start_at),end=Date.parse(n.end_at),timed=Number.isFinite(start)&&Number.isFinite(end)&&start<end;
    if(n.lifecycle==='expired'||reportedWindowExpired(n.window_as_reported,now)||(timed&&end<=now)||(!fresh(feed.retrieved_at,6,now)&&!timed)||(feed.retained_previous&&!timed))continue;
    const municipalities=list(n.municipalities).filter(m=>m&&(m.location_id==='araquari'||(Number.isFinite(m.distance_km)&&m.distance_km>=0&&m.distance_km<=40)));
    if(!Array.isArray(n.municipalities)&&n.ibge_code==='4201307')municipalities.push({location_id:'araquari',name:'Araquari'});
    if(!municipalities.length)continue;
    const local=municipalities.some(m=>m.location_id==='araquari');
    const url=inmetReadableLink(n.url);if(!url)continue;
    add({...n,source:'INMET',title:n.type||'Aviso meteorológico',url,
      regions:municipalities.map(m=>m.name||m.location_id).join(', ')+(local?'':' · entorno; Araquari não confirmada'),
      summary:list(n.risks).filter(t=>typeof t==='string').join(' '),retained_previous:n.retained_previous||feed.retained_previous});
  }
  // Lower-severity neighboring warnings belong to the regular INMET disclosure.
  // This also covers bordering municipalities outside the old 40-km point radius.
  for(const n of bordering.filter(row=>row.severity_rank===1)){
    add({...n,source:'INMET',title:n.title||'Aviso meteorológico',
      regions:n.municipalities.map(m=>m.name).join(', ')+' · entorno; Araquari não confirmada',
      summary:list(n.risks).filter(t=>typeof t==='string').join(' ')});
  }
  for(const p of list(data?.synthesis?.publication_evidence)){
    if(p.source!=='Epagri/Ciram'||!(now<Date.parse(p.valid_until))||!fresh(p.collected_at,6,now))continue;
    const url=safeLink(p.url);if(!url)continue;
    add({...p,id:p.url,publication_type:'Previsão editorial',regions:p.scope==='municipality_explicit'?'Araquari':'Referência regional',url});
  }
  return rows;
}

function borderingNotices(data,now=Date.now(),minimumRank=2) {
  const feed=data?.bordering_notice_context;
  if(feed?.kind!=='inmet_bordering_municipality_warning_context_not_araquari_alert'||!['available','retained_unconfirmed'].includes(feed.status)||!Array.isArray(feed.notices))return [];
  const seen=new Set(),rows=[];
  for(const n of feed.notices.slice(0,100)){
    if(!n)continue;
    const normalized=String(n.severity||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();
    const rank={'perigo potencial':1,'perigo':2,'grande perigo':3}[normalized];
    if(!rank||rank!==n.severity_rank||rank<minimumRank)continue;
    if(n.araquari_included!==false||n.scope!=='bordering_municipalities_only'||typeof n.id!=='string'||seen.has(n.id))continue;
    const start=Date.parse(n.start_at),end=Date.parse(n.end_at);
    if(!Number.isFinite(start)||!Number.isFinite(end)||!(start<end)||now>=end)continue;
    const places=Array.isArray(n.municipalities)?n.municipalities.filter(m=>m&&typeof m.name==='string'&&/^\d{7}$/.test(m.ibge_code||'')&&m.ibge_code!=='4201307').slice(0,16):[];
    if(!places.length)continue;
    const url=inmetReadableLink(n.url);
    if(!url)continue;
    seen.add(n.id);
    rows.push({...n,municipalities:places,verified_current:now>=start,high_severity:n.severity_rank>=2,url,
      retained_previous:n.retained_previous||feed.status==='retained_unconfirmed'});
  }
  return rows.sort((a,b)=>Number(b.high_severity)-Number(a.high_severity)||b.severity_rank-a.severity_rank||Date.parse(a.start_at)-Date.parse(b.start_at));
}
function borderingAlertSummary(rows) {
  if(!rows.length)return null;
  const maximum=Math.max(...rows.map(n=>n.severity_rank));
  const municipalities=[...new Set(rows.flatMap(n=>n.municipalities.map(p=>p.name)))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
  const named=municipalities.slice(0,3).join(', ');
  const extra=municipalities.length>3?` e mais ${municipalities.length-3}`:'';
  const active=rows.filter(n=>n.verified_current).length;
  const scheduled=rows.length-active;
  const phases=[];
  if(active)phases.push(`${active} vigente${active===1?'':'s'}`);
  if(scheduled)phases.push(`${scheduled} programado${scheduled===1?'':'s'}`);
  if(rows.some(n=>n.retained_previous))phases.push('consulta anterior; verificar revisões');
  return {
    severity:maximum===3?'grande-perigo':'perigo',
    label:maximum===3?'Grande Perigo':'Perigo',
    preview:`${rows.length} aviso${rows.length===1?'':'s'} · ${phases.join(', ')} · ${named}${extra} · Araquari não incluída`,
  };
}
function renderBorderingAlerts(now=Date.now()) {
  const shell=el('bordering-alerts'),body=el('bordering-alerts-content');
  if(!shell||!body)return;
  const rows=borderingNotices(panel.data,now);
  shell.hidden=!rows.length;
  body.replaceChildren();
  if(!rows.length){shell.open=false;return;}
  const summary=borderingAlertSummary(rows);
  shell.dataset.severity=summary.severity;
  el('bordering-heading').textContent='Perigo no entorno imediato de Araquari';
  el('bordering-alerts-badge').textContent=summary.label;
  el('bordering-alerts-preview').textContent=summary.preview;
  for(const n of rows){
    const card=node('article','bordering-alert-item high-severity');
    card.dataset.severity=n.severity_rank===3?'grande-perigo':'perigo';
    const title=node('h3','','INMET · '+n.severity);
    card.append(title);
    paragraph(card,n.title+' · '+n.municipalities.map(p=>p.name).join(', ')+'.');
    paragraph(card,(n.verified_current?'Vigente':'Programado')+' · '+date(n.start_at)+' até '+date(n.end_at)+'.','small');
    if(n.retained_previous)paragraph(card,'Consulta anterior: revisão ou cancelamento ainda não reconfirmados.','small');
    const validRisks=Array.isArray(n.risks)?n.risks.filter(r=>typeof r==='string').slice(0,2):[];
    if(validRisks.length)paragraph(card,validRisks.join(' · ').slice(0,430),'small');
    addInmetReadableDetails(card,n);
    card.append(officialLink(n.url,'Consultar avisos no portal INMET ↗'));
    body.append(card);
  }
}

// Official source text stays intact; only the first reading layer is condensed.
function noticePhase(notice,now=Date.now()) {
  const start=Date.parse(notice.start_at),end=Date.parse(notice.end_at);
  if(!Number.isFinite(start)||!Number.isFinite(end)||start>=end)return 'Horário a conferir';
  return now<start?'Programado':now<end?'Vigente':'Encerrado';
}
function noticeScopePreview(notice) {
  const raw=String(notice.regions||'').trim().replace(/\.+$/,'');
  if(!raw)return 'Abrangência a conferir';
  if(notice.source!=='INMET')return raw.slice(0,85);
  const places=raw.split(' · ')[0].split(',').map(p=>p.trim()).filter(Boolean);
  if(places.some(p=>p.toLocaleLowerCase('pt-BR')==='araquari')){
    return places.length>1?`Araquari e mais ${places.length-1} município${places.length===2?'':'s'}`:'Araquari';
  }
  return places.length>2?`${places[0]} e mais ${places.length-1} municípios`:raw.slice(0,85);
}
function noticePreview(notice,now=Date.now()) {
  const phase=noticePhase(notice,now),start=Date.parse(notice.start_at),end=Date.parse(notice.end_at);
  const validity=Number.isFinite(start)&&Number.isFinite(end)&&start<end?'até '+date(notice.end_at):'validade a confirmar';
  return `${phase} · ${validity} · ${noticeScopePreview(notice)}`;
}
function noticeSourceSummary(notices,now=Date.now()) {
  const counts={Vigente:0,Programado:0,'Horário a conferir':0};
  for(const n of notices){
    const phase=noticePhase(n,now);
    if(Object.hasOwn(counts,phase))counts[phase]++;
  }
  const result=[];
  if(counts.Vigente)result.push(`${counts.Vigente} vigente${counts.Vigente===1?'':'s'}`);
  if(counts.Programado)result.push(`${counts.Programado} programado${counts.Programado===1?'':'s'}`);
  if(counts['Horário a conferir'])result.push(`${counts['Horário a conferir']} a conferir`);
  if(notices.some(n=>n.retained_previous))result.push('consulta anterior');
  return result.join(' · ');
}
function noticeSeverityClass(severity) {
  const term=String(severity||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();
  return {'grande perigo':'grande-perigo','perigo':'perigo','perigo potencial':'potencial'}[term]||'neutral';
}
function noticeKey(n) {return [n.source,n.id||n.url||n.title,n.start_at||''].join('::').slice(0,500);}
function renderHomeNotices() {
  const now=Date.now(),rows=homeNotices(panel.data,now);
  let visible=0;
  for(const [id,source]of [['epagri','Epagri/Ciram'],['inmet','INMET']]){
    const notices=rows.filter(n=>n.source===source),disclosure=el(id+'-context'),body=el(id+'-notices');
    const expanded=new Set([...body.querySelectorAll('.notice-entry[open]')].map(x=>x.dataset.noticeKey));
    disclosure.hidden=!notices.length;
    if(!notices.length)disclosure.open=false;
    else visible++;
    const label=notices.some(n=>n.publication_type)?'Avisos e previsões':'Avisos';
    const phases=noticeSourceSummary(notices,now);
    el(id+'-notice-summary').textContent=`${label} · ${source} (${notices.length})${phases?' · '+phases:''}`;
    body.replaceChildren();
    if(!notices.length)continue;
    let allToggle=null;
    const updateToggle=()=>{
      if(!allToggle)return;
      const entries=[...body.querySelectorAll('.notice-entry')];
      allToggle.textContent=entries.every(n=>n.open)?'Recolher todos':'Expandir todos';
    };
    if(notices.length>1){
      const bar=node('div','notice-actions');
      allToggle=node('button','notice-toggle-all','Expandir todos');
      allToggle.type='button';
      allToggle.addEventListener('click',()=>{
        const entries=[...body.querySelectorAll('.notice-entry')],open=!entries.every(n=>n.open);
        for(const entry of entries)entry.open=open;
        updateToggle();
      });
      bar.append(allToggle);body.append(bar);
    }
    for(const n of notices){
      const card=node('details','notice-entry'),header=node('summary','notice-entry-summary'),content=node('div','notice-entry-body');
      card.dataset.noticeKey=noticeKey(n);
      card.open=expanded.has(card.dataset.noticeKey);
      const heading=node('span','notice-entry-heading');
      heading.append(node('strong','notice-entry-title',n.title||'Aviso meteorológico'));
      heading.append(node('span','notice-entry-subtitle',noticePreview(n,now)));
      header.append(heading);
      if(n.severity){
        const badge=node('span','notice-severity',n.severity);
        badge.dataset.severity=noticeSeverityClass(n.severity);
        header.append(badge);
      }
      if(n.retained_previous)header.append(node('span','notice-reconfirmation','Consulta anterior'));
      card.append(header);
      if(n.publication_type)paragraph(content,n.publication_type,'small');
      paragraph(content,'Abrangência: '+String(n.regions||'Não informada').replace(/\.+$/,'')+'.');
      paragraph(content,'Período: '+noticePeriod(n,now)+'.');
      if(n.source==='INMET')addInmetReadableDetails(content,n);
      else if(n.summary)paragraph(content,String(n.summary).slice(0,650),'notice-original-summary');
      if(n.scope==='territory_needs_review')paragraph(content,'Possível abrangência territorial: conferir o texto oficial.','small');
      if(n.retained_previous)paragraph(content,'Consulta anterior; atualização da fonte indisponível.','small');
      const linkText=n.source==='INMET'?'Consultar avisos no portal INMET ↗':n.publication_type?'Ler previsão completa ↗':'Ler aviso completo ↗';
      content.append(officialLink(n.url,linkText));card.append(content);
      card.addEventListener('toggle',updateToggle);
      body.append(card);
    }
    updateToggle();
  }
  el('notice-layout').dataset.visible=String(visible);
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
  if(currentCandidates.length){body.append(node('h3','','Evidências atuais'));const linked=new Set();for(const c of currentCandidates.slice(0,6)){
    paragraph(body,`${c.reason} Referência válida até ${date(c.valid_until)}.`);
    for(const e of c.evidence||[]){
      const inmet=String(e.source||'').toUpperCase().startsWith('INMET')||Boolean(e.url&&inmetReadableLink(e.url));
      const url=inmet?inmetReadableLink(e.url||INMET_PUBLIC_PORTAL):safeLink(e.url);
      if(url&&!linked.has(url)){linked.add(url);body.append(officialLink(url,inmet?'Consultar avisos no portal INMET ↗':'Ler publicação completa ↗'));}
    }
  }}
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
if(typeof module!=='undefined')module.exports={dailyForecast,inmetReadableLink,borderingNotices,borderingAlertSummary,homeNotices,noticePhase,noticeScopePreview,noticePreview,noticeSourceSummary,noticeSeverityClass,noticePeriod,reportedWindowExpired,primaryNotice,inmetContextStatus,inmetNotices,fresh,dashboardCurrent,protocolCurrent,forecastCurrent,currentGauges,signalCurrent,effectiveAssessment,getChartSeries,comparableReadings,pointDescription,riskPresentation,stationName,chartScale};
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
  for(const b of document.querySelectorAll('[data-focus]'))b.addEventListener('click',()=>{if(b.dataset.daily==='true'){location.href='./dados.html'+(b.dataset.dailyTarget||'#model-comparison');return;}panel.hours=24;el('chart-range').value='24';selectVariable(b.dataset.focus);el('chart-heading').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});});
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
  setInterval(()=>{renderSummary();renderRecent();if(panel.chartExpired!==!dashboardCurrent(panel.data)||panel.chartValidity!==chartValidity())renderChart();publicationRefresh?.check();},60000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden){renderSummary();renderChart();publicationRefresh?.check();}});
  window.addEventListener('online',()=>publicationRefresh?.check());
  let chartWidth=0;
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(entries=>{const width=Math.round(entries[0].contentRect.width);if(width>0&&width!==chartWidth){chartWidth=width;requestAnimationFrame(renderChart);}}).observe(el('chart-panels'));
  loadDashboard();
}
