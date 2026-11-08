'use strict';
(function(root){
  function create({getVersion,readLatest,reload,onError=()=>{},onSuccess=()=>{},isVisible=()=>true,now=()=>Date.now(),intervalMs=60000}) {
    let busy=false,lastAttempt=-Infinity;
    async function check() {
      if(busy||!isVisible()||now()-lastAttempt<intervalMs)return false;
      busy=true;lastAttempt=now();
      try {
        const latest=await readLatest();
        if(latest?.schema_version!==1||latest.fixture_mode||!Number.isFinite(Date.parse(latest.generated_at)))throw new Error('Invalid publication');
        onSuccess();
        const current=Date.parse(getVersion());
        // Never roll back a newer publication while CDN edges converge.
        if(!Number.isFinite(current)||Date.parse(latest.generated_at)>current){await reload();return true;}
        return false;
      }catch(error){onError(error);return false;}
      finally{busy=false;}
    }
    return {check};
  }
  if(typeof module!=='undefined')module.exports={create};
  root.PublicationRefresh={create};
})(typeof globalThis!=='undefined'?globalThis:this);
