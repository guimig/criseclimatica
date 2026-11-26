'use strict';
/* Presentation only. Raw samples, source validity and risk rules stay with their owners. */
(function(){
  const HOUR=3600000,TZ='America/Sao_Paulo';
  const light=['#267246','#316d9e','#73548c','#246e70','#755d3e','#4b657c'];
  const dark=['#88d5a3','#92bff1','#cba9ed','#89d0d0','#d9c29c','#a8c0d4'];
  const number=v=>Number.isFinite(v)?v.toLocaleString('pt-BR',{maximumFractionDigits:1}):'—';
  const date=v=>Number.isFinite(Date.parse(v))?new Intl.DateTimeFormat('pt-BR',{timeZone:TZ,day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(v)):'não informado';
  function identity(key,field='',isDark=false){
    let hash=0;for(const c of String(key))hash=(Math.imul(hash,31)+c.charCodeAt(0))>>>0;
    const models={best_match:0,ecmwf_ifs025:1,ncep_gfs_global:2,precipitation_mm:1,temperature_c:1,wind_kmh:1,gust_kmh:1};
    const index=models[key]??hash%light.length;
    const modelDash=key==='ecmwf_ifs025'?'7 4':key==='ncep_gfs_global'?'2 4':'';
    return {color:(isDark?dark:light)[index],shape:['circle','square','triangle'][Object.hasOwn(models,key)?index%3:hash%3],
      dash:field==='gust_kmh'?(modelDash?modelDash+' 2 4':'6 4'):modelDash};
  }
  function scale(values,temperature=false){
    const valid=values.filter(Number.isFinite),minimum=valid.length?Math.min(...valid):0,maximum=valid.length?Math.max(...valid):0;
    const min=temperature?minimum-1:0,range=Math.max(1,maximum-min),power=10**Math.floor(Math.log10(range/5));
    const step=([1,2,2.5,5,10].find(v=>v>=range/5/power)||10)*power;
    return {low:Math.floor(min/step)*step,high:Math.max(Math.ceil(maximum/step)*step,Math.floor(min/step)*step+step),step};
  }
  function resolution(hours,width,count=1){
    const desired=hours>72?6:hours>24?3:1;
    return [1,3,6,12,24].find(h=>h>=desired&&(width*h/hours/Math.max(1,count)>=4||h===24))||24;
  }
  function aggregateRain(points,start,hours,block){
    const byTime=new Map();
    for(const p of points){
      const t=Date.parse(p.time),value=Number.isFinite(p.value)&&p.value>=0?p.value:null;
      if(!Number.isFinite(t))continue;
      if(byTime.has(t)&&byTime.get(t)!==value)byTime.set(t,null);else if(!byTime.has(t))byTime.set(t,value);
    }
    const bins=[];
    for(let offset=0;offset<hours;offset+=block){
      const expected=Math.min(block,hours-offset);let valid=0,total=0;
      for(let h=1;h<=expected;h++){const v=byTime.get(start+(offset+h)*HOUR);if(Number.isFinite(v)){valid++;total+=v;}}
      bins.push({start_at:new Date(start+offset*HOUR).toISOString(),time:new Date(start+(offset+expected)*HOUR).toISOString(),
        value:valid===expected?total:null,partialValue:valid?total:null,validHours:valid,expectedHours:expected,
        status:valid===expected?'complete':valid?'partial':'missing'});
    }
    return bins;
  }
  // Keep endpoints and all bucket extrema. Breaks are processed before simplification.
  function simplify(points,start,end,width){
    if(points.length<=width*2)return points;
    const buckets=new Map();
    points.forEach((p,i)=>{const bucket=Math.floor((Date.parse(p.time)-start)/(end-start)*width);if(!buckets.has(bucket))buckets.set(bucket,[]);buckets.get(bucket).push(i);});
    const keep=new Set([0,points.length-1]);
    for(const indices of buckets.values()){
      keep.add(indices[0]);keep.add(indices.at(-1));
      keep.add(indices.reduce((a,b)=>points[a].value<=points[b].value?a:b));
      keep.add(indices.reduce((a,b)=>points[a].value>=points[b].value?a:b));
    }
    return [...keep].sort((a,b)=>a-b).map(i=>points[i]);
  }
  function segments(points,gapMs=HOUR){
    const runs=[];let run=[],last=null;
    for(const p of points){const t=Date.parse(p.time);if(!Number.isFinite(p.value)||!Number.isFinite(t)){if(run.length)runs.push(run);run=[];last=null;continue;}
      if(last!==null&&t-last>gapMs){if(run.length)runs.push(run);run=[];}run.push(p);last=t;
    }
    if(run.length)runs.push(run);return runs;
  }
  function ticks(start,end,width){
    const target=Math.max(2,Math.min(5,Math.floor(width/100))),step=([1,3,6,12,24,48,72,120].find(h=>h*HOUR>=(end-start)/target)||240)*HOUR;
    const result=[start];
    // Brasília is UTC-3. Align day and hour boundaries in the displayed timezone.
    const offset=3*HOUR;
    for(let t=Math.ceil((start-offset)/step)*step+offset;t<end;t+=step)if(t>start&&(t-start)/(end-start)*width>=55&&(end-t)/(end-start)*width>=55)result.push(t);
    result.push(end);return result;
  }
  function observationGaps(series,start,end){
    const intervals=series.flatMap(s=>s.points.filter(p=>Number.isFinite(p.value)).map(p=>{const t=Date.parse(p.time),tolerance=(s.gapMs||HOUR)/2;return [Math.max(start,t-tolerance),Math.min(end,t+tolerance)];}))
      .filter(([a,b])=>Number.isFinite(a)&&b>a).sort((a,b)=>a[0]-b[0]);
    let cursor=start;const gaps=[];
    for(const [a,b]of intervals){if(a>cursor)gaps.push({a:cursor,b:a});cursor=Math.max(cursor,b);}
    if(cursor<end)gaps.push({a:cursor,b:end});return gaps.filter(g=>g.b-g.a>=HOUR);
  }
  function make(tag,attrs={},text){
    const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;return n;
  }
  function html(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
  function marker(x,y,color,shape='circle',radius=3.5){
    const attrs={fill:color,class:'chart-sample','data-sample-marker':''};
    if(shape==='square')return make('rect',{...attrs,x:x-radius,y:y-radius,width:radius*2,height:radius*2});
    if(shape==='triangle')return make('path',{...attrs,d:`M${x},${y-radius-1} L${x+radius+1},${y+radius} L${x-radius-1},${y+radius} Z`});
    return make('circle',{...attrs,cx:x,cy:y,r:radius});
  }
  function axes(root,{start,end,W,H,L,R,T,B,low,high,step}){
    const x=t=>L+(t-start)/(end-start)*(W-L-R),y=v=>H-B-(v-low)/(high-low)*(H-T-B);
    for(let v=low;v<=high+step/100;v+=step){root.append(make('line',{x1:L,x2:W-R,y1:y(v),y2:y(v),class:'chart-grid'}),make('text',{x:L-8,y:y(v)+4,'text-anchor':'end',class:'chart-label'},number(Math.abs(v)<step/100?0:v)));}
    const list=ticks(start,end,W-L-R);
    list.forEach((t,i)=>{const align=i===0?'start':i===list.length-1?'end':'middle',instant=new Date(t);
      root.append(make('text',{x:x(t),y:H-25,'text-anchor':align,class:'chart-label'},new Intl.DateTimeFormat('pt-BR',{timeZone:TZ,hour:'2-digit',minute:'2-digit'}).format(instant)),
        make('text',{x:x(t),y:H-7,'text-anchor':align,class:'chart-label'},new Intl.DateTimeFormat('pt-BR',{timeZone:TZ,day:'2-digit',month:'2-digit'}).format(instant)));
    });return {x,y};
  }
  function legendItems(target,series){
    target.replaceChildren();
    for(const s of series){
      const item=html('span','legend-item'),swatch=make('svg',{width:30,height:16,viewBox:'0 0 30 16','aria-hidden':'true',class:'legend-swatch'});
      swatch.append(make('line',{x1:1,x2:29,y1:8,y2:8,stroke:s.color,'stroke-width':2.5,'stroke-dasharray':s.dash||''}),marker(15,8,s.color,s.shape,3));
      item.append(swatch,html('span','',s.name));target.append(item);
    }
  }
  function valueText(p,unit){
    return Number.isFinite(p?.value)?`${number(p.value)} ${unit}`:p?.status==='partial'?`Parcial: ${p.validHours}/${p.expectedHours} h · soma disponível ${number(p.partialValue)} ${unit}`:'Sem amostra';
  }
  function nearestIndex(times,t){
    if(!times.length)return -1;
    let left=0,right=times.length;while(left<right){const middle=(left+right)>>1;if(times[middle]<t)left=middle+1;else right=middle;}
    if(left===0)return 0;if(left===times.length)return left-1;
    return t-times[left-1]<=times[left]-t?left-1:left;
  }
  function readingAt(series,t,interval=false){
    const points=series.points;
    if(interval)return points.find(p=>t>Date.parse(p.start_at)&&t<=Date.parse(p.time))||null;
    const times=series.timestamps||points.map(p=>Date.parse(p.time));
    const nearest=points[nearestIndex(times,t)];
    return nearest&&Math.abs(Date.parse(nearest.time)-t)<=(series.gapMs||HOUR)/2?nearest:null;
  }
  const tableState=new WeakMap();
  function dataTable(host,series,{label,unit,cumulativeHours=0}={}){
    if(!host)return;
    let state=tableState.get(host);
    if(!state){
      const details=html('details','chart-data'),summary=html('summary','','Ver dados deste gráfico'),body=html('div','');details.append(summary,body);host.replaceChildren(details);
      state={details,body,page:0,rows:[]};tableState.set(host,state);details.addEventListener('toggle',()=>{if(details.open)fillTable(state);});
    }
    const query=[label,...series.map(s=>s.id+':'+s.points[0]?.time+':'+s.points.at(-1)?.time)].join('|');
    if(state.query!==query)state.page=0;state.query=query;state.label=label;state.unit=unit;state.cumulativeHours=cumulativeHours;
    state.rows=series.flatMap(s=>s.points.map(p=>({s,p}))).sort((a,b)=>Date.parse(b.p.time)-Date.parse(a.p.time)||a.s.name.localeCompare(b.s.name));
    state.page=Math.min(state.page,Math.max(0,Math.ceil(state.rows.length/50)-1));state.details.hidden=!state.rows.length;
    if(state.details.open)fillTable(state);
  }
  function fillTable(state){
    const {body,rows,page,unit,cumulativeHours}=state;body.replaceChildren();
    const wrap=html('div','chart-table-scroll');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Dados: '+state.label);
    const table=html('table','data-table');table.append(html('caption','',state.label+(cumulativeHours?` · cada valor corresponde às ${cumulativeHours} h anteriores ao término`:' · valores originais, antes do agrupamento visual')));
    const head=html('thead',''),tr=html('tr','');for(const text of ['Término / horário','Estação ou modelo','Valor','Início do intervalo']){const th=html('th','',text);th.scope='col';tr.append(th);}head.append(tr);table.append(head);
    const tbody=html('tbody','');for(const {s,p}of rows.slice(page*50,(page+1)*50)){
      const row=html('tr','');for(const text of [date(p.time),s.name,valueText(p,unit),p.start_at?date(p.start_at):'Leitura pontual'])row.append(html('td','',text));tbody.append(row);
    }table.append(tbody);wrap.append(table);body.append(wrap);
    const controls=html('div','chart-table-pages'),status=html('span','',`${page*50+1}–${Math.min(rows.length,(page+1)*50)} de ${rows.length} registros`);status.setAttribute('role','status');
    for(const [text,delta,disabled]of [['Anteriores',-1,page===0],['Próximos',1,(page+1)*50>=rows.length]]){const button=html('button','',text);button.type='button';button.disabled=disabled;button.addEventListener('click',()=>{state.page+=delta;fillTable(state);state.body.querySelector('button:not(:disabled)')?.focus();});controls.append(button);}
    controls.append(status);body.append(controls);
  }
  function render(target,legend,tooltip,input,options){
    target.replaceChildren();legend.replaceChildren();tooltip.hidden=true;
    const {domain,label,unit,sharedScale=null,forecast=false,cumulativeHours=0,tableHost=null}=options,[start,end]=domain;
    const isDark=document.documentElement?.dataset?.theme==='dark';
    const source=input.map(s=>({...s,...identity(s.identity||s.id,s.field,isDark),...s.style,points:s.points.slice().sort((a,b)=>Date.parse(a.time)-Date.parse(b.time))}));
    dataTable(tableHost,source,{label,unit,cumulativeHours});
    const rain=source.some(s=>s.field==='precipitation_mm'||s.field?.startsWith('rain_'));
    const W=Math.max(180,Math.round(target.clientWidth||600)),H=280,L=48,R=12,T=24,B=50,w=W-L-R,h=H-T-B;
    const hours=(end-start)/HOUR,block=forecast&&rain?resolution(hours,w,source.length):1;
    const displayLabel=forecast&&rain&&block>1?label.replace(/por hora/g,`por blocos de ${block} h`):label;
    const series=source.map(s=>{const points=forecast&&rain?aggregateRain(s.points,start,hours,block):s.points;
      return {...s,name:forecast&&rain&&block>1?s.name.replace(' · 1 h',` · ${block} h`):s.name,points,timestamps:points.map(p=>Date.parse(p.time))};});
    const points=series.flatMap(s=>s.points.filter(p=>Number.isFinite(p.value)).map(p=>({...p,series:s})));
    const validHours=forecast?source.map(s=>{const available=new Set(s.points.filter(p=>Number.isFinite(p.value)).map(p=>Date.parse(p.time)));return Array.from({length:hours},(_,i)=>start+(i+(rain?1:0))*HOUR).filter(t=>available.has(t)).length;}):[];
    const coverage=forecast&&validHours.length?`Cobertura: ${Math.min(...validHours)}/${hours} h${validHours.some(n=>n<hours)?' · há lacunas':''}.`:'';
    const result={block,coverage,series};
    if(!points.length){target.append(html('p','empty',options.emptyText||'Sem amostras completas para este recorte. Ausência de dados não significa zero.'));return result;}
    const bounds=sharedScale||scale(points.map(p=>p.value),source.some(s=>s.field==='temperature_c'));
    const root=make('svg',{viewBox:`0 0 ${W} ${H}`,role:'img',class:'weather-chart',tabindex:0,'aria-label':`${displayLabel}, em ${unit}. ${forecast&&rain&&block>1?`Barras de ${block} horas. `:''}Horários de Brasília. Use setas para consultar; Enter fixa e Escape libera.`});
    root.append(make('title',{},displayLabel),make('text',{x:L,y:14,class:'chart-unit'},unit));
    const {x,y}=axes(root,{start,end,W,H,L,R,T,B,...bounds});
    if(forecast){
      const missing=[];
      if(rain){for(const p of series[0].points){const count=series.filter(s=>Number.isFinite(s.points.find(q=>q.time===p.time)?.value)).length;if(count<series.length)missing.push({a:Date.parse(p.start_at),b:Date.parse(p.time),partial:count>0||series.some(s=>s.points.find(q=>q.time===p.time)?.status==='partial')});}}
      else for(let i=0;i<hours;i++){const t=start+i*HOUR,count=series.filter(s=>s.points.some(p=>Date.parse(p.time)===t&&Number.isFinite(p.value))).length;if(count<series.length)missing.push({a:t,b:t+HOUR,partial:count>0});}
      const runs=[];for(const gap of missing){const last=runs.at(-1);if(last&&last.b===gap.a&&last.partial===gap.partial)last.b=gap.b;else runs.push({...gap});}
      for(const gap of runs){const band=make('rect',{x:x(gap.a),y:T,width:Math.max(1,x(gap.b)-x(gap.a)),height:h,class:'chart-gap'});band.append(make('title',{},`${gap.partial?'Cobertura parcial':'Sem amostras'}: ${date(new Date(gap.a).toISOString())} a ${date(new Date(gap.b).toISOString())}`));root.append(band);if(x(gap.b)-x(gap.a)>90)root.append(make('text',{x:x(gap.a)+5,y:T+16,class:'chart-gap-label'},gap.partial?'Parcial':'Sem dados'));}
    }else{
      for(const gap of observationGaps(series,start,end)){const band=make('rect',{x:x(gap.a),y:T,width:Math.max(1,x(gap.b)-x(gap.a)),height:h,class:'chart-gap'});band.append(make('title',{},'Sem amostras próximas neste trecho. Não significa valor zero.'));root.append(band);if(x(gap.b)-x(gap.a)>90)root.append(make('text',{x:x(gap.a)+5,y:T+16,class:'chart-gap-label'},'Sem amostras'));}
    }
    series.forEach((s,index)=>{
      if(forecast&&rain){
        for(const p of s.points){if(!Number.isFinite(p.value))continue;const a=x(Date.parse(p.start_at)),b=x(Date.parse(p.time)),slot=(b-a)*.86/series.length,bx=a+(b-a)*.07+slot*index;
          const mark=p.value===0?make('line',{x1:bx,x2:bx+Math.max(.5,slot-.8),y1:y(0),y2:y(0),stroke:s.color,'stroke-width':1.5,class:'chart-zero'}):make('rect',{x:bx,y:y(p.value),width:Math.max(.5,slot-.8),height:y(0)-y(p.value),fill:s.color,class:'rain-interval'});
          mark.append(make('title',{},`${s.name}: ${valueText(p,unit)} · ${date(p.start_at)} a ${date(p.time)}`));root.append(mark);
        }
      }else{
        const runs=segments(s.points,s.gapMs||HOUR);
        for(const run of runs){const reduced=simplify(run,start,end,Math.max(1,Math.floor(w)));
          if(reduced.length>1)root.append(make('path',{d:reduced.map((p,i)=>`${i?'L':'M'}${x(Date.parse(p.time)).toFixed(2)},${y(p.value).toFixed(2)}`).join(' '),fill:'none',stroke:s.color,'stroke-width':2.5,'stroke-dasharray':s.dash||'',class:cumulativeHours?'accumulation-line':'weather-line'}));
          const selected=reduced.length<=60?reduced:[reduced[0],reduced.at(-1),reduced.reduce((a,b)=>a.value<b.value?a:b),reduced.reduce((a,b)=>a.value>b.value?a:b)];
          for(const p of new Set(selected)){const dot=marker(x(Date.parse(p.time)),y(p.value),s.color,s.shape);dot.setAttribute('class',cumulativeHours?'chart-sample accumulation-sample':'chart-sample');dot.append(make('title',{},`${s.name}: ${number(p.value)} ${unit} · ${cumulativeHours?`${cumulativeHours} h anteriores a `:''}${date(p.time)}`));root.append(dot);}
        }
      }
    });
    legendItems(legend,series);
    const times=[...new Set(series.flatMap(s=>s.points.map(p=>Date.parse(p.time))))].filter(t=>Number.isFinite(t)&&t>=start&&t<=end).sort((a,b)=>a-b);
    if(tableHost?.id)root.setAttribute('aria-details',tableHost.id);
    if(typeof ChartInteraction!=='undefined')ChartInteraction.attach(root,{width:W,left:L,right:R,top:T,bottom:H-B,domain,times,tooltip,lookup(t){
      const selected=series.map(s=>({s,p:readingAt(s,t,forecast&&rain)}));
      const rows=selected.slice(0,4),marks=rows.filter(r=>Number.isFinite(r.p?.value)).map(({s,p})=>({x:forecast&&rain?x(t):x(Date.parse(p.time)),y:y(p.value),color:s.color,shape:s.shape}));
      const text=[cumulativeHours?`Acumulado móvel de ${cumulativeHours} h · término da leitura`:displayLabel,...rows.map(({s,p})=>`${s.name}: ${valueText(p,unit)}${p?' · '+(forecast&&rain?date(p.start_at)+' a ':'')+date(p.time):''}`)];
      if(selected.length>4)text.push(`+${selected.length-4} séries · filtre por estação ou consulte a tabela`);
      if(!marks.length)text.push('Ausência de amostra não significa zero.');return {text:text.join('\n'),marks};
    }});
    target.append(root);return result;
  }
  const api={HOUR,identity,scale,resolution,aggregateRain,simplify,segments,ticks,observationGaps,nearestIndex,readingAt,axes,marker,legendItems,dataTable,render,number,date};
  if(typeof module!=='undefined')module.exports=api;
  if(typeof window!=='undefined')window.WeatherCharts=api;
})();
