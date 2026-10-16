const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const root=path.join(__dirname,'..'),builder=path.join(root,'tools/build_foreground_recorder_source.cjs');
function staged(){
 const base=fs.realpathSync(os.tmpdir()),dir=fs.mkdtempSync(path.join(base,'imus5-foreground-test-'));
 try{
  require(fs.existsSync(builder)?builder:path.join(root,'tools/build_continuity_recorder_source.cjs')).prepareStage(dir);
  return {core:require(path.join(dir,'src/common/research.js')),ux:fs.readFileSync(path.join(dir,'src/Probe/index.ux'),'utf8'),
   manifest:JSON.parse(fs.readFileSync(path.join(dir,'src/manifest.json')))};
 }finally{assert.equal(path.dirname(fs.realpathSync(dir)),base);fs.rmSync(dir,{recursive:true,force:true});}
}
async function settle(){await new Promise(setImmediate);await new Promise(setImmediate);}
function rig(options={}){
 const profile=staged(),files=new Map(),calls=[],unsubs=[],timers=new Map();let time=1000,native=null,timerId=0,loads=0;
 const brightness={setKeepScreenOn:o=>{calls.push(o);if(options.throwCall)throw Error('native screen error');if(options.sync)o.success();}};
 const file={list:o=>o.success({fileList:[]}),writeText:o=>{if(options.failHead&&/_head\.json$/.test(o.uri)){o.fail('disk',5);return;}files.set(o.uri,o.text);o.success();}};
 const sensor={DATA_TYPES:{ACCELEROMETER:2},subscribe:o=>{native=o;if(options.sensorFail)o.fail('sensor',9);return 129;},unsubscribe:h=>unsubs.push(h)};
 const context={sensor,file,research:{createStore:f=>profile.core.createStore(f,{now:()=>time})},
  sensorCapture:require('../variants/precise-recorder/src/common/sensor-capture.js'),
  inputProbe:require('../variants/input-probe/src/common/input-probe.js'),storageDiagnostic:{},legacyCore:{},transfer:{},interconnect:{},
  Date:{now:()=>time},Math,JSON,Promise,setInterval:()=>1,clearInterval(){},
  setTimeout:fn=>{const id=++timerId;timers.set(id,fn);return id;},clearTimeout:id=>timers.delete(id),
  require:n=>{assert.equal(n,'@system.brightness');loads++;if(options.missing)throw Error('screen module unavailable');return brightness;}};
 const guard=path.join(root,'variants/foreground-recorder/src/common/screen-guard.js');if(fs.existsSync(guard))context.screenGuard=require(guard);
 vm.createContext(context);vm.runInContext(profile.ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result='),context);
 const page=Object.assign({},context.result.private,context.result);page.onInit();page.durationSeconds=10;
 return {page,profile,files,calls,unsubs,timers,loads:()=>loads,native:()=>native,time:t=>{time=t;},
  tail:()=>[...files.values()].map(JSON.parse).find(o=>o.kind==='tail'),
  head:()=>[...files.values()].map(JSON.parse).find(o=>o.kind==='head'),
  push:()=>native.callback({ACCELEROMETER:{x:0.125,y:2.5,z:9.75}}),
  fireTimers:()=>{for(const [id,fn] of [...timers]){timers.delete(id);fn();}}};
}
async function start(r){r.page.startRecording();await settle();assert.equal(r.calls[0].keepScreenOn,true);r.calls[0].success();await settle();}

test('actual page must acquire screen hold before any recording file or subscription',async()=>{
 const r=rig();assert.equal(r.loads(),0);r.page.startRecording();await settle();
 assert.equal(r.calls.length,1,'a real screen hold request is required');assert.equal(r.calls[0].keepScreenOn,true);
 assert.equal(r.files.size,0);assert.equal(r.native(),null);
 r.calls[0].success();await settle();assert.ok(r.head());assert.ok(r.native());
 assert.equal(r.head().metadata.screen_policy.mode,'foreground_keep_awake');
 r.page.stopRecording();await settle();r.calls[1].success();await settle();
});
test('screen request failure blocks capture and leaves a visible error',async()=>{
 const r=rig();r.page.startRecording();await settle();r.calls[0].fail('denied',403);await settle();
 assert.equal(r.files.size,0);assert.equal(r.native(),null);assert.equal(r.page.alert,true);assert.match(r.page.status,/保亮/);
});
test('missing ordinary screen module is caught only when recording is requested',async()=>{
 const r=rig({missing:true});assert.equal(r.loads(),0);r.page.startRecording();await settle();
 assert.equal(r.loads(),1);assert.equal(r.files.size,0);assert.equal(r.native(),null);assert.equal(r.page.alert,true);
});
test('rapid repeated start emits one acquire request',async()=>{
 const r=rig();r.page.startRecording();r.page.startRecording();await settle();assert.equal(r.calls.length,1);
 r.page.onHide();r.calls[0].success();await settle();for(const c of r.calls.slice(1))c.success();await settle();assert.equal(r.files.size,0);
});
test('duplicate successful acquire callback cannot turn off a running hold',async()=>{
 const r=rig();await start(r);r.calls[0].success();await settle();assert.equal(r.calls.length,1);
 r.push();r.page.stopRecording();await settle();r.calls[1].success();await settle();assert.equal(r.tail().screen_observation.release.status,'success');
});
test('manual stop seals only after screen release observation and native cancellation',async()=>{
 const r=rig();await start(r);r.push();r.time(1100);r.page.stopRecording();await settle();
 assert.equal(r.calls.length,2);assert.equal(r.calls[1].keepScreenOn,false);assert.equal(r.tail(),undefined);
 r.calls[1].success();await settle();const tail=r.tail();assert.equal(tail.stop_reason,'manual');
 assert.equal(tail.screen_observation.acquire.status,'success');assert.equal(tail.screen_observation.release.status,'success');
 assert.equal(tail.acquisition_observation.accepted_rows,1);assert.deepEqual(r.unsubs,[129]);
});
test('failed release is retained as a quality warning and screen observation',async()=>{
 const r=rig();await start(r);r.push();r.page.stopRecording();await settle();r.calls[1].fail('cannot release',9);await settle();
 assert.equal(r.tail().screen_observation.release.status,'failed');assert.ok(r.tail().quality.warnings.includes('screen_release_unconfirmed'));assert.equal(r.page.alert,true);
});
test('release callback timeout seals with explicit unknown cleanup status',async()=>{
 const r=rig();await start(r);r.push();r.page.stopRecording();await settle();r.fireTimers();await settle();
 assert.equal(r.tail().screen_observation.release.status,'timeout');assert.ok(r.tail().quality.warnings.includes('screen_release_unconfirmed'));
});
test('leaving during acquire blocks file creation and closes a late successful hold',async()=>{
 const r=rig();r.page.startRecording();await settle();r.page.onHide();r.calls[0].success();await settle();
 assert.ok(r.calls.some(c=>c.keepScreenOn===false));for(const c of r.calls.filter(c=>!c.keepScreenOn))c.success();await settle();
 assert.equal(r.files.size,0);assert.equal(r.native(),null);
});
test('hide then destroy stops one foreground session and does not duplicate release',async()=>{
 const r=rig();await start(r);r.push();r.page.onHide();r.page.onDestroy();await settle();
 assert.equal(r.calls.filter(c=>!c.keepScreenOn).length,1);r.calls[1].success();await settle();
 assert.equal(r.tail().stop_reason,'page_hide');assert.ok(r.tail().quality.warnings.includes('page_hide'));assert.deepEqual(r.unsubs,[129]);
});
test('synchronous native callbacks remain reentrancy-safe',async()=>{
 const r=rig({sync:true});r.page.startRecording();await settle();r.push();r.page.stopRecording();await settle();
 assert.equal(r.tail().screen_observation.release.status,'success');assert.equal(r.tail().count,1);assert.equal(r.calls.length,2);
});
test('acquire timeout prevents capture and a late success is switched off',async()=>{
 const r=rig();r.page.startRecording();await settle();r.fireTimers();await settle();r.calls[0].success();await settle();
 assert.equal(r.files.size,0);assert.equal(r.native(),null);assert.equal(r.page.alert,true);assert.ok(r.calls.some(c=>c.keepScreenOn===false));
 for(const c of r.calls.filter(c=>!c.keepScreenOn))c.success();await settle();
});
test('head write failure releases the acquired screen without starting the sensor',async()=>{
 const r=rig({failHead:true});await start(r);assert.equal(r.native(),null);assert.equal(r.calls[1].keepScreenOn,false);r.calls[1].success();await settle();
 assert.equal(r.page.alert,true);assert.equal(r.files.size,0);
});
test('synchronous sensor failure still seals cancellation and screen cleanup observations',async()=>{
 const r=rig({sensorFail:true});await start(r);assert.equal(r.tail(),undefined);r.calls[1].success();await settle();
 assert.equal(r.tail().stop_reason,'sensor_fail');assert.equal(r.tail().screen_observation.release.status,'success');assert.deepEqual(r.unsubs,[129]);
});
test('source profile adds only the documented screen capability and keeps old scope',()=>{
 const p=staged();assert.equal(p.manifest.versionName,'0.4.3');assert.equal(p.manifest.versionCode,12);
 assert.deepEqual(p.manifest.features.map(f=>f.name).sort(),['system.brightness','system.file','system.interconnect','system.sensor']);
 assert.match(p.ux,/录制期间保持亮屏/);assert.doesNotMatch(p.ux,/getRecentData|system\.audio|system\.geolocation/);
});
