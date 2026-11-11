'use strict';
/* Same deterministic evidence presentation on home and detailed pages. */
(function(){
  const names={rain:'Chuva',wind:'Vento',temperature:'Temperatura'};
  const fieldNames={rain_1h_mm:'chuva em 1 h',rain_24h_mm:'chuva em 24 h',wind_kmh:'vento',gust_kmh:'rajada'};
  const number=v=>Number.isFinite(v)?v.toLocaleString('pt-BR',{maximumFractionDigits:1}):'—';
  const date=v=>Number.isFinite(Date.parse(v))?new Intl.DateTimeFormat('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(v)):'horário não informado';
  const live=(r,now)=>Number.isFinite(Date.parse(r?.valid_until))&&now<Date.parse(r.valid_until);
  function valid(data){return data?.schema_version===1&&data.kind==='araquari_multisource_weather_not_institutional_level'&&data.location_id==='araquari'&&Array.isArray(data.observations)&&Array.isArray(data.signals)&&Array.isArray(data.notices)&&Array.isArray(data.station_registry)&&data.formal_level===null;}
  function currentStats(data,field,now=Date.now()){
    const rows=(data?.statistics?.[field]?.members||[]).filter(r=>live(r,now));
    if(!rows.length)return null;
    const values=rows.map(r=>r.value).sort((a,b)=>a-b),mid=Math.floor(values.length/2);
    return {members:rows,count:rows.length,mean:values.reduce((a,b)=>a+b,0)/values.length,median:values.length%2?values[mid]:(values[mid-1]+values[mid])/2,max:values.at(-1),min:values[0],unit:rows[0].unit};
  }
  function presentation(data,now=Date.now()){
    if(!valid(data))return null;
    const signals=data.signals.filter(r=>live(r,now)&&r.band>0).sort((a,b)=>b.band-a.band);
    const notices=data.notices.filter(r=>live(r,now));
    const normative=data.normative_assessment;
    if(live(normative,now)&&['laranja','vermelho'].includes(normative.suggested_level))return {color:normative.suggested_level,active:normative.suggested_level,title:normative.title,kind:'Correspondência normativa · conferir',reason:normative.reason};
    if(notices.length){
      const sources=[...new Set(notices.map(r=>r.source))].join(' e ');
      return {color:'amarelo',active:null,title:'Avisos meteorológicos para Araquari',kind:'Situação meteorológica',reason:`${sources}: ${notices.map(r=>`${r.title} · ${r.severity} · ${date(r.start_at)} a ${date(r.end_at)}`).join('; ')}. A correspondência com a norma está nos detalhes.`};
    }
    if(signals.length){const s=signals[0];return {color:'amarelo',active:null,title:'Atenção a '+(s.variable.startsWith('rain')?'chuva':'vento'),kind:'Referência técnica · acompanhamento',reason:`${s.nature==='observation'?'Medição':'Previsão'} de ${fieldNames[s.variable]||s.variable}: ${number(s.value)} ${s.unit} · ${s.name||s.source} · ${date(s.end_at)}. ${s.nature==='observation'?'Os extremos são preservados individualmente.':'Previsão não confirma ocorrência.'}`};}
    const observation=data.observations.some(r=>live(r,now));
    const forecast=Object.values(data.selected_forecast?.sources_by_variable||{}).some(r=>live(r,now));
    if(observation||forecast)return {color:'neutral',active:null,title:'Acompanhamento das condições locais',kind:observation&&forecast?'Observações e previsões':'Cobertura parcial',reason:'Nenhuma referência técnica de atenção nas evidências ainda válidas. Confira abaixo chuva, vento, temperatura e a cobertura disponível; isso não constitui declaração de normalidade institucional.'};
    const daily=data.forecast_context?.days?.some(r=>live(r,now));
    return {color:'neutral',active:null,title:daily?'Previsão diária disponível':'Sem referências atuais suficientes',kind:'Cobertura parcial',reason:daily?'A previsão diária continua disponível. Medições e detalhamento horário não têm referências atuais suficientes.':'As fontes disponíveis não sustentam uma leitura atual. Consulte os horários e os canais oficiais.'};
  }
  function element(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;}
  function render(target,data,detailed=false){
    if(!target)return;target.replaceChildren();
    if(!valid(data)){target.append(element('p','','Síntese local indisponível nesta publicação.'));return;}
    const now=Date.now();target.append(element(detailed?'h2':'h3','','Condições em Araquari'));
    const grid=element('div','synthesis-grid');
    for(const [name,fields] of Object.entries({rain:['rain_24h_mm','rain_1h_mm'],wind:['gust_kmh','wind_kmh'],temperature:['temperature_c']})){
      const box=element('article','synthesis-item');box.append(element('h4','',names[name]));
      const field=fields.find(f=>currentStats(data,f,now)),stat=field?currentStats(data,field,now):null;
      if(stat){box.append(element('p','',`${fieldNames[field]||'Temperatura'}: ${number(stat.median)} ${stat.unit}${stat.count>1?' · mediana':''}`),element('p','small',`${stat.count} ${stat.count>1?'estações':'estação'} · maior: ${number(stat.max)} ${stat.unit}`));}
      else box.append(element('p','small','Sem medição local comparável e atual.'));
      const forecastFields={rain:['precipitation_mm'],wind:['wind_kmh','gust_kmh'],temperature:['temperature_c']}[name];
      const products=[...new Set(forecastFields.map(f=>data.selected_forecast?.sources_by_variable?.[f]).filter(r=>live(r,now)).map(r=>r.name+(r.fallback?' · substituição ativa':'')))];
      box.append(element('p','small',products.length?'Previsão horária: '+products.join('; '):'Sem previsão horária completa para esta variável.'));
      if(detailed&&stat){box.append(element('p','small',`Média: ${number(stat.mean)} ${stat.unit} · intervalo: ${number(stat.min)}–${number(stat.max)} ${stat.unit}. Pesos iguais por estação.`));for(const r of stat.members)box.append(element('p','small',`${r.name}: ${number(r.value)} ${r.unit} · ${date(r.end_at)}${r.method.includes('approximation')?' · intervalo aproximado em 5 min':''}`));}
      grid.append(box);
    }
    target.append(grid);
    const parts=Object.fromEntries(new Intl.DateTimeFormat('en',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(now)).map(p=>[p.type,p.value]));
    const today=`${parts.year}-${parts.month}-${parts.day}`;
    const days=(data.forecast_context?.days||[]).filter(r=>live(r,now)&&r.day>=today);
    const inmet=days.find(r=>r.source==='INMET');
    if(inmet){
      const periods={manha:'manhã',tarde:'tarde',noite:'noite',dia:'dia'};
      target.append(element('p','synthesis-daily',`INMET · ${inmet.day.split('-').reverse().join('/')} · mín. ${number(inmet.minimum_c)} °C / máx. ${number(inmet.maximum_c)} °C${inmet.cached?' · consulta anterior':''}. `+(inmet.periods||[]).map(p=>`${periods[p.period]||p.period}: ${p.summary}${p.wind_intensity_text?'; vento '+p.wind_intensity_text:''}`).join(' · ')));
    }
    const cp=days.find(r=>r.source==='CPTEC/INPE');
    if(cp)target.append(element('p','small',`CPTEC/INPE · ${cp.day.split('-').reverse().join('/')} · ${cp.locality||'localidade de referência'}: ${number(cp.minimum_c)}–${number(cp.maximum_c)} °C. Períodos ainda não conciliados com os produtos horários.`));
    const details=element('details','synthesis-method');details.append(element('summary','','Fontes, cobertura e critérios'));
    details.append(element('p','small','Rainha, Porto Grande, Centro e IFC Araquari têm igual importância. Cada variável participa quando há leitura compatível e válida. Chuva diária e acumulado móvel de 24 h permanecem separados.'));
    details.append(element('p','small','Epagri/Ciram e INMET têm igual relevância meteorológica. A norma institucional cita Epagri/Ciram; avisos INMET não são convertidos em níveis institucionais.'));
    details.append(element('p','small','As previsões contribuem pelos períodos e variáveis disponíveis, sem média de textos ou votação. ECMWF, GFS e seleção automática compartilham o provedor Open-Meteo.'));
    for(const r of data.rejected||[])details.append(element('p','small',`${data.station_registry.find(s=>s.id===r.station)?.name||r.station} · ${r.variable}: ${r.reason==='simultaneous_temperature_humidity_zero'?'temperatura e umidade simultaneamente zeradas; possível falha do sensor':'leitura ausente, inválida ou vencida'}.`));
    if(detailed){
      for(const r of data.regional_observations||[])if(live(r,now))details.append(element('p','small',`Contexto regional: ${r.name} · ${r.distance_km} km · ${number(r.value)} ${r.unit} · ${date(r.end_at)}. Não participa da média das quatro estações locais.`));
      for(const r of data.unit_inference||[])details.append(element('p','small',`Sensor ${r.sensor_id}: ${r.suggested_unit?'unidade provável '+r.suggested_unit:'unidade ainda ambígua'} · ${r.sample_count} leituras, ${r.nonzero_count} não nulas. Inferência não habilitada para limiares.`));
      const n=data.normative_assessment;details.append(element('p','small',`Correspondência normativa registrada em ${date(data.generated_at)}: ${n?.title||'a verificar'}; ${n?.reason||''} Não é decisão institucional.${Date.parse(n?.valid_until)<=now?' Referência normativa vencida.':''}`));
    }
    target.append(details);
  }
  window.WeatherSynthesis={valid,currentStats,presentation,render};
  const target=document.getElementById('weather-synthesis-detail');
  if(target){let data=null,version=null,loading=false;
    async function load(){if(loading)return;loading=true;try{
      const latest=await fetch('./data/latest.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('latest');return r.json();});
      const feed=await fetch('./data/dashboard.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('dashboard');return r.json();});
      if(feed.fixture_mode||feed.generated_at!==latest.generated_at||feed.publication_at!==latest.generated_at||!valid(feed.synthesis))throw Error('publication');
      if(version&&Date.parse(feed.generated_at)<Date.parse(version))return;
      version=feed.generated_at;data=feed.synthesis;render(target,data,true);
    }catch{if(!data)target.replaceChildren(element('p','','Não foi possível consultar a síntese local. Nova tentativa automática.'));else render(target,data,true);}finally{loading=false;}}
    load();setInterval(()=>{if(!document.hidden)load();},60000);window.addEventListener('online',load);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load();});document.getElementById('reload')?.addEventListener('click',load);
  }
})();
