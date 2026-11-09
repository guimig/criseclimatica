'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const {create}=require('../web/publication-refresh.js');
const script=fs.readFileSync(path.join(__dirname,'../web/dashboard.js'),'utf8');
const stamp=new Date().toISOString(),older=new Date(Date.now()-60000).toISOString();
const latest={schema_version:1,generated_at:stamp,publication_at:stamp};
const dashboard={schema_version:1,kind:'araquari_weather_dashboard_not_official_decision',location_id:'araquari',decision_automated:false,generated_at:stamp,publication_at:stamp,valid_until:new Date(Date.now()+10800000).toISOString()};
const history={kind:'araquari_point_observation_history_not_climatology',location_id:'araquari',generated_at:stamp,publication_at:stamp,records:[]};
const payloads={'latest.json':latest,'dashboard.json':dashboard,'observation_history.json':history};
function harness(respond){
  const requests=[],elements=new Map();let responder=respond;
  const context=vm.createContext({console:{error(){}},Intl,Date,URL,AbortController,setTimeout,clearTimeout,
    fetch:async(url,options)=>{
      requests.push(url);assert.equal(options.cache,'no-store');
      const name=url.split('/').at(-1).split('?')[0];
      return responder(name,url);
    }});
  vm.runInContext(script,context); // Avoid the DOM boot; exercise the real loader.
  context.document={getElementById(id){if(!elements.has(id))elements.set(id,{});return elements.get(id);}};
  vm.runInContext('renderSummary=()=>{};renderRecent=()=>{};renderMemory=()=>{};renderChart=()=>{};',context);
  return {run:code=>vm.runInContext(code,context),requests,elements,setResponder(fn){responder=fn;}};
}
const response=payload=>({ok:true,json:async()=>JSON.parse(JSON.stringify(payload))});
const valid=name=>response(payloads[name]);
(async()=>{
  const normal=harness(valid);
  assert.equal(await normal.run('loadDashboard()'),true);
  assert.equal(normal.requests.length,3);
  assert.equal(normal.run('panel.history.records.length'),0);
  assert.equal(normal.run('panel.fetchError||panel.loading'),false);
  for(const fail of ['identity','timestamp','network','http','json']){
    const h=harness((name,url)=>{
      if(!url.includes('?refresh=')&&name==='dashboard.json'){
        if(fail==='identity')return response({...dashboard,publication_at:older});
        if(fail==='timestamp')return response({...dashboard,generated_at:older});
        if(fail==='network')throw Error('Failed to fetch');
        if(fail==='http')return {ok:false,status:503};
        if(fail==='json')return {ok:true,json:async()=>{throw SyntaxError('truncated');}};
      }
      return valid(name);
    });
    assert.equal(await h.run('loadDashboard()'),true,fail+' recovers in the same load');
    assert.equal(h.requests.length,6,fail);
    assert.ok(h.requests.slice(3).every(url=>url.includes('?refresh=')),fail);
    assert.equal(new Set(h.requests.slice(3).map(url=>url.split('?')[1])).size,1);
    assert.equal(h.run('panel.data.generated_at'),stamp);
    assert.equal(h.run('panel.fetchError'),false);
  }
  const never=harness(name=>response(name==='dashboard.json'?{...dashboard,publication_at:older}:payloads[name]));
  assert.equal(await never.run('loadDashboard()'),false);
  assert.equal(never.run('panel.data'),null);
  assert.equal(never.run('panel.fetchError'),true);
  assert.match(never.run('riskPresentation(null).title'),/Dados indisponíveis/);
  assert.doesNotMatch(never.run('riskPresentation(null).reason'),/perdeu validade|preservada/);
  assert.equal(never.elements.get('refresh').disabled,false);
  never.setResponder(valid);
  assert.equal(await never.run('loadDashboard()'),true);
  const verified=never.run('panel.data');
  never.setResponder(()=>{throw Error('offline');});
  assert.equal(await never.run('loadDashboard()'),false);
  assert.equal(never.run('panel.data'),verified);
  let successes=0,errors=0;
  const poll=create({getVersion:()=>never.run('panel.data?.generated_at'),needsReload:()=>never.run('panel.fetchError||panel.incompleteHistory'),
    intervalMs:0,readLatest:async()=>latest,reload:()=>never.run('loadDashboard()'),onSuccess:()=>successes++,onError:()=>errors++});
  assert.equal(await poll.check(),false);
  assert.equal(successes,0);assert.equal(errors,1);
  assert.equal(never.run('panel.fetchError'),true); // A valid manifest cannot hide a failed dashboard.
  never.setResponder(valid);
  assert.equal(await poll.check(),true);assert.equal(successes,1);
  assert.equal(never.run('panel.fetchError'),false);
  const missingHistory=harness(name=>{if(name==='observation_history.json')throw Error('offline');return valid(name);});
  assert.equal(await missingHistory.run('loadDashboard()'),true);
  assert.equal(missingHistory.run('panel.incompleteHistory'),true);
  assert.equal(missingHistory.run('panel.data.generated_at'),stamp);
  const invalid=harness(name=>response(name==='dashboard.json'?{...dashboard,fixture_mode:true}:payloads[name]));
  assert.equal(await invalid.run('loadDashboard()'),false);assert.equal(invalid.run('panel.data'),null);
  const rollback=harness(valid);await rollback.run('loadDashboard()');
  rollback.setResponder(name=>response({...payloads[name],generated_at:older,publication_at:older}));
  assert.equal(await rollback.run('loadDashboard()'),false);
  assert.equal(rollback.run('panel.data.generated_at'),stamp);
  console.log('Dashboard loading passed: transient CDN identities, timestamps, network/HTTP/JSON recovery, bounded cache-bypassing retry, first-load messages, preserved snapshots, polling recovery, missing history, fixtures and rollback.');
})().catch(error=>{console.error(error);process.exitCode=1;});
