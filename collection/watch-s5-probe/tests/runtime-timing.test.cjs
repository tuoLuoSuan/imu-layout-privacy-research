const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const root=path.resolve(__dirname,'..'),candidate=path.join(root,'tools/build_runtime_timing_source.cjs');
const temp=fs.realpathSync(os.tmpdir()),stage=fs.mkdtempSync(path.join(temp,'imus5-runtime-test-'));
let core,driver,timing,ux;
try{
 require(fs.existsSync(candidate)?candidate:path.join(root,'tools/build_progressive_recorder_source.cjs')).prepareStage(stage);
 core=require(path.join(stage,'src/common/research.js'));driver=require(path.join(stage,'src/common/sensor-capture.js'));
 const tp=path.join(stage,'src/common/runtime-timing.js');if(fs.existsSync(tp))timing=require(tp);
 ux=fs.readFileSync(path.join(stage,'src/Probe/index.ux'),'utf8');
}finally{assert.equal(path.dirname(fs.realpathSync(stage)),temp);fs.rmSync(stage,{recursive:true,force:true});}
async function rig(){
 let t=1000000,cost=0,held=false;const files=new Map(),acks=[];
 const file={list:o=>o.success({fileList:[]}),writeText:o=>{t+=cost;const done=()=>{files.set(o.uri,o.text);o.success();};if(held)acks.push(done);else done();}};
 const session=await core.createStore(file,{now:()=>t}).start({durationSeconds:600,interval:'high',sensorPath:'generic'});
 return {session,files,now:()=>t,advance:n=>{t+=n;},cost:n=>{cost=n;},hold:v=>{held=v;},ack:()=>acks.shift()(),objects:()=>[...files.values()].map(JSON.parse)};
}
test('independent candidate declares bounded timing and exposes it only through the internal session interface',async()=>{
 const r=await rig(),head=r.objects()[0];assert.equal(head.metadata.app_version,'0.4.10');
 assert.equal(head.metadata.runtime_timing_policy.schema_version,1);assert.equal(typeof r.session.runtimeTiming,'function');
 assert.ok(timing);assert.equal(r.session.state().runtime_timing_observation,undefined);
 assert.match(ux,/runtimeTiming:s.runtimeTiming\(\)/);assert.doesNotMatch(ux.split('</template>')[0],/onclick="(?:openInput|inspectStorage)"/);
});
test('driver body cost and time between checkpoints remain distinct observations',()=>{
 assert.ok(timing,'timing module required');let t=1000,cb;const obs=timing.create(()=>t);
 const sensor={DATA_TYPES:{ACCELEROMETER:2},subscribe:o=>{cb=o.callback;return 129;},unsubscribe:()=>{}};
 const d=driver.create(sensor,{now:()=>t,runtimeTiming:obs,onValue:()=>{t+=1200;return true;}});
 d.start({sensorPath:'generic',interval:'high'});cb({ACCELEROMETER:{x:.1,y:.2,z:9.8}});
 t+=1510;cb({ACCELEROMETER:{x:.1,y:.2,z:9.8}});d.stop();
 const s=obs.snapshot();assert.equal(s.metrics.callback_body_ms.max_ms,1200);assert.equal(s.metrics.callback_between_ms.max_ms,1510);
 assert.equal(s.metrics.callback_body_ms.count,2);assert.equal(s.metrics.callback_body_ms.pending,0);
});
test('synchronous write call and later ACK have separate bounded spans',async()=>{
 const r=await rig();assert.equal(typeof r.session.runtimeTiming,'function');r.cost(40);r.hold(true);
 for(let i=0;i<128;i++){r.advance(60);r.session.push({x:.1,y:.2,z:9.8},'visible',r.now());}
 let s=r.session.runtimeTiming().snapshot();assert.equal(s.metrics.write_call_ms.max_ms,40);assert.equal(s.metrics.write_ack_ms.pending,1);
 r.advance(160);r.ack();s=r.session.runtimeTiming().snapshot();assert.equal(s.metrics.write_ack_ms.max_ms,200);assert.equal(s.metrics.write_ack_ms.pending,0);
 r.hold(false);r.session.stop('manual');
});
test('tail cutoff honestly preserves an in-progress final tick without adding a timer',async()=>{
 const r=await rig();r.session.push({x:.1,y:.2,z:9.8},'visible',r.now());
 for(let i=0;i<2400;i++){r.advance(250);if(i%4===0)r.session.push({x:.1,y:.2,z:9.8},'visible',r.now());r.session.tick();}
 const tail=r.objects().find(o=>o.kind==='tail');assert.ok(tail.runtime_timing_observation);assert.equal(tail.runtime_timing_observation.cutoff,'tail_construction');
 assert.equal(tail.runtime_timing_observation.metrics.tick_body_ms.pending,1);assert.equal(tail.count,tail.persisted);
});
test('retention stays bounded and wall-clock rollback does not fabricate a duration',()=>{
 assert.ok(timing);let t=1000;const obs=timing.create(()=>t);
 for(let i=0;i<10000;i++){const at=obs.begin('notify_body_ms');t+=i%30;obs.end('notify_body_ms',at,t,i);}
 const at=obs.begin('notify_body_ms');obs.end('notify_body_ms',at,at-1,1);
 const s=obs.snapshot(),m=s.metrics.notify_body_ms;assert.equal(m.count,10000);assert.equal(m.invalid,1);assert.equal(m.pending,0);
 assert.equal(m.top.length,5);assert.equal(m.histogram.reduce((a,b)=>a+b,0),m.count);assert.ok(JSON.stringify(s).length<12000);
});
test('one-second sample gap warning, storage and heartbeat gates remain active',async()=>{
 const r=await rig();r.session.push({x:.1,y:.2,z:9.8},'visible',r.now());r.advance(1000);r.session.tick();r.advance(510);r.session.push({x:.1,y:.2,z:9.8},'visible',r.now());r.session.stop('manual');
 const tail=r.objects().find(o=>o.kind==='tail');assert.ok(tail.runtime_timing_observation);assert.deepEqual(tail.quality.warnings,['callback_gap_over_1s']);
 assert.equal(tail.count,2);assert.equal(tail.quality.max_gap_ms,1510);assert.equal(r.objects()[0].metadata.storage_policy.timed_flush_ms,8000);
});
