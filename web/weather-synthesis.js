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
  const riskNames={verde:'Normalidade',azul:'Preparação',amarelo:'Atenção',laranja:'Alerta',vermelho:'Alerta máximo',roxo:'Calamidade'};
  function riskLevel(product,now=Date.now()){
    const neutral={color:'neutral',active:null,title:'Sem classificação',kind:'Dados parciais',reason:'Faltam referências atuais para definir o nível.'};
    if(!product||!['araquari-risk-v2','araquari-risk-v3'].includes(product.method_version)||product.kind!=='consultative_risk_level_not_official_decision'||product.official_level!==null||!Array.isArray(product.candidates))return neutral;
    if(Date.parse(product.generated_at)>now+600000)return neutral;
    const order=Object.keys(riskNames);
    const candidates=product.candidates.filter(c=>c&&order.includes(c.level)&&c.level!=='roxo'&&typeof c.reason==='string'&&Array.isArray(c.evidence)&&c.evidence.length&&live(c,now)).sort((a,b)=>order.indexOf(b.level)-order.indexOf(a.level));
    const c=candidates[0];return c?{color:c.level,active:c.level,title:riskNames[c.level],kind:'Consultivo',reason:c.reason}:neutral;
  }
  function presentation(data,now=Date.now()){
    return data?.risk_classification?riskLevel(data.risk_classification,now):null;
  }
  function element(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;}
  function render(target,data,detailed=false){
    if(!target)return;target.replaceChildren();
    if(!valid(data)){target.append(element('p','','Síntese local indisponível nesta publicação.'));return;}
    const now=Date.now();
    if(detailed&&data.risk_classification){
      const risk=riskLevel(data.risk_classification,now),box=element('section','risk-analysis');
      box.append(element('h2','','Classificação de risco'),element('h3','',risk.title),element('p','',risk.reason),element('p','small','Nível consultivo com referência às categorias da PN 13/2026. A decisão institucional permanece com a autoridade competente.'));
      box.append(element('h4','','Evidências utilizadas'));
      const candidates=data.risk_classification.candidates||[];
      for(const c of candidates)box.append(element('p','small',`${riskNames[c.level]} · ${c.reason} · válida até ${date(c.valid_until)}${live(c,now)?'':' · vencida'}.`));
      box.append(element('h4','','Cobertura necessária para normalidade'));
      for(const r of data.risk_classification.requirements||[])box.append(element('p','small',`${r.label}: ${r.available&&live(r,now)?'disponível':'ausente ou vencida'}${r.resolution==='qualitative_daily_or_period'?' · INMET diário/por turno':''}${r.evidence?.some(e=>e.retained_previous)?' · consulta anterior válida':''}${r.valid_until?' · até '+date(r.valid_until):''}.`));
      box.append(element('h4','','Critérios por nível'));
      for(const level of data.risk_classification.levels||[])box.append(element('p','small',`${level.name}: ${level.criterion}`));
      const link=element('a','','Critérios completos e limites do algoritmo ↗');link.href='https://github.com/guimig/criseclimatica/blob/main/docs/CLASSIFICACAO_CONSULTIVA.md';link.target='_blank';link.rel='noopener noreferrer';box.append(link);target.append(box);
    }
    target.append(element(detailed?'h2':'h3','','Observações e previsões'));
    const grid=element('div','synthesis-grid');
    for(const [name,fields] of Object.entries({rain:['rain_24h_mm','rain_1h_mm'],wind:['gust_kmh','wind_kmh'],temperature:['temperature_c']})){
      const box=element('article','synthesis-item');box.append(element('h4','',names[name]));
      const field=fields.find(f=>currentStats(data,f,now)),stat=field?currentStats(data,field,now):null;
      if(stat){box.append(element('p','',`${detailed||name==='rain'?(fieldNames[field]||'Temperatura')+': ':''}${number(stat.median)} ${stat.unit}${stat.count>1?' · mediana':''}`),element('p','small',`${stat.count} ${stat.count>1?'estações':'estação'} · maior: ${number(stat.max)} ${stat.unit}`));}
      else box.append(element('p','small','Sem medição local comparável e atual.'));
      const forecastFields={rain:['precipitation_mm'],wind:['wind_kmh','gust_kmh'],temperature:['temperature_c']}[name];
      const products=[...new Set(forecastFields.map(f=>data.selected_forecast?.sources_by_variable?.[f]).filter(r=>live(r,now)).map(r=>r.name+(r.retained_previous?' · consulta anterior válida':r.fallback?' · substituição ativa':'')))];
      if(detailed||!products.length)box.append(element('p','small',products.length?'Previsão horária: '+products.join('; '):'Sem previsão horária completa para esta variável.'));
      if(detailed&&stat){box.append(element('p','small',`Média: ${number(stat.mean)} ${stat.unit} · intervalo: ${number(stat.min)}–${number(stat.max)} ${stat.unit}. Pesos iguais por estação.`));for(const r of stat.members)box.append(element('p','small',`${r.name}: ${number(r.value)} ${r.unit} · ${date(r.end_at)}${r.method.includes('approximation')?' · intervalo aproximado em 5 min':''}`));}
      if(detailed)for(const other of fields.filter(f=>f!==field)){
        const extra=currentStats(data,other,now);if(!extra)continue;
        box.append(element('p','small',`${fieldNames[other]||other}: ${number(extra.median)} ${extra.unit} · ${extra.count} ${extra.count>1?'estações':'estação'} · média ${number(extra.mean)} ${extra.unit} · maior ${number(extra.max)} ${extra.unit}.`));
        for(const r of extra.members)box.append(element('p','small',`${r.name}: ${number(r.value)} ${r.unit} · ${date(r.end_at)}${r.method.includes('approximation')?' · intervalo aproximado em 5 min':''}`));
      }
      grid.append(box);
    }
    target.append(grid);
    const parts=Object.fromEntries(new Intl.DateTimeFormat('en',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(now)).map(p=>[p.type,p.value]));
    const today=`${parts.year}-${parts.month}-${parts.day}`;
    const days=(data.forecast_context?.days||[]).filter(r=>live(r,now)&&r.day>=today);
    const inmet=days.find(r=>r.source==='INMET');
    if(inmet){
      const periods={manha:'manhã',tarde:'tarde',noite:'noite',dia:'dia'};
      const grouped=new Map();for(const p of inmet.periods||[]){const text=`${p.summary}${p.wind_intensity_text?'; vento '+p.wind_intensity_text:''}`;if(!grouped.has(text))grouped.set(text,[]);grouped.get(text).push(periods[p.period]||p.period);}
      const descriptions=[...grouped].map(([text,labels])=>labels.join(', ')+': '+text).join(' · ');
      target.append(element('p','synthesis-daily',`INMET · ${inmet.day.split('-').reverse().join('/')} · mín. ${number(inmet.minimum_c)} °C / máx. ${number(inmet.maximum_c)} °C${inmet.cached?' · consulta anterior':''}. `+descriptions));
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

    }
    target.append(details);
    if(detailed&&data.alert_history?.episodes?.length){
      const history=element('details','synthesis-method');history.append(element('summary','','Histórico de níveis'),element('p','small','Registros por coleta; os intervalos não representam duração contínua de um evento.'));
      for(const row of data.alert_history.episodes.slice(0,12))history.append(element('p','small',`${row.label||riskNames[row.state]||'Sem classificação'} · ${date(row.first_seen_at)} a ${date(row.last_seen_at)} · ${row.samples} coletas.`));
      target.append(history);
    }
  }
  window.WeatherSynthesis={valid,currentStats,presentation,riskLevel,render};
  const target=document.getElementById('weather-synthesis-detail');
  if(target){let data=null,version=null,loading=false;
    async function load(){if(loading)return;loading=true;try{
      const latest=await fetch('./data/latest.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('latest');return r.json();});
      const feed=await fetch('./data/dashboard.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('dashboard');return r.json();});
      if(feed.fixture_mode||feed.generated_at!==latest.generated_at||feed.publication_at!==latest.generated_at||!valid(feed.synthesis))throw Error('publication');
      if(version&&Date.parse(feed.generated_at)<Date.parse(version))return;
      version=feed.generated_at;data={...feed.synthesis,alert_history:feed.alert_history};render(target,data,true);
    }catch{if(!data)target.replaceChildren(element('p','','Não foi possível consultar a síntese local. Nova tentativa automática.'));else render(target,data,true);}finally{loading=false;}}
    load();setInterval(()=>{if(!document.hidden)load();},60000);window.addEventListener('online',load);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load();});document.getElementById('reload')?.addEventListener('click',load);
  }
})();
