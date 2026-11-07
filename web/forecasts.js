'use strict';
/* Shared attribution and comparison view. No provider requests in the browser. */
(function(){
  const labels={precipitation_mm:'Chuva acumulada',temperature_c:'Temperatura máxima',gust_kmh:'Rajada máxima',wind_kmh:'Vento máximo'};
  const short={precipitation_mm:'Chuva por hora',temperature_c:'Temperatura',gust_kmh:'Rajadas'};
  const names={best_match:'Seleção automática',ecmwf_ifs025:'ECMWF IFS',ncep_gfs_global:'NOAA GFS'};
  const n=(v)=>Number.isFinite(v)?v.toLocaleString('pt-BR',{maximumFractionDigits:1}):'—';
  const dt=v=>Number.isFinite(Date.parse(v))?new Intl.DateTimeFormat('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(v)):'não informado';
  function dom(tag,cls,text){const x=document.createElement(tag);if(cls)x.className=cls;if(text!==undefined)x.textContent=text;return x;}
  function current(data){return data?.schema_version===1&&data?.kind==='araquari_comparable_forecasts_not_probability'&&data.location_id==='araquari'&&!data.fixture_mode&&Date.now()<Date.parse(data.valid_until)&&Date.now()-Date.parse(data.generated_at)>=-600000;}
  function rangeText(m){return m?.status==='comparable'?`${n(m.minimum)} a ${n(m.maximum)} ${m.unit}`:'Comparação indisponível';}
  function renderCompact(target,data){
    if(!target)return;target.replaceChildren();
    if(!current(data)){target.append(dom('p','comparison-note','Comparação entre modelos indisponível ou vencida. Os indicadores principais mantêm sua própria referência.'));return;}
    const grid=dom('div','comparison-ranges'),w=data.windows.find(w=>w.hours===24);
    for(const field of ['precipitation_mm','gust_kmh','temperature_c']){
      const m=w?.metrics.find(m=>m.variable===field),box=dom('div','comparison-range');
      box.append(dom('span','',labels[field]+' · 24 h'),dom('strong','',rangeText(m)));
      if(m?.status==='comparable')box.append(dom('small','',`${m.members.filter(m=>m.value!==null).length} previsões com série completa`));
      grid.append(box);
    }
    target.append(grid,dom('p','comparison-note','Faixa entre previsões para os mesmos horários, sem média. Não é probabilidade. A seleção automática pode utilizar ECMWF e GFS.'));
    const link=dom('a','comparison-link','Comparar modelos, horários e CPTEC →');link.href='./dados.html#model-comparison';target.append(link);
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
        if(v?.peak_at)cell.append(dom('small','',dt(v.peak_at)));tr.append(cell);
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
    let cursor=0;const total=hours;
    function show(index){cursor=Math.max(0,Math.min(total-1,index));const t=start+(cursor+(rain?1:0))*3600000;const parts=series.map(r=>{const p=r.points.find(p=>Date.parse(p.time)===t);return `${names[r.id]}: ${n(p?.[field])} ${rain?'mm':field==='temperature_c'?'°C':'km/h'}`;});tooltip.textContent=`${rain?dt(new Date(t-3600000).toISOString())+' a ':''}${dt(new Date(t).toISOString())} · ${parts.join(' · ')}`;tooltip.hidden=false;}
    root.addEventListener('pointermove',e=>{const b=root.getBoundingClientRect();show(Math.floor(((e.clientX-b.left)*W/b.width-L)/(W-L-R)*hours));});
    root.addEventListener('click',e=>{const b=root.getBoundingClientRect();show(Math.floor(((e.clientX-b.left)*W/b.width-L)/(W-L-R)*hours));});
    root.addEventListener('keydown',e=>{if(['ArrowRight','ArrowLeft','Home','End'].includes(e.key)){e.preventDefault();show(e.key==='Home'?0:e.key==='End'?total-1:cursor+(e.key==='ArrowRight'?1:-1));}});target.append(root);
  }
  function renderDetailed(target,data){
    if(!target)return;target.replaceChildren();target.append(dom('h3','','Previsões em comparação · Araquari'));
    if(!current(data)){target.append(dom('p','comparison-note','Comparação indisponível ou vencida. Não se infere concordância ou normalidade.'));return;}
    target.append(dom('p','','Open-Meteo é o serviço de acesso; ECMWF e NOAA produzem os modelos identificados. A seleção automática permanece principal pela cobertura horária, sem superioridade local demonstrada.'));
    const controls=dom('div','model-chart-controls'),vlabel=dom('label','','Variável'),variable=dom('select'),hlabel=dom('label','','Período'),horizon=dom('select');
    variable.setAttribute('aria-label','Variável da comparação');horizon.setAttribute('aria-label','Período da comparação');
    for(const [key,text]of Object.entries(short)){const op=dom('option','',text);op.value=key;variable.append(op);}
    for(const h of [24,72]){const op=dom('option','',h+' horas');op.value=h;horizon.append(op);}vlabel.append(variable);hlabel.append(horizon);controls.append(vlabel,hlabel);
    const period=dom('p','comparison-note'),plot=dom('div','model-comparison-plot'),tooltip=dom('p','comparison-tooltip'),legend=dom('div','comparison-legend'),tables=dom('div');tooltip.hidden=true;tooltip.setAttribute('aria-live','polite');
    target.append(controls,period,plot,legend,tooltip,tables);
    function update(){if(!current(data)){renderDetailed(target,data);return;}const hours=Number(horizon.value),w=data.windows.find(w=>w.hours===hours);period.textContent=`${dt(w.start_at)} a ${dt(w.end_at)} · Brasília. Chuva: barras por hora e modelo; demais variáveis: linhas. Lacunas não são zero.`;chart(plot,data,variable.value,hours,tooltip,legend);tables.replaceChildren();table(tables,w);}
    variable.addEventListener('change',update);horizon.addEventListener('change',update);document.addEventListener('observatorythemechange',update);update();
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
  window.ForecastComparison={renderCompact,renderDetailed};
  const detailed=document.getElementById('model-comparison');
  if(detailed){let feed=null;async function load(){try{const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);let responses;try{responses=await Promise.all(['forecast_comparison','latest'].map(id=>fetch('./data/'+id+'.json',{cache:'no-store',signal:controller.signal}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();})));}finally{clearTimeout(timer);}const [data,latest]=responses;if(latest.fixture_mode||latest.generated_at!==data.generated_at)throw Error('Publication mismatch');feed=data;renderDetailed(detailed,feed);}catch{renderDetailed(detailed,null);}}load();setInterval(()=>{if(feed&&!current(feed)){feed=null;renderDetailed(detailed,null);}},60000);}
})();
