'use strict';
/* Shared attribution and comparison view. No provider requests in the browser. */
(function(){
  const labels={precipitation_mm:'Chuva acumulada',temperature_c:'Temperatura máxima',gust_kmh:'Rajada máxima',wind_kmh:'Vento máximo'};
  const short={precipitation_mm:'Chuva por hora',temperature_c:'Temperatura',gust_kmh:'Rajadas'};
  const names={best_match:'Seleção automática',ecmwf_ifs025:'ECMWF IFS',ncep_gfs_global:'NOAA GFS'};
  const n=(v)=>Number.isFinite(v)?v.toLocaleString('pt-BR',{maximumFractionDigits:1}):'—';
  const dt=v=>Number.isFinite(Date.parse(v))?new Intl.DateTimeFormat('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(v)):'não informado';
  function dom(tag,cls,text){const x=document.createElement(tag);if(cls)x.className=cls;if(text!==undefined)x.textContent=text;return x;}
  function validComparison(data){
    return Boolean(data?.schema_version===1&&data.kind==='araquari_comparable_forecasts_not_probability'&&data.location_id==='araquari'&&!data.fixture_mode&&
      Number.isFinite(Date.parse(data.generated_at))&&Number.isFinite(Date.parse(data.valid_until))&&
      Array.isArray(data.records)&&data.records.every(r=>r&&Array.isArray(r.hourly)&&r.hourly.every(p=>p&&Number.isFinite(Date.parse(p.time))))&&
      Array.isArray(data.windows)&&[24,72].every(hours=>data.windows.filter(w=>w?.hours===hours).length===1&&data.windows.some(w=>w?.hours===hours&&Date.parse(w.end_at)>Date.parse(w.start_at)&&
        Array.isArray(w.metrics)&&Object.keys(labels).every(field=>w.metrics.some(m=>m?.variable===field&&Array.isArray(m.members)&&m.members.every(r=>r&&typeof r.id==='string')&&Array.isArray(m.highest_sources)))))&&
      data.cptec&&Array.isArray(data.cptec.days)&&data.cptec.days.every(d=>d&&typeof d.day==='string')&&Array.isArray(data.limitations));
  }
  function current(data){const age=Date.now()-Date.parse(data?.generated_at);return validComparison(data)&&Date.now()<Date.parse(data.valid_until)&&age>=-600000&&age<=10800000;}
  function rangeText(m){return m?.status==='comparable'?`${n(m.minimum)} a ${n(m.maximum)} ${m.unit}`:'Comparação indisponível';}
  function validInmet(data){
    const finite=v=>v===null||(typeof v==='number'&&Number.isFinite(v)&&v>=-50&&v<=65);
    return Boolean(data?.schema_version===1&&data.kind==='inmet_araquari_municipal_forecast_not_observations_or_risk_criteria'&&
      data.location_id==='araquari'&&data.ibge_code==='4201307'&&data.issued_at===null&&data.risk_criteria===false&&data.numeric_rain_or_gust_inferred===false&&
      ['available','cached','stale','unavailable','fixture_mode'].includes(data.status)&&(['unavailable','fixture_mode'].includes(data.status)||(Number.isFinite(Date.parse(data.retrieved_at))&&Number.isFinite(Date.parse(data.valid_until))))&&Array.isArray(data.days)&&data.days.length<=7&&
      data.days.every(d=>d&&/^\d{4}-\d{2}-\d{2}$/.test(d.day)&&finite(d.minimum_c)&&finite(d.maximum_c)&&Array.isArray(d.periods)&&d.periods.length<=3&&
        d.periods.every(p=>p&&['manha','tarde','noite','dia'].includes(p.period)&&typeof p.summary==='string'&&typeof p.wind_intensity_text==='string'&&typeof p.wind_direction==='string'))&&
      Array.isArray(data.daily_comparison)&&data.daily_comparison.length<=7&&data.daily_comparison.every(r=>r&&typeof r.day==='string'&&finite(r.model_minimum_c)&&finite(r.model_maximum_c)));
  }
  function renderInmet(target,data,compact=false){
    const box=dom('section','inmet-municipal-forecast');box.append(dom(compact?'h3':'h4','','INMET · previsão municipal de Araquari'));
    if(!validInmet(data)||!['available','cached'].includes(data.status)||!Number.isFinite(Date.parse(data.retrieved_at))||
       Date.now()-Date.parse(data.retrieved_at)<-600000||Date.now()-Date.parse(data.retrieved_at)>21600000||Date.now()>=Date.parse(data.valid_until)){
      box.append(dom('p','comparison-note','Previsão municipal INMET indisponível ou sem referência atual válida. As demais previsões permanecem independentes.'));target.append(box);return;
    }
    box.append(dom('p','comparison-note',`${data.status==='cached'?'Consulta atual falhou; previsão preservada. ':''}Consulta: ${dt(data.retrieved_at)} · dias civis de Brasília. Emissão completa não informada pela API.`));
    const today=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    const days=data.days.filter(d=>d.day>=today),grid=dom('div','inmet-forecast-days');
    for(const day of days.slice(0,compact?3:7)){
      const card=dom(compact?'article':'details','inmet-forecast-day'),title=`${day.day.split('-').reverse().join('/')} · mín. ${n(day.minimum_c)} °C · máx. ${n(day.maximum_c)} °C`;
      card.append(dom(compact?'strong':'summary','',title));
      const pair=data.daily_comparison.find(r=>r.day===day.day);
      card.append(dom('p','comparison-note',pair?.status==='comparable_context'&&pair.model_hours===24?`Open-Meteo · 24 amostras horárias do mesmo dia: mín. ${n(pair.model_minimum_c)} °C · máx. ${n(pair.model_maximum_c)} °C.`:`Open-Meteo: dia sem 24 amostras horárias válidas (${pair?.model_hours||0}/24 h); sem comparação numérica.`));
      if(compact)card.append(dom('p','',Array.from(new Set(day.periods.map(p=>p.summary).filter(Boolean))).join(' / ')));
      else for(const period of day.periods){
        const label={manha:'Manhã',tarde:'Tarde',noite:'Noite',dia:'Dia'}[period.period];
        card.append(dom('p','',`${label}: ${period.summary||'Condição não informada'}. Vento: ${period.wind_intensity_text||'não informado'}${period.wind_direction?' · '+period.wind_direction:''}.`));
        if(Number.isFinite(period.humidity_min_pct)&&Number.isFinite(period.humidity_max_pct))card.append(dom('p','comparison-note',`Umidade prevista: ${n(period.humidity_min_pct)}% a ${n(period.humidity_max_pct)}%.`));
      }
      grid.append(card);
    }
    if(!days.length)box.append(dom('p','comparison-note','Nenhuma data de previsão atual disponível.'));
    box.append(grid,dom('p','comparison-note','Comparação contextual, sem média nem votação entre fontes. Extremos de amostras horárias podem diferir dos extremos diários previstos. Textos de chuva e vento não são convertidos em mm, probabilidade ou km/h; este produto participa da síntese diária e não define nível institucional.'));
    const link=dom('a','comparison-link','Consultar previsão INMET ↗');link.href='https://previsao.inmet.gov.br/4201307';link.target='_blank';link.rel='noopener noreferrer';box.append(link);target.append(box);
  }
  function renderCompact(target,data){
    if(!target)return;target.replaceChildren();
    if(!current(data)){target.append(dom('p','comparison-note','Comparação entre modelos indisponível ou vencida. Os indicadores principais mantêm sua própria referência.'));renderInmet(target,data?.inmet,true);return;}
    const grid=dom('div','comparison-ranges'),w=data.windows.find(w=>w.hours===24);
    for(const field of ['precipitation_mm','gust_kmh','temperature_c']){
      const m=w?.metrics.find(m=>m.variable===field),box=dom('div','comparison-range');
      box.append(dom('span','',labels[field]+' · 24 h'),dom('strong','',rangeText(m)));
      if(m?.status==='comparable'){const count=m.members.filter(m=>m.value!==null).length;box.append(dom('small','',m.spread===0?`${count} séries completas · valores coincidentes`:`${count} séries completas · maior: ${m.highest_sources.map(id=>names[id]).join(', ')}`));}
      grid.append(box);
    }
    target.append(grid,dom('p','comparison-note','Faixa entre previsões para os mesmos horários, sem média. Não é probabilidade. A seleção automática pode utilizar ECMWF e GFS.'));
    const link=dom('a','comparison-link','Comparar modelos, horários e CPTEC →');link.href='./dados.html#model-comparison';target.append(link);
    renderInmet(target,data.inmet,true);
  }
  function table(target,window){
    const scroll=dom('div','comparison-table-wrap'),t=dom('table','comparison-table'),head=dom('tr');
    for(const title of ['Previsão',...['precipitation_mm','gust_kmh','temperature_c'].map(k=>labels[k])])head.append(dom('th','',title));
    const thead=dom('thead');thead.append(head);t.append(thead);const body=dom('tbody');
    for(const id of ['best_match','ecmwf_ifs025','ncep_gfs_global']){
      const tr=dom('tr');tr.append(dom('th','',names[id]+(id==='best_match'?' · principal provisória':'')));
      for(const field of ['precipitation_mm','gust_kmh','temperature_c']){
        const m=window.metrics.find(m=>m.variable===field),v=m?.members.find(r=>r.id===id);
        const cell=dom('td','',v?.value!==null&&Number.isFinite(v?.value)?`${n(v.value)} ${m.unit}`:`Sem série completa (${v?.valid_hours||0}/${window.hours} h)`);
        if(v?.peak_at)cell.append(dom('small','',dt(v.peak_at)));if(m?.status==='comparable'&&m.spread>0&&m.highest_sources.includes(id)){cell.classList.add('comparison-highest');cell.append(dom('small','','Maior nesta janela'));}tr.append(cell);
      }
      body.append(tr);
    }
    t.append(body);scroll.append(t);target.append(scroll);
  }
  function chart(target,data,field,hours,tooltip,legend){
    target.replaceChildren();legend.replaceChildren();tooltip.hidden=true;
    const w=data.windows.find(w=>w.hours===hours),start=Date.parse(w.start_at),end=Date.parse(w.end_at),rain=field==='precipitation_mm';
    const records=data.records.filter(r=>r.status==='available');
    const series=records.map(r=>({...r,points:r.hourly.filter(p=>{const t=Date.parse(p.time);return rain?t>start&&t<=end:t>=start&&t<end;})}));
    const values=series.flatMap(r=>r.points.map(p=>p[field]).filter(Number.isFinite));
    if(!values.length){target.append(dom('p','comparison-note','Sem valores válidos para comparar neste período.'));return;}
    const dark=document.documentElement.dataset.theme==='dark',colors=dark?['#8bd1ad','#89b9fa','#e9b36e']:['#24714f','#366db4','#a26323'];
    const W=Math.max(300,Math.round(target.clientWidth||700)),H=280,L=48,R=18,T=22,B=48,low=rain||field==='gust_kmh'?0:Math.floor(Math.min(...values)-1),high=Math.max(low+1,Math.ceil(Math.max(...values)*1.08));
    const x=t=>L+(t-start)/(end-start)*(W-L-R),y=v=>H-B-(v-low)/(high-low)*(H-B-T);
    const ns='http://www.w3.org/2000/svg';function svg(tag,attrs,text){const e=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs||{}))e.setAttribute(k,String(v));if(text!==undefined)e.textContent=text;return e;}
    const root=svg('svg',{viewBox:`0 0 ${W} ${H}`,tabindex:0,role:'img','aria-label':`${short[field]} por modelo. Use setas ou toque para consultar.`});
    for(let i=0;i<=4;i++){const v=low+(high-low)*i/4;root.append(svg('line',{x1:L,x2:W-R,y1:y(v),y2:y(v),class:'chart-grid'}),svg('text',{x:L-8,y:y(v)+5,'text-anchor':'end',class:'comparison-axis'},n(v)));}
    const ticks=W<500?2:4;for(let i=0;i<=ticks;i++){const t=start+(end-start)*i/ticks;root.append(svg('text',{x:x(t),y:H-16,'text-anchor':i===0?'start':i===ticks?'end':'middle',class:'comparison-axis'},new Intl.DateTimeFormat('pt-BR',{timeZone:'America/Sao_Paulo',hour:'2-digit',day:'2-digit',month:'2-digit'}).format(new Date(t))));}
    series.forEach((r,index)=>{
      const color=colors[['best_match','ecmwf_ifs025','ncep_gfs_global'].indexOf(r.id)]||colors[0],item=dom('span','');const swatch=dom('i');swatch.style.background=color;item.append(swatch,document.createTextNode(names[r.id]||r.name));legend.append(item);
      if(rain){const slot=(W-L-R)/hours,bw=Math.max(.8,slot*.8/series.length);for(const p of r.points)if(Number.isFinite(p[field])){const bar=svg('rect',{x:x(Date.parse(p.time)-3600000)+slot*.1+bw*index,y:y(p[field]),width:bw,height:Math.max(0,y(0)-y(p[field])),fill:color});bar.append(svg('title',{},`${r.name}: ${n(p[field])} mm · ${dt(new Date(Date.parse(p.time)-3600000).toISOString())} a ${dt(p.time)}`));root.append(bar);}}
      else{let d='',last=null;for(const p of r.points){const t=Date.parse(p.time);if(!Number.isFinite(p[field])){last=null;continue;}d+=(last!==null&&t-last===3600000?'L':'M')+x(t)+','+y(p[field])+' ';last=t;}root.append(svg('path',{d,fill:'none',stroke:color,'stroke-width':2.5,'stroke-dasharray':index===1?'7 4':index===2?'2 4':'none'}));}
    });
    if(typeof ChartInteraction!=='undefined'){
      const times=Array.from({length:hours},(_,i)=>start+(i+(rain?1:0))*3600000);
      ChartInteraction.attach(root,{width:W,left:L,right:R,top:T,bottom:H-B,domain:[start,end],times,tooltip,
        lookup(t){const index=Math.max(0,Math.min(hours-1,rain?Math.ceil((t-start)/3600000)-1:Math.round((t-start)/3600000)));
          const targetTime=times[index],marks=[];
          const parts=series.map(r=>{const p=r.points.find(p=>Date.parse(p.time)===targetTime);if(Number.isFinite(p?.[field]))marks.push({x:rain?x(t):x(targetTime),y:y(p[field]),color:colors[['best_match','ecmwf_ifs025','ncep_gfs_global'].indexOf(r.id)]});
            return `${names[r.id]}: ${n(p?.[field])} ${rain?'mm':field==='temperature_c'?'°C':'km/h'}`;});
          return {text:`${rain?dt(new Date(targetTime-3600000).toISOString())+' a ':''}${dt(new Date(targetTime).toISOString())}\n${parts.join('\n')}`,marks};
        }});target.append(root);return;
    }
    let cursor=0;const total=hours;
    function show(index){cursor=Math.max(0,Math.min(total-1,index));const t=start+(cursor+(rain?1:0))*3600000;const parts=series.map(r=>{const p=r.points.find(p=>Date.parse(p.time)===t);return `${names[r.id]}: ${n(p?.[field])} ${rain?'mm':field==='temperature_c'?'°C':'km/h'}`;});tooltip.textContent=`${rain?dt(new Date(t-3600000).toISOString())+' a ':''}${dt(new Date(t).toISOString())} · ${parts.join(' · ')}`;tooltip.hidden=false;}
    root.addEventListener('pointermove',e=>{const b=root.getBoundingClientRect();show(Math.floor(((e.clientX-b.left)*W/b.width-L)/(W-L-R)*hours));});
    root.addEventListener('click',e=>{const b=root.getBoundingClientRect();show(Math.floor(((e.clientX-b.left)*W/b.width-L)/(W-L-R)*hours));});
    root.addEventListener('keydown',e=>{if(['ArrowRight','ArrowLeft','Home','End'].includes(e.key)){e.preventDefault();show(e.key==='Home'?0:e.key==='End'?total-1:cursor+(e.key==='ArrowRight'?1:-1));}});target.append(root);
  }
  function renderDetailed(target,data){
    if(!target)return;if(target._comparisonResize)target._comparisonResize.disconnect();if(target._comparisonTheme)document.removeEventListener('observatorythemechange',target._comparisonTheme);target.replaceChildren();target.append(dom('h3','','Previsões em comparação · Araquari'));
    if(!current(data)){target.append(dom('p','comparison-note','Comparação indisponível ou vencida. Não se infere concordância ou normalidade.'));renderInmet(target,data?.inmet);return;}
    target.append(dom('p','','Open-Meteo é o serviço de acesso; ECMWF e NOAA produzem os modelos identificados. A seleção automática permanece principal pela cobertura horária, sem superioridade local demonstrada.'));
    const controls=dom('div','model-chart-controls'),vlabel=dom('label','','Variável'),variable=dom('select'),hlabel=dom('label','','Período'),horizon=dom('select');
    variable.setAttribute('aria-label','Variável da comparação');horizon.setAttribute('aria-label','Período da comparação');
    for(const [key,text]of Object.entries(short)){const op=dom('option','',text);op.value=key;variable.append(op);}
    for(const h of [24,72]){const op=dom('option','',h+' horas');op.value=h;horizon.append(op);}vlabel.append(variable);hlabel.append(horizon);controls.append(vlabel,hlabel);
    const selected=target._comparisonSelection;
    if(selected&&Object.hasOwn(short,selected.variable))variable.value=selected.variable;
    if(selected&&[24,72].includes(selected.hours))horizon.value=String(selected.hours);
    const period=dom('p','comparison-note'),plot=dom('div','model-comparison-plot'),tooltip=dom('p','comparison-tooltip'),legend=dom('div','comparison-legend'),tables=dom('div');tooltip.hidden=true;tooltip.setAttribute('aria-live','polite');
    target.append(controls,period,plot,legend,tooltip,tables);
    function update(){if(!current(data)){renderDetailed(target,data);return;}const hours=Number(horizon.value),w=data.windows.find(w=>w.hours===hours);target._comparisonSelection={variable:variable.value,hours};period.textContent=`${dt(w.start_at)} a ${dt(w.end_at)} · Brasília. Chuva: barras por hora e modelo; demais variáveis: linhas. Lacunas não são zero.`;chart(plot,data,variable.value,hours,tooltip,legend);tables.replaceChildren();table(tables,w);}
    variable.addEventListener('change',update);horizon.addEventListener('change',update);target._comparisonTheme=update;document.addEventListener('observatorythemechange',update);update();if(typeof ResizeObserver!=='undefined'){let lastWidth=0;target._comparisonResize=new ResizeObserver(entries=>{const width=Math.round(entries[0].contentRect.width);if(width>0&&width!==lastWidth){lastWidth=width;requestAnimationFrame(update);}});target._comparisonResize.observe(plot);}
    renderInmet(target,data.inmet);
    target.append(dom('h4','','CPTEC/INPE · contexto diário separado'));
    const cp=data.cptec;target.append(dom('p','comparison-note',`Localidade: ${cp.locality||'não identificada'} · atualização informada: ${cp.updated_day||'não informada'} · consulta: ${dt(cp.checked_at)}. Períodos diários e localização ainda não conciliados; fora das faixas numéricas.`));
    if(cp.status==='available'){const list=dom('div','cptec-comparison-days');for(const day of cp.days){list.append(dom('p','',`${day.day}: mínima ${n(day.minimum_c)} °C · máxima ${n(day.maximum_c)} °C`));}target.append(list);}else target.append(dom('p','','Previsão CPTEC sem referência atual válida.'));
    const link=dom('a','','Ver previsão CPTEC completa e condição do tempo ↓');link.href='#cptec-title';target.append(link);
    const methods=dom('details','comparison-methods');methods.append(dom('summary','','Fontes, grades e limites da comparação'));
    for(const r of data.records)methods.append(dom('p','',`${r.name} · ${r.status==='available'?'coletada em '+dt(r.collected_at):'indisponível'+(r.diagnostic?' ('+r.diagnostic+')':'')} · grade: ${Number.isFinite(r.grid_point?.latitude)?n(r.grid_point.latitude)+', '+n(r.grid_point.longitude):'não informada'}. Rodada: não informada.`));
    for(const text of data.limitations)methods.append(dom('p','',text));
    methods.append(dom('p','','Arquivo por coleta: sete dias, até 64 publicações, alvos horários futuros de até 72 h. Ainda sem cálculo de erro, pesos ou probabilidades.'));
    const archive=dom('a','','Abrir arquivo de previsões por coleta (JSON) ↗');archive.href='./data/model_forecast_history.json';methods.append(archive);target.append(methods);
  }
  if(typeof module!=='undefined')module.exports={validComparison,current,validInmet};
  if(typeof window==='undefined'||typeof document==='undefined')return;
  window.ForecastComparison={renderCompact,renderDetailed};
  const detailed=document.getElementById('model-comparison');
  if(detailed){
    let feed=null,loading=false;
    async function read(id){
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
      try{const r=await fetch('./data/'+id+'.json',{cache:'no-store',signal:controller.signal});if(!r.ok)throw Error('HTTP '+r.status);return await r.json();}
      finally{clearTimeout(timer);}
    }
    async function load(){
      if(loading)return;loading=true;
      try{
        let loaded=null;
        for(let attempt=0;attempt<2;attempt++){
          const [data,latest]=await Promise.all([read('forecast_comparison'),read('latest')]);
          if(latest.fixture_mode||latest.schema_version!==1||!validComparison(data)||Date.parse(data.generated_at)>Date.now()+600000)throw Error('Invalid publication');
          if(latest.generated_at===data.generated_at){loaded=data;break;}
        }
        if(!loaded)throw Error('Publication mismatch');
        if(feed&&Date.parse(loaded.generated_at)<Date.parse(feed.generated_at))return;
        feed=loaded;renderDetailed(detailed,feed);
      }catch{
        renderDetailed(detailed,feed);
        if(current(feed))detailed.append(dom('p','comparison-note','Falha ao buscar nova comparação; última leitura preservada com seus horários.'));
      }finally{loading=false;}
    }
    const refresh=typeof PublicationRefresh!=='undefined'?PublicationRefresh.create({
      getVersion:()=>feed?.generated_at,readLatest:()=>read('latest'),reload:load,isVisible:()=>!document.hidden}):null;
    load();
    setInterval(()=>{if(feed&&!current(feed))renderDetailed(detailed,null);refresh?.check();},60000);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh?.check();});
    window.addEventListener('online',()=>refresh?.check());
  }
})();
