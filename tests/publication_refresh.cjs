'use strict';
const assert=require('node:assert/strict');
const {create}=require('../web/publication-refresh.js');
(async()=>{
  let version='2026-11-08T12:00:00Z',clock=Date.parse(version),visible=true,requests=0,reloads=0,errors=0;
  let next={schema_version:1,generated_at:version};
  const poll=create({getVersion:()=>version,now:()=>clock,isVisible:()=>visible,
    readLatest:async()=>{requests++;return next;},reload:async()=>{reloads++;version=next.generated_at;},onError:()=>errors++});
  assert.equal(await poll.check(),false);assert.equal(requests,1);
  next={...next,generated_at:'2026-11-08T12:00:30Z'};
  await poll.check();assert.equal(requests,1); // throttle
  clock+=60000;visible=false;await poll.check();assert.equal(requests,1);
  visible=true;assert.equal(await poll.check(),true);assert.equal(reloads,1);
  clock+=60000;next.generated_at='2026-11-08T12:00:00Z';await poll.check();assert.equal(reloads,1); // no CDN rollback
  clock+=60000;next.fixture_mode=true;await poll.check();assert.equal(errors,1);assert.equal(version,'2026-11-08T12:00:30Z');
  clock+=60000;next={schema_version:1,generated_at:'invalid'};await poll.check();assert.equal(errors,2);
  let finish;
  const locked=create({getVersion:()=>version,readLatest:()=>new Promise(resolve=>{finish=resolve;}),reload:async()=>{reloads++;}});
  const pending=locked.check();assert.equal(await locked.check(),false);
  finish({schema_version:1,generated_at:version});await pending;assert.equal(reloads,1);
  const offline=create({getVersion:()=>version,readLatest:async()=>{throw Error('offline');},reload:async()=>{throw Error('must not run');},onError:()=>errors++});
  await offline.check();assert.equal(errors,3);assert.equal(version,'2026-11-08T12:00:30Z');
  let incomplete=true,repaired=0;
  const repair=create({getVersion:()=>version,now:()=>clock,readLatest:async()=>({schema_version:1,generated_at:version}),needsReload:()=>incomplete,
    reload:async latest=>{assert.equal(latest.generated_at,version);repaired++;incomplete=false;}});
  assert.equal(await repair.check(),true);assert.equal(repaired,1);
  clock+=60000;assert.equal(await repair.check(),false);assert.equal(repaired,1);
  const future=create({getVersion:()=>version,now:()=>clock,readLatest:async()=>({schema_version:1,generated_at:'2030-01-01T00:00:00Z'}),
    reload:async()=>{throw Error('Future publication cannot be loaded');},onError:()=>errors++});
  assert.equal(await future.check(),false);assert.equal(errors,4);
  console.log('Publication refresh passed: active tab, new versions, throttling, locking, invalid/test data, CDN rollback and offline recovery.');
})().catch(error=>{console.error(error);process.exitCode=1;});
