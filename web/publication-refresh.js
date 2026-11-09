'use strict';
(function(root){
  function create({getVersion,readLatest,reload,needsReload=()=>false,onError=()=>{},onSuccess=()=>{},isVisible=()=>true,now=()=>Date.now(),intervalMs=60000}) {
    let busy=false,lastAttempt=-Infinity;
    async function check() {
      if(busy||!isVisible()||now()-lastAttempt<intervalMs)return false;
      busy=true;lastAttempt=now();
      try {
        const latest=await readLatest();
        if(latest?.schema_version!==1||latest.fixture_mode||!Number.isFinite(Date.parse(latest.generated_at))||Date.parse(latest.generated_at)>now()+600000)throw new Error('Invalid publication');
        const current=Date.parse(getVersion());
        // Never roll back a newer publication while CDN edges converge.
        if(!Number.isFinite(current)||Date.parse(latest.generated_at)>current||(Date.parse(latest.generated_at)===current&&needsReload())){
          if(await reload(latest)===false)throw new Error('Publication reload failed');
          onSuccess();return true;
        }
        // An older edge response cannot confirm a pending failed read.
        if(needsReload())return false;
        onSuccess();
        return false;
      }catch(error){onError(error);return false;}
      finally{busy=false;}
    }
    return {check};
  }
  if(typeof module!=='undefined')module.exports={create};
  root.PublicationRefresh={create};
})(typeof globalThis!=='undefined'?globalThis:this);
