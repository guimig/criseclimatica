'use strict';
(function () {
  const tabs=[...document.querySelectorAll('[data-explore-tab]')],panels=[...document.querySelectorAll('[data-explore-panel]')];
  if(!tabs.length||!panels.length)return;
  const names=new Set(panels.map(p=>p.dataset.explorePanel));
  function revealAncestors(target){for(let node=target?.parentElement;node;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;}
  function activate(name,{writeHash=false,focus=false}={}){
    if(!names.has(name))name='overview';
    for(const panel of panels)panel.hidden=panel.dataset.explorePanel!==name;
    for(const tab of tabs){const active=tab.dataset.exploreTab===name;tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;if(active&&focus)tab.focus();}
    if(writeHash&&location.hash!=='#explore-'+name)history.pushState(null,'','#explore-'+name);
    document.documentElement.classList.add('explore-ready');
  }
  function fromHash(){
    let hash;try{hash=decodeURIComponent(location.hash.slice(1));}catch{hash='';}
    const target=document.getElementById(hash),pane=target?.closest('[data-explore-panel]');
    activate(pane?.dataset.explorePanel||'overview');
    if(target&&pane&&target!==pane){revealAncestors(target);requestAnimationFrame(()=>target.scrollIntoView({block:'start',behavior:'auto'}));}
  }
  for(const tab of tabs){
    tab.addEventListener('click',()=>activate(tab.dataset.exploreTab,{writeHash:true}));
    tab.addEventListener('keydown',event=>{
      if(!['ArrowRight','ArrowLeft','ArrowUp','ArrowDown','Home','End'].includes(event.key))return;
      event.preventDefault();const index=tabs.indexOf(tab),next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(['ArrowRight','ArrowDown'].includes(event.key)?1:-1)+tabs.length)%tabs.length;
      activate(tabs[next].dataset.exploreTab,{writeHash:true,focus:true});
    });
  }
  for(const button of document.querySelectorAll('[data-open-section]'))button.addEventListener('click',()=>{activate(button.dataset.openSection,{writeHash:true});document.getElementById('explore-'+button.dataset.openSection).focus({preventScroll:true});});
  const media=matchMedia('(max-width:900px)');
  const orientation=()=>document.getElementById('explore-tabs').setAttribute('aria-orientation',media.matches?'horizontal':'vertical');
  media.addEventListener('change',orientation);orientation();
  window.addEventListener('hashchange',fromHash);window.addEventListener('popstate',fromHash);fromHash();
})();
