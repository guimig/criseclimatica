'use strict';
(function(){
  const key='observatorio-theme';
  function preference(storage,dark){try{const saved=storage.getItem(key);if(saved==='dark'||saved==='light')return saved;}catch{}return dark?'dark':'light';}
  if(typeof module!=='undefined')module.exports={preference};
  if(typeof document==='undefined')return;
  let storage;try{storage=window.localStorage;}catch{storage={getItem(){return null;},setItem(){}};}
  let theme=preference(storage,window.matchMedia?.('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme=theme;
  function buttonState(){const b=document.getElementById('theme-toggle');if(!b)return;b.setAttribute('aria-pressed',String(theme==='dark'));b.setAttribute('aria-label',theme==='dark'?'Usar tema claro':'Usar tema escuro');b.textContent=theme==='dark'?'☀ Claro':'☾ Escuro';}
  function bind(){buttonState();document.getElementById('theme-toggle')?.addEventListener('click',()=>{theme=theme==='dark'?'light':'dark';document.documentElement.dataset.theme=theme;try{storage.setItem(key,theme);}catch{}buttonState();document.dispatchEvent(new Event('observatorythemechange'));});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind,{once:true});else bind();
})();
