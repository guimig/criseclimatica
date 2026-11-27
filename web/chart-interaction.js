'use strict';
/* One cursor behavior for overview, detailed and multi-model charts. */
(function(){
  function attach(root,options){
    const {width,left,right,top,bottom,domain,times,tooltip,lookup}=options;
    const vertical=options.axis==='y';
    if(!root||!tooltip||!times?.length||!domain.every(Number.isFinite))return;
    const ns='http://www.w3.org/2000/svg';
    const shape=(name,attrs)=>{const n=document.createElementNS(ns,name);for(const [key,value]of Object.entries(attrs))n.setAttribute(key,String(value));return n;};
    const x=t=>left+(t-domain[0])/(domain[1]-domain[0])*(width-left-right);
    const row=t=>top+(t-domain[0])/(domain[1]-domain[0])*(bottom-top);
    const guide=shape('line',{x1:left,x2:vertical?width-right:left,y1:top,y2:vertical?top:bottom,class:'chart-cursor',visibility:'hidden','data-chart-cursor':''});
    const marks=shape('g',{'data-chart-markers':''});
    const hit=shape('rect',{x:left,y:vertical?0:top,width:Math.max(1,width-left-right),height:Math.max(1,vertical?Number(root.getAttribute('viewBox').split(' ')[3]):bottom-top),fill:'transparent',class:'chart-hit','data-chart-hit':''});
    root.append(guide,marks,hit);root.dataset.pinned='false';tooltip.classList.add('interactive-tooltip');tooltip.setAttribute('role','status');tooltip.setAttribute('aria-live','off');
    if(tooltip.id)root.setAttribute('aria-describedby',tooltip.id);
    let cursor=0,pinned=false;
    const nearest=t=>typeof WeatherCharts!=='undefined'?WeatherCharts.nearestIndex(times,t):times.reduce((best,v,i)=>Math.abs(v-t)<Math.abs(times[best]-t)?i:best,0);
    function hide(){tooltip.hidden=true;guide.setAttribute('visibility','hidden');marks.replaceChildren();}
    function position(clientX,clientY){
      // On small screens the reading stays in the document flow, below the chart.
      if(getComputedStyle(tooltip).position==='static'){
        tooltip.style.removeProperty('left');tooltip.style.removeProperty('top');return;
      }
      const parent=tooltip.offsetParent||tooltip.parentElement,box=parent.getBoundingClientRect();
      const tw=tooltip.offsetWidth,th=tooltip.offsetHeight;
      const pad=8,gap=12,w=parent.clientWidth,h=parent.clientHeight;
      // The absolute containing block starts inside the parent's border.
      const ax=clientX-box.left-parent.clientLeft,ay=clientY-box.top-parent.clientTop;
      // Flip to the left near the right edge, then clamp without squeezing the text.
      let px=ax+gap;if(px+tw>w-pad)px=ax-tw-gap;
      px=Math.max(pad,Math.min(px,Math.max(pad,w-tw-pad)));
      let py=ay-th-gap;if(py<pad)py=ay+20;
      py=Math.max(pad,Math.min(py,Math.max(pad,h-th-pad)));
      tooltip.style.left=px+'px';tooltip.style.top=py+'px';
    }
    function show(t,event,keyboard=false){
      const value=lookup(t,keyboard);if(!value)return;
      tooltip.replaceChildren(document.createTextNode(value.text));
      if(pinned){const note=document.createElement('span');note.className='tooltip-pinned';note.textContent='Fixado · toque/clique ou Esc para soltar';tooltip.append(note);}
      tooltip.setAttribute('aria-live',keyboard?'polite':'off');tooltip.hidden=false;
      if(vertical){guide.setAttribute('y1',row(t));guide.setAttribute('y2',row(t));}else{guide.setAttribute('x1',x(t));guide.setAttribute('x2',x(t));}guide.setAttribute('visibility','visible');marks.replaceChildren();
      for(const point of value.marks||[])if(Number.isFinite(point.x)&&Number.isFinite(point.y)){
        const mark=typeof WeatherCharts!=='undefined'?WeatherCharts.marker(point.x,point.y,point.color||'currentColor',point.shape,4.5):shape('circle',{cx:point.x,cy:point.y,r:4.5,fill:point.color||'currentColor'});
        mark.setAttribute('class','chart-point-ring');marks.append(mark);
      }
      const box=root.getBoundingClientRect();position(event?.clientX??box.left+(vertical?width/2:x(t))/width*box.width,event?.clientY??box.top+(vertical?row(t):top+20));
    }
    function time(event){const box=root.getBoundingClientRect(),pixel=vertical?(event.clientY-box.top)/box.height*Number(root.getAttribute('viewBox').split(' ')[3]):(event.clientX-box.left)/box.width*width;
      const ratio=vertical?(pixel-top)/Math.max(1,bottom-top):(pixel-left)/(width-left-right);return Math.max(domain[0],Math.min(domain[1],domain[0]+ratio*(domain[1]-domain[0])));}
    root.addEventListener('pointermove',event=>{if(event.pointerType==='touch'||pinned)return;const t=time(event);cursor=nearest(t);show(t,event);});
    root.addEventListener('click',event=>{pinned=!pinned;root.dataset.pinned=String(pinned);if(pinned){const t=time(event);cursor=nearest(t);show(t,event);}else hide();});
    root.addEventListener('pointerleave',()=>{if(!pinned)hide();});
    root.addEventListener('blur',()=>{if(!pinned)hide();});
    root.addEventListener('keydown',event=>{
      if(event.key==='Escape'){event.preventDefault();pinned=false;root.dataset.pinned='false';hide();return;}
      if(['Enter',' '].includes(event.key)){event.preventDefault();pinned=!pinned;root.dataset.pinned=String(pinned);if(pinned)show(times[cursor],null,true);else hide();return;}
      if(!['ArrowRight','ArrowLeft','Home','End',...(vertical?['ArrowDown','ArrowUp']:[])].includes(event.key))return;
      event.preventDefault();cursor=event.key==='Home'?0:event.key==='End'?times.length-1:Math.max(0,Math.min(times.length-1,cursor+(['ArrowRight','ArrowDown'].includes(event.key)?1:-1)));
      show(times[cursor],null,true);
    });
  }
  if(typeof module!=='undefined')module.exports={attach};
  if(typeof window!=='undefined')window.ChartInteraction={attach};
})();
