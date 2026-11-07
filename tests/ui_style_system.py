"""Rendered accessibility checks shared by the page-level browser scenarios."""


def check_style_system(page):
    report=page.evaluate("""() => {
      const rgb=s=>(s.match(/[0-9.]+/g)||[]).map(Number);
      const blend=(fg,bg)=>fg.slice(0,3).map((v,i)=>v*(fg[3]??1)+bg[i]*(1-(fg[3]??1)));
      const luminance=c=>c.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
      function background(el){
        const chain=[];for(let p=el;p;p=p.parentElement)chain.unshift(p);
        return chain.reduce((bg,p)=>blend(rgb(getComputedStyle(p).backgroundColor),bg),[255,255,255]);
      }
      const errors=[];
      for(const el of document.querySelectorAll('button,select,summary,.reference-links a')){
        if(!el.checkVisibility()||el.disabled)continue;
        const rect=el.getBoundingClientRect(),style=getComputedStyle(el);
        const label=el.id||el.textContent.trim().slice(0,60);
        if(rect.height<43.5||rect.width<43.5)errors.push({label,problem:'Small touch target',width:rect.width,height:rect.height});
        const bg=background(el),fg=blend(rgb(style.color),bg),a=luminance(bg),b=luminance(fg),contrast=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
        if(contrast<4.5)errors.push({label,problem:'Text contrast below 4.5',contrast});
        if(el.tagName==='SELECT'){
          const border=luminance(rgb(style.borderTopColor)),contrast=(Math.max(a,border)+.05)/(Math.min(a,border)+.05);
          if(contrast<3)errors.push({label,problem:'Select border contrast below 3',contrast});
        }
        if(parseFloat(style.fontSize)<13)errors.push({label,problem:'Small control text',font:style.fontSize});
      }
      if(document.documentElement.scrollWidth>innerWidth)errors.push({problem:'Page overflow'});
      return errors;
    }""")
    assert not report, report
