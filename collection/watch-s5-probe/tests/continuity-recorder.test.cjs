const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const newer=path.join(__dirname,'../tools/build_continuity_recorder_source.cjs');
function staged(){
 const tmp=fs.realpathSync(os.tmpdir()),dir=fs.mkdtempSync(path.join(tmp,'imus5-continuity-test-'));
 try{require(fs.existsSync(newer)?newer:'../tools/build_precise_recorder_source.cjs').prepareStage(dir);
  return {core:require(path.join(dir,'src/common/research.js')),ux:fs.readFileSync(path.join(dir,'src/Probe/index.ux'),'utf8'),manifest:JSON.parse(fs.readFileSync(path.join(dir,'src/manifest.json')))};
 }finally{assert.equal(path.dirname(fs.realpathSync(dir)),tmp);fs.rmSync(dir,{recursive:true,force:true});}
}
async function rig(duration=10){
 const profile=staged(),files=new Map();let t=1000;
 const file={list:o=>o.success({fileList:[]}),writeText:o=>{files.set(o.uri,o.text);o.success();}};
 const s=await profile.core.createStore(file,{now:()=>t}).start({sensorPath:'generic',interval:'high',durationSeconds:duration});
 return {s,profile,files,time:v=>{t=v;},push:()=>s.push({x:0.125,y:2.5,z:9.75},'visible',t),objects:()=>[...files.values()].map(JSON.parse),tail:()=>[...files.values()].map(JSON.parse).find(o=>o.kind==='tail')};
}
test('ordinary pre-deadline 3s silence protection already works',async()=>{
 const r=await rig();r.push();r.time(4250);r.s.tick();assert.equal(r.tail().stop_reason,'sensor_silence');
});
test('delayed terminal tick cannot mislabel a long final silence as ordinary duration',async()=>{
 const r=await rig();r.push();r.time(11000);r.s.tick();const t=r.tail();
 assert.equal(t.stop_reason,'sensor_silence');assert.ok(t.quality.warnings.includes('sensor_silence_observed'));assert.equal(t.continuity_observation.terminal_gap_ms,10000);
});
test('manual stop preserves the requested reason and warns about final silence',async()=>{
 const r=await rig();r.push();r.time(5000);r.s.stop('manual');
 assert.equal(r.tail().stop_reason,'manual');assert.ok(r.tail().quality.warnings.includes('sensor_silence_observed'));
});
test('head records mode and fixed continuity policy before any sample',async()=>{
 const r=await rig(),head=r.objects().find(o=>o.kind==='head');r.s.stop('manual');
 assert.equal(head.metadata.sensor_path,'generic');assert.equal(head.metadata.continuity_policy.heartbeat_period_ms,1000);assert.equal(head.metadata.continuity_policy.silence_limit_ms,3000);
});
test('60s normal synthetic capture has real heartbeat events and final counts',async()=>{
 const r=await rig(60);
 for(let dt=0;dt<60000;dt+=250){r.time(1000+dt);r.push();r.s.tick();}
 r.time(61000);r.s.tick();const tail=r.tail(),events=r.objects().filter(o=>o.kind==='block').flatMap(o=>o.events).filter(e=>e.type==='capture_heartbeat');
 assert.equal(tail.stop_reason,'duration');assert.equal(tail.count,240);assert.equal(events.length,60);assert.equal(tail.continuity_observation.heartbeat_count,60);
 assert.equal(tail.continuity_observation.last_accepted_epoch_ms,60750);assert.equal(tail.continuity_observation.terminal_gap_ms,250);assert.equal(tail.continuity_observation.late_tick_count,0);
 assert.ok(!tail.quality.warnings.includes('event_overflow'));
});
test('late ticks produce one observed heartbeat and do not fabricate missed events',async()=>{
 const r=await rig();r.push();r.time(3000);r.push();r.s.tick();r.time(3100);r.s.stop('manual');
 const t=r.tail(),events=r.objects().filter(o=>o.kind==='block').flatMap(o=>o.events).filter(e=>e.type==='capture_heartbeat');
 assert.equal(events.length,1);assert.equal(t.continuity_observation.max_tick_gap_ms,2000);assert.equal(t.continuity_observation.late_tick_count,1);assert.ok(t.quality.warnings.includes('heartbeat_tick_delay'));
});
test('zero callbacks retain silence evidence without inventing a last callback',async()=>{
 const r=await rig();r.time(11000);r.s.tick();const t=r.tail();assert.equal(t.stop_reason,'sensor_silence');
 assert.equal(t.count,0);assert.equal(t.continuity_observation.last_accepted_epoch_ms,null);assert.ok(t.quality.warnings.includes('no_samples'));
});
test('actual page driver seals final counters and shows a visible interruption warning',async()=>{
 const profile=staged(),files=new Map(),unsubs=[];let t=1000,native;
 const file={list:o=>o.success({fileList:[]}),writeText:o=>{files.set(o.uri,o.text);o.success();}};
 const sensor={DATA_TYPES:{ACCELEROMETER:2},subscribe:o=>{native=o;return 129;},unsubscribe:h=>unsubs.push(h)};
 const ctx={sensor,file,research:{createStore:f=>profile.core.createStore(f,{now:()=>t})},sensorCapture:require('../variants/precise-recorder/src/common/sensor-capture.js'),
  inputProbe:require('../variants/input-probe/src/common/input-probe.js'),storageDiagnostic:{},legacyCore:{},transfer:{},interconnect:{},Date:{now:()=>t},Math,JSON,Promise,setInterval:()=>1,clearInterval(){}};
 vm.createContext(ctx);vm.runInContext(profile.ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result='),ctx);
 const p=Object.assign({},ctx.result.private,ctx.result);p.onInit();p.durationSeconds=10;p.startRecording();await new Promise(setImmediate);
 native.callback({ACCELEROMETER:{x:0.125,y:2.5,z:9.75}});t=11000;
 native.callback({ACCELEROMETER:{x:0.25,y:2.5,z:9.75}});await new Promise(setImmediate);
 const tail=[...files.values()].map(JSON.parse).find(o=>o.kind==='tail');
 assert.equal(tail.count,1);assert.equal(tail.stop_reason,'sensor_silence');assert.equal(tail.acquisition_observation.callback_count,2);
 assert.equal(tail.acquisition_observation.accepted_rows,1);assert.equal(tail.acquisition_observation.cleanup.status,'unsubscribe_returned');assert.deepEqual(unsubs,[129]);
 assert.equal(p.alert,true);assert.match(p.status,/中断/);assert.equal(p.recording,false);
});
