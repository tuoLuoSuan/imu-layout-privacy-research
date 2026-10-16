const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const capture=require('../variants/precise-recorder/src/common/sensor-capture.js');
function staged(){
 const base=fs.realpathSync(os.tmpdir()),dir=fs.mkdtempSync(path.join(base,'imus5-precise-test-'));
 try{require('../tools/build_precise_recorder_source.cjs').prepareStage(dir);return {core:require(path.join(dir,'src/common/research.js')),ux:fs.readFileSync(path.join(dir,'src/Probe/index.ux'),'utf8'),manifest:JSON.parse(fs.readFileSync(path.join(dir,'src/manifest.json')))};}
 finally{assert.equal(path.dirname(fs.realpathSync(dir)),base);fs.rmSync(dir,{recursive:true,force:true});}
}
function disk(sync){const files=new Map();const dispatch=fn=>sync?fn():queueMicrotask(fn);return {files,api:{
 list:o=>dispatch(()=>o.success({fileList:[...files.keys()].map(uri=>({uri:uri.replace('files/','files//')}))})),
 writeText:o=>dispatch(()=>{files.set(o.uri,o.text);o.success();}),readText:o=>dispatch(()=>o.success({text:files.get(o.uri)}))}};}
const settle=()=>new Promise(setImmediate);
async function recording(sync,nativeFail){
 const profile=staged(),d=disk(sync);let t=1000,driver,session,nativeOptions;const unsubs=[];
 const sensor={DATA_TYPES:{ACCELEROMETER:2},subscribe(o){nativeOptions=o;if(nativeFail)o.fail('native failure exact',203);return 129;},unsubscribe:h=>unsubs.push(h)};
 session=await profile.core.createStore(d.api,{now:()=>t}).start({sensorPath:'generic',interval:'high',durationSeconds:10},s=>{
  if(s.status!=='recording'&&driver)driver.stop();
 });
 driver=capture.create(sensor,{now:()=>t,onValue:(v,at)=>session.push(v,'visible',at),onFail:e=>{session.event('sensor_fail',e.message);session.stop('sensor_fail');},
  beforeCallback:()=>session.holdAcquisition(),afterCallback:()=>session.releaseAcquisition(),onChange:r=>{if(session.state().status!=='sealed')session.setAcquisitionObservation(r);}});
 session.holdAcquisition();try{driver.start({sensorPath:'generic',interval:'high'});}finally{session.releaseAcquisition();}
 return {profile,d,session,driver,sensor,unsubs,time:v=>{t=v;},emit:v=>nativeOptions.callback(v)};
}
test('generic head metadata uses actual mode/interval; mixed names refused and existing legacy default remains available',async()=>{
 const {core,manifest}=staged(),d=disk();assert.equal(manifest.versionName,'0.4.1');assert.equal(manifest.versionCode,10);
 const s=await core.createStore(d.api,{now:()=>1000}).start({sensorPath:'generic',durationSeconds:10});
 const head=[...d.files.values()].map(JSON.parse).find(p=>p.kind==='head');assert.equal(head.metadata.requested_interval,'high');assert.equal(head.metadata.acquisition_api,'@system.sensor.subscribe');assert.equal(head.metadata.app_version,'0.4.1');s.stop('manual');await settle();
 await assert.rejects(()=>core.createStore(disk().api).start({sensorPath:'generic',interval:'game'}),/设置/);
 await assert.rejects(()=>core.createStore(disk().api).start({sensorPath:'legacy',interval:'high'}),/设置/);
});
test('ten-second synthetic decimal recording saves multiple blocks and final observation exactly matches all rows',async()=>{
 const r=await recording(false,false);for(let i=0;i<500;i++){r.time(1000+i*20);r.emit({ACCELEROMETER:{x:i+0.123456789,y:-2.5,z:9.8}});}r.time(11000);r.session.tick();await settle();await settle();
 const parts=[...r.d.files.values()].map(JSON.parse),blocks=parts.filter(p=>p.kind==='block').sort((a,b)=>a.index-b.index),rows=blocks.flatMap(p=>p.rows),tail=parts.find(p=>p.kind==='tail');
 assert.equal(rows.length,500);assert.ok(blocks.length>=4);assert.equal(rows[0][2],0.123456789);assert.equal(rows[0][1],1000);assert.equal(tail.persisted,500);
 assert.equal(tail.acquisition_observation.accepted_rows,500);assert.equal(tail.acquisition_observation.fractional_xyz_scalars,1500);assert.equal(tail.acquisition_observation.cleanup.handle,129);assert.deepEqual(r.unsubs,[129]);
 const store=r.profile.core.createStore(r.d.api);assert.equal((await store.list(false))[0].count,500);const before=[...r.d.files];const inv=await store.inventory(tail.session_id);
 for(const f of inv.files)await store.readPart(inv.id,f);assert.deepEqual([...r.d.files],before);
});
test('synchronous native fail cannot seal before returned-handle cleanup; zero-row failure remains exportable',async()=>{
 const r=await recording(true,true);await settle();const tail=[...r.d.files.values()].map(JSON.parse).find(p=>p.kind==='tail');
 assert.ok(tail);assert.equal(tail.count,0);assert.equal(tail.stop_reason,'sensor_fail');assert.equal(tail.acquisition_observation.error.message,'native failure exact');assert.equal(tail.acquisition_observation.cleanup.handle,129);assert.deepEqual(r.unsubs,[129]);
});
test('late callback at duration is not counted as an accepted row and seal barrier captures final counters',async()=>{
 const r=await recording(true,false);r.emit({ACCELEROMETER:{x:0.125,y:1,z:2}});r.time(11001);r.emit({ACCELEROMETER:{x:0.25,y:1,z:2}});await settle();
 const tail=[...r.d.files.values()].map(JSON.parse).find(p=>p.kind==='tail');assert.equal(tail.count,1);assert.equal(tail.acquisition_observation.callback_count,2);assert.equal(tail.acquisition_observation.accepted_rows,1);assert.equal(tail.acquisition_observation.first_accepted_callback_epoch_ms,1000);
});
test('sealing hold is balanced and observation report cannot exceed its bound',async()=>{
 const {core}=staged(),d=disk(true);const s=await core.createStore(d.api,{now:()=>1000}).start({sensorPath:'generic',durationSeconds:2});
 s.holdAcquisition();s.stop('manual');assert.equal(s.state().status,'stopping');assert.throws(()=>s.setAcquisitionObservation({x:'a'.repeat(33000)}),/boundary/);s.setAcquisitionObservation({status:'stopped'});s.releaseAcquisition();assert.equal(s.state().status,'sealed');assert.throws(()=>s.releaseAcquisition(),/hold/);
});
test('unsubscribe exception is a reported quality warning, not a silent successful stop',async()=>{
 const r=await recording(true,false);r.emit({ACCELEROMETER:{x:0.125,y:2,z:3}});r.sensor.unsubscribe=()=>{throw Error('native unsubscribe failed');};r.session.stop('manual');await settle();
 const tail=[...r.d.files.values()].map(JSON.parse).find(p=>p.kind==='tail');assert.ok(tail.quality.warnings.includes('sensor_cleanup_unconfirmed'));assert.equal(tail.acquisition_observation.cleanup.error.message,'native unsubscribe failed');
});
function page(){
 const profile=staged(),ctx={sensorCapture:capture,inputProbe:require('../variants/input-probe/src/common/input-probe.js'),research:profile.core,sensor:{},file:{},storageDiagnostic:{},legacyCore:{},transfer:{},interconnect:{},Date,Math,JSON,Promise,setInterval:()=>1,clearInterval(){}};
 vm.createContext(ctx);vm.runInContext(profile.ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result='),ctx);
 const p=Object.assign({},ctx.result.private,ctx.result);p.onInit();return {p,ux:profile.ux};
}
test('UI defaults generic/high, mode switch resets only its requested interval, and busy gate blocks changes',()=>{
 const {p,ux}=page();assert.match(ux,/回调到达/);assert.equal(p.interval,'high');assert.equal(p._lists[6][p._values[6]],'generic');
 p.settingIndex=6;p.changeValue(1);assert.equal(p.interval,'game');assert.equal(p._lists[6][p._values[6]],'legacy');p.settingIndex=1;p.changeValue(1);assert.equal(p.interval,'ui');
 p.recording=true;p.settingIndex=6;p.changeValue(1);assert.equal(p._lists[6][p._values[6]],'legacy');p.recording=false;p.changeValue(1);assert.equal(p.interval,'high');assert.equal(p.settingValue,'通用入口');
});
