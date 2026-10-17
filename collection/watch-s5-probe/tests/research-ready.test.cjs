const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),tmp=fs.realpathSync(os.tmpdir()),builder=path.join(root,'tools/build_research_ready_source.cjs');
const stage=fs.mkdtempSync(path.join(tmp,'imus5-ready-test-'));let sources,manifest;
try{
 require(fs.existsSync(builder)?builder:path.join(root,'tools/build_lifecycle_reporting_source.cjs')).prepareStage(stage);
 sources=Object.fromEntries(['research.js','record-catalog.js','sensor-capture.js','screen-guard.js','directory-entries.js','runtime-timing.js','continuity-observer.js'].map(n=>[n,fs.readFileSync(path.join(stage,'src/common',n),'utf8')]));
 sources.page=fs.readFileSync(path.join(stage,'src/Probe/index.ux'),'utf8');manifest=JSON.parse(fs.readFileSync(path.join(stage,'src/manifest.json')));
}finally{assert.equal(path.dirname(fs.realpathSync(stage)),tmp);fs.rmSync(stage,{recursive:true,force:true});}
const settle=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
function rig(){
 let clock=1000000,seq=0,native,unsubs=0;const files=new Map(),timers=new Map(),intervals=new Map(),pending=[],calls={list:0,read:0,write:0,delete:0},screens=[];
 const setTimeoutFake=(fn,delay)=>{const id=++seq;timers.set(id,{fn,due:clock+delay,delay});return id;};
 const cache={};function load(name){if(cache[name])return cache[name];const mod={exports:{}};cache[name]=mod.exports;
  const context={module:mod,require:n=>load(path.basename(n)),Date:{now:()=>clock},setTimeout:setTimeoutFake,clearTimeout:id=>timers.delete(id),Promise,Math,JSON};
  vm.runInNewContext(sources[name],context,{filename:name});cache[name]=mod.exports;return mod.exports;}
 const file={list:o=>{calls.list++;if(r.delayList)pending.push(o);else o.success({fileList:[...files.keys()].map(uri=>({uri}))});},
  readText:o=>{calls.read++;files.has(o.uri)?o.success({text:files.get(o.uri)}):o.fail('missing',404);},
  writeText:o=>{calls.write++;if(r.failWrite){r.failWrite=false;o.fail('controlled',5);return;}files.set(o.uri,o.text);o.success();},delete:o=>{calls.delete++;files.delete(o.uri);o.success();}};
 const sensor={DATA_TYPES:{ACCELEROMETER:2},subscribe:o=>{native=o;return 129;},unsubscribe:()=>unsubs++};
 const core=load('research.js'),catalog=load('record-catalog.js');
 const context={file,sensor,research:{...core,createStore:f=>core.createStore(f,{now:()=>clock})},recordCatalog:catalog,sensorCapture:load('sensor-capture.js'),screenGuard:load('screen-guard.js'),
  inputProbe:{},storageDiagnostic:{},legacyCore:{},transfer:{},interconnect:{},Date:{now:()=>clock},Math,JSON,Promise,
  setTimeout:setTimeoutFake,clearTimeout:id=>timers.delete(id),setInterval:fn=>{const id=++seq;intervals.set(id,fn);return id;},clearInterval:id=>intervals.delete(id),
  require:()=>({setKeepScreenOn:o=>{screens.push(o.keepScreenOn);o.success();}})};
 vm.createContext(context);vm.runInContext(sources.page.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result='),context);
 const page=Object.assign({},context.result.private,context.result);
 const r={page,files,calls,screens,pending,delayList:false,clock:()=>clock,unsubs:()=>unsubs,
  at:t=>{clock=t;},emit:()=>native.callback({ACCELEROMETER:{x:.125,y:-.25,z:9.75}}),tick:()=>{for(const f of [...intervals.values()])f();},
  async advance(target){for(;;){const entries=[...timers].filter(([id,t])=>t.due<=target).sort((a,b)=>a[1].due-b[1].due);if(!entries.length)break;
    const[id,t]=entries[0];timers.delete(id);clock=t.due;t.fn();await settle();}clock=target;await settle();},
  parts:()=>[...files.values()].map(JSON.parse),tail:()=>r.parts().find(x=>x.kind==='tail')};
 page.onInit();return r;
}
async function record(interval,gaps,until=7000,first=0){
 const r=rig();r.page.interval=interval;r.page.durationSeconds=600;r.page.startRecording();await settle();
 const agenda=[];for(let t=first,i=0;t<=until;i++,t+=Array.isArray(gaps)?gaps[i%gaps.length]:gaps)agenda.push({at:t,emit:true});
 for(let t=250;t<=until;t+=250)agenda.push({at:t,emit:false});agenda.sort((a,b)=>a.at-b.at||Number(b.emit)-Number(a.emit));
 let delivered=0;for(const e of agenda){r.at(1000000+e.at);if(e.emit){if(r.page.recording)delivered++;r.emit();}else r.tick();await settle();}
 return {r,delivered};
}
function addSession(r,i=0){const id=String(1000+i)+'_abcdef',p='internal://files/s5r_'+id;
 r.files.set(p+'_head.json',JSON.stringify({kind:'head',schema_version:2,session_id:id,started_epoch_ms:1000}));
 r.files.set(p+'_b0000.json','{}');r.files.set(p+'_tail.json',JSON.stringify({kind:'tail',session_id:id,blocks:1,persisted:37,stopped_epoch_ms:2000,quality:{warnings:[]}}));return id;}
test('independent candidate declares startup engineering policy and retains four ordinary capabilities',async()=>{
 assert.equal(manifest.versionName,'0.4.13');assert.equal(manifest.versionCode,22);
 assert.deepEqual(JSON.parse(JSON.stringify(manifest.features.map(f=>f.name).sort())),['system.brightness','system.file','system.interconnect','system.sensor']);
 const{r}=await record('high',60,3000);r.page.stopRecording();await settle();
 assert.equal(r.parts().find(x=>x.kind==='head').metadata.startup_rate_policy.minimum_arrival_per_second,10);
 assert.equal(r.tail().startup_rate_observation.status,'not_checked_before_stop');
});
for(const gaps of [200,[10,390]])test('slow high stops once after5s, preserves every arrived row and cleanup: '+gaps,async()=>{
 const{r,delivered}=await record('high',gaps);const tail=r.tail();assert.ok(tail);assert.equal(tail.stop_reason,'startup_rate_low');
 assert.equal(tail.count,delivered);assert.equal(tail.persisted,delivered);assert.equal(tail.startup_rate_observation.status,'stopped_slow');
 assert.ok(tail.quality.warnings.includes('startup_rate_low'));assert.equal(r.unsubs(),1);assert.deepEqual(r.screens,[true,false]);
 assert.equal(r.parts().filter(x=>x.kind==='head').length,1);assert.equal(r.parts().filter(x=>x.kind==='tail').length,1);
});
test('normal high continues beyond5s, one inclusive minute preserves1001 rows and terminal report',async()=>{
 const{r}=await record('high',60,60000);assert.equal(r.page.recording,true);r.page.stopRecording();await settle();
 assert.equal(r.tail().count,1001);assert.equal(r.tail().startup_rate_observation.status,'passed');assert.equal(r.tail().acquisition_observation.accepted_rows,1001);
});
for(const interval of ['mid','low'])test(interval+' is never stopped by the high-only guard',async()=>{
 const{r}=await record(interval,200);assert.equal(r.page.recording,true);r.page.stopRecording();await settle();
 assert.equal(r.tail().stop_reason,'manual');assert.equal(r.tail().startup_rate_observation.status,'not_applicable');
});
test('late first callbacks cannot turn an insufficient startup span into a pass',async()=>{
 const{r}=await record('high',60,6000,2700);assert.equal(r.tail().stop_reason,'startup_rate_unconfirmed');
 assert.equal(r.tail().startup_rate_observation.status,'insufficient');assert.equal(r.tail().startup_rate_observation.callback_span_ms<2500,true);
});
test('failed browse retains the old list as stale, with no write or delete',async()=>{
 const r=rig();addSession(r);r.page.showRecords();await settle();assert.equal(r.page.recordPosition,'1 / 1');r.delayList=true;r.page.reloadRecords();await settle();await r.advance(1008000);
 assert.equal(r.page._items.length,1);assert.equal(r.page._store.catalogState().source,'stale');assert.match(r.page.catalogNote,/上次|旧/);
 assert.doesNotMatch(r.page.capacityText,/已满|0\/40/);assert.equal(r.calls.write+r.calls.delete,0);
});
test('without an old list, failure shows unknown count rather than zero records',async()=>{
 const r=rig();r.delayList=true;r.page.showRecords();await settle();await r.advance(1008000);
 assert.match(r.page.capacityText,/未知/);assert.notEqual(r.page.recordPosition,'0 / 0');assert.equal(r.calls.write+r.calls.delete,0);
});
test('a stale display cannot bypass fresh inventory before export',async()=>{
 const r=rig(),id=addSession(r);await r.page._store.list(false);r.delayList=true;
 const refresh=r.page._store.list(false).then(x=>x,e=>e);await r.advance(1008000);await refresh;
 const before=r.calls.list;const inventory=r.page._store.inventory(id).then(x=>({value:x}),e=>({error:e}));await settle();assert.equal(r.calls.list,before+1);
 await r.advance(1017000);r.pending.at(-1).success({fileList:[...r.files.keys()].map(uri=>({uri}))});await settle();
 assert.ok((await inventory).value);assert.equal(r.calls.write+r.calls.delete,0);
});
test('core live reads tolerate9s but retain a30s engineering terminal wait',async()=>{
 const r=rig(),id=addSession(r);r.delayList=true;
 let result;const request=r.page._store.inventory(id).then(x=>{result=x;},e=>{result=e;});await settle();await r.advance(1009000);
 assert.equal(result,undefined);r.pending[0].success({fileList:[...r.files.keys()].map(uri=>({uri}))});await request;assert.equal(result.id,id);
 const later=r.page._store.inventory(id).then(x=>x,e=>e);await settle();await r.advance(1039000);assert.match((await later).message,/超时/);
});
test('outer export read waits30s and cancellation invalidates late success',async()=>{
 const r=rig(),p=r.page,op={generation:1,releasing:false};p._exportScreen=op;p._exportScreenGeneration=1;let resolve,result;
 const wait=p.exportFileRead(op,'inventory',()=>new Promise(ok=>{resolve=ok;})).then(x=>{result=x;},e=>{result=e;});
 await r.advance(1009000);assert.equal(result,undefined);resolve('kept');await wait;assert.equal(result,'kept');
 const wait2=p.exportFileRead(op,'readPart',()=>new Promise(()=>{})).then(x=>x,e=>e);await r.advance(1039000);assert.match((await wait2).message,/超时/);
 const wait3=p.exportFileRead(op,'inventory',()=>new Promise(ok=>{resolve=ok;})).then(x=>x,e=>e);p.cancelExportFiles(op);assert.match((await wait3).message,/结束/);resolve('late');await settle();
 assert.equal(op.fileObservation.cancelled,1);assert.equal(op.fileObservation.timeout_ms,30000);
});
module.exports={rig,record,addSession,settle,sources};
test('save retry before startup check seals an explicitly unchecked observation',async()=>{
 const{r}=await record('high',60,3000);r.failWrite=true;r.page.stopRecording();await settle();assert.equal(r.page.retryable,true);
 r.page.retrySave();await settle();assert.ok(r.tail());assert.equal(r.tail().startup_rate_observation.status,'not_checked_before_stop');
 assert.ok(r.tail().quality.warnings.includes('storage_error'));
});
test('a late old directory result cannot replace a newer explicit scan',async()=>{
 const r=rig();addSession(r);r.page.showRecords();await settle();r.delayList=true;
 const p=r.page._store.list(false).then(x=>x,e=>e);await r.advance(1008000);await p;const old=r.pending[0];
 r.delayList=false;addSession(r,1);await r.page._store.list(false);assert.equal(r.page._store.catalogState().total,2);
 old.success({fileList:[]});await settle();assert.equal(r.page._store.catalogState().total,2);assert.equal(r.page._store.catalogState().source,'fresh');
});
test('hidden/destroyed slow startup preserves samples and releases screen without resubscribing',async()=>{
 for(const action of ['onHide','onDestroy']){const{r,delivered}=await record('high',200,3000);r.page[action]();await settle();
  assert.equal(r.tail().count,delivered);assert.equal(r.tail().startup_rate_observation.status,'not_checked_before_stop');assert.equal(r.unsubs(),1);assert.deepEqual(r.screens,[true,false]);}
});
