const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../variants/research-recorder/src/common/research.js');

function disk() {
  const files = new Map(); let hold = false, failure = false; const pending = [];
  const api = {
    list(o) { queueMicrotask(() => o.success({fileList: [...files.keys()].map(uri => ({uri}))})); },
    readText(o) { queueMicrotask(() => files.has(o.uri) ? o.success({text: files.get(o.uri)}) : o.fail('missing',301)); },
    writeText(o) { const run = () => failure ? o.fail('full',300) : (files.set(o.uri,o.text),o.success()); if(hold)pending.push(run);else queueMicrotask(run); },
    delete(o) { queueMicrotask(() => files.delete(o.uri) ? o.success() : o.fail('missing',301)); }
  };
  return {api, files, pending, hold(v) {hold=v;}, fail(v) {failure=v;}, flush() {while(pending.length)pending.shift()();}};
}
const settle = () => new Promise(resolve => setImmediate(resolve));

test('five-minute synthetic stream persists all raw values with bounded RAM and a terminal tail', async () => {
  const d=disk();let t=1000000;const store=core.createStore(d.api,{now:()=>t});
  const s=await store.start({durationSeconds:300, interval:'game', wrist:'left',participant:'P01'});
  for(let i=0;i<15000;i++){t=1000000+i*20;s.push({x:1.234567890123,y:-2,z:3},'visible');if(i%50===0){s.tick();await settle();}assert.ok(s.state().buffered<=512);}
  s.stop('manual');await settle();await settle();
  assert.equal(s.state().status,'sealed');assert.equal(s.state().persisted,15000);
  const items=await store.list(false);assert.equal(items.length,1);assert.equal(items[0].count,15000);
  const inv=await store.inventory(items[0].id);const texts=[];
  for(const name of inv.files)texts.push(await store.readPart(items[0].id,name));
  const blocks=texts.map(JSON.parse).filter(p=>p.kind==='block');
  assert.equal(blocks.flatMap(b=>b.rows).length,15000);assert.equal(blocks[0].rows[0][2],1.234567890123);
  assert.equal(JSON.parse(texts[0]).metadata.time_source,'Date.now_callback_arrival');
  assert.equal(JSON.parse(texts[0]).metadata.participant,'P01');
});

test('slow disk stops before exceeding bounded queue, keeps pending data, and records failure',async()=>{
  const d=disk();let t=1;const store=core.createStore(d.api,{now:()=>t});const s=await store.start({durationSeconds:60});
  d.hold(true);for(let i=0;i<600;i++){t++;s.push({x:i,y:0,z:0});}
  assert.ok(s.state().buffered<=512);assert.equal(s.state().stop_reason,'queue_overflow');assert.equal(s.state().count,512);
  d.hold(false);d.flush();await settle();await settle();assert.equal(s.state().status,'sealed');
  assert.equal(s.state().count,s.state().persisted);assert.ok(s.state().warnings.includes('queue_overflow'));
});

test('write failure retains the same pending block for explicit retry; incomplete sessions remain recoverable',async()=>{
  const d=disk();let t=100;const store=core.createStore(d.api,{now:()=>t});const s=await store.start({durationSeconds:60});
  d.fail(true);for(let i=0;i<128;i++){t++;s.push({x:i,y:0,z:0});}await settle();
  assert.equal(s.state().status,'failed');assert.equal(s.state().buffered,128);
  let items=await store.list(false);assert.equal(items[0].state,'interrupted');
  d.fail(false);s.retry();await settle();await settle();assert.equal(s.state().status,'sealed');assert.equal(s.state().persisted,128);
});

test('wall clock regressions abort and invalid samples are counted without manufacturing rows',async()=>{
  const d=disk();let t=1000;const store=core.createStore(d.api,{now:()=>t});const s=await store.start({durationSeconds:10});
  s.push({x:NaN,y:0,z:0});t=1020;s.push({x:1,y:2,z:3});t=1010;s.push({x:1,y:2,z:3});await settle();await settle();
  assert.equal(s.state().stop_reason,'clock_regression');assert.equal(s.state().count,1);assert.equal(s.state().invalid_samples,1);
});

test('trash is reversible; purge requires sealed session and explicit identity; paths reject traversal',async()=>{
  const d=disk();const store=core.createStore(d.api);const s=await store.start({durationSeconds:2});s.push({x:1,y:2,z:3});s.stop('manual');await settle();await settle();
  const id=s.state().id;await store.trash(id);assert.equal((await store.list(false)).length,0);assert.equal((await store.list(true)).length,1);
  await store.restore(id);assert.equal((await store.list(false)).length,1);
  await assert.rejects(()=>store.purge(id,id),/回收/);await store.trash(id);await assert.rejects(()=>store.purge(id,'wrong'),/确认/);
  await store.purge(id,id);assert.equal((await store.list(true)).length,0);
  await assert.rejects(()=>store.inventory('../secret'),/ID/);await assert.rejects(()=>store.readPart(id,'../../secret'),/文件/);
});

test('a timed-out file callback never silently completes the session on late success',async()=>{
  const d=disk();let t=0;const store=core.createStore(d.api,{now:()=>t});const s=await store.start({durationSeconds:60});
  d.hold(true);for(let i=0;i<128;i++){t++;s.push({x:i,y:0,z:0});}t+=8100;s.tick();
  assert.equal(s.state().status,'failed');assert.equal(s.state().stop_reason,'write_timeout');
  d.flush();await settle();assert.equal(s.state().status,'failed');assert.equal(s.state().retryable,false);
});

test('permanent delete can resume after a partial failure without touching other sessions',async()=>{
  const d=disk();const store=core.createStore(d.api);const s=await store.start({durationSeconds:2});s.push({x:1,y:2,z:3});s.stop('manual');await settle();await settle();
  const id=s.state().id;await store.trash(id);d.files.set('internal://files/unrelated.json','keep');
  const original=d.api.delete;let n=0;d.api.delete=o=>{if(++n===2)queueMicrotask(()=>o.fail('error',300));else original(o);};
  await assert.rejects(()=>store.purge(id,id));const items=await store.list(true);assert.equal(items[0].state,'deleting');
  await store.purge(id,id);assert.equal((await store.list(true)).length,0);assert.equal(d.files.get('internal://files/unrelated.json'),'keep');
});

test('duration stops without admitting an out-of-window callback and competing starts are refused',async()=>{
  const d=disk();let t=1000;const store=core.createStore(d.api,{now:()=>t});
  const a=store.start({durationSeconds:2}),b=store.start({durationSeconds:2});await assert.rejects(()=>b,/保存上一条/);const s=await a;
  t=1020;s.push({x:1,y:2,z:3});t=3000;assert.equal(s.push({x:4,y:5,z:6}),false);await settle();await settle();
  assert.equal(s.state().count,1);assert.equal(s.state().stop_reason,'duration');assert.equal(s.state().status,'sealed');
});

module.exports={disk,settle};
