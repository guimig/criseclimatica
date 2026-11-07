'use strict';
/* One cursor behavior for overview, detailed and multi-model charts. */
(function(){
  function attach(root,options){
    const {width,left,right,top,bottom,domain,times,tooltip,lookup}=options;
    if(!root||!tooltip||!times?.length||!domain.every(Number.isFinite))return;
    const ns='http://www.w3.org/2000/svg';
    const shape=(name,attrs)=>{const n=document.createElementNS(ns,name);for(const [key,value]of Object.entries(attrs))n.setAttribute(key,String(value));return n;};
    const x=t=>left+(t-domain[0])/(domain[1]-domain[0])*(width-left-right);
    const guide=shape('line',{x1:left,x2:left,y1:top,y2:bottom,class:'chart-cursor',visibility:'hidden','data-chart-cursor':''});
    const marks=shape('g',{'data-chart-markers':''});
    const hit=shape('rect',{x:left,y:top,width:Math.max(1,width-left-right),height:Math.max(1,bottom-top),fill:'transparent',class:'chart-hit','data-chart-hit':''});
    root.append(guide,marks,hit);root.dataset.pinned='false';tooltip.classList.add('interactive-tooltip');tooltip.setAttribute('role','status');tooltip.setAttribute('aria-live','off');
    if(tooltip.id)root.setAttribute('aria-describedby',tooltip.id);
    let cursor=0,pinned=false;
    function hide(){tooltip.hidden=true;guide.setAttribute('visibility','hidden');marks.replaceChildren();}
    function position(clientX,clientY){
      const parent=tooltip.offsetParent||tooltip.parentElement,box=parent.getBoundingClientRect();
      const tw=tooltip.offsetWidth,th=tooltip.offsetHeight;
      let px=Math.max(8,Math.min(clientX-box.left+12,box.width-tw-8));
      let py=clientY-box.top-th-12;if(py<8)py=clientY-box.top+20;
      // Keep the reading within its panel, including on narrow touch screens.
      py=Math.max(8,Math.min(py,Math.max(8,box.height-th-8)));
      tooltip.style.left=px+'px';tooltip.style.top=py+'px';
    }
    function show(t,event,keyboard=false){
      const value=lookup(t,keyboard);if(!value)return;
      tooltip.replaceChildren(document.createTextNode(value.text));
      if(pinned){const note=document.createElement('span');note.className='tooltip-pinned';note.textContent='Leitura fixada · clique/toque novamente ou Esc para soltar';tooltip.append(note);}
      tooltip.setAttribute('aria-live',keyboard?'polite':'off');tooltip.hidden=false;
      guide.setAttribute('x1',x(t));guide.setAttribute('x2',x(t));guide.setAttribute('visibility','visible');marks.replaceChildren();
      for(const point of value.marks||[])if(Number.isFinite(point.x)&&Number.isFinite(point.y))marks.append(shape('circle',{cx:point.x,cy:point.y,r:4.5,fill:point.color||'currentColor',class:'chart-point-ring'}));
      const box=root.getBoundingClientRect();position(event?.clientX??box.left+x(t)/width*box.width,event?.clientY??box.top+top+20);
    }
    function time(event){const box=root.getBoundingClientRect(),pixel=(event.clientX-box.left)/box.width*width;return Math.max(domain[0],Math.min(domain[1],domain[0]+(pixel-left)/(width-left-right)*(domain[1]-domain[0])));}
    root.addEventListener('pointermove',event=>{if(event.pointerType==='touch'||pinned)return;const t=time(event);cursor=times.reduce((best,v,i)=>Math.abs(v-t)<Math.abs(times[best]-t)?i:best,0);show(t,event);});
    root.addEventListener('click',event=>{pinned=!pinned;root.dataset.pinned=String(pinned);if(pinned)show(time(event),event);else hide();});
    root.addEventListener('pointerleave',()=>{if(!pinned)hide();});
    root.addEventListener('blur',()=>{if(!pinned)hide();});
    root.addEventListener('keydown',event=>{
      if(event.key==='Escape'){event.preventDefault();pinned=false;root.dataset.pinned='false';hide();return;}
      if(!['ArrowRight','ArrowLeft','Home','End'].includes(event.key))return;
      event.preventDefault();cursor=event.key==='Home'?0:event.key==='End'?times.length-1:Math.max(0,Math.min(times.length-1,cursor+(event.key==='ArrowRight'?1:-1)));
      show(times[cursor],null,true);
    });
  }
  if(typeof module!=='undefined')module.exports={attach};
  if(typeof window!=='undefined')window.ChartInteraction={attach};
})();
