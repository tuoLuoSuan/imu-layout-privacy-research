const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const root=path.resolve(__dirname,'..'),candidate=path.join(root,'tools/build_long_recorder_source.cjs');
const base=fs.realpathSync(os.tmpdir()),stage=fs.mkdtempSync(path.join(base,'imus5-long-test-'));
let core,ux;
try{
  require(fs.existsSync(candidate)?candidate:path.join(root,'tools/build_clean_interface_source.cjs')).prepareStage(stage);
  core=require(path.join(stage,'src/common/research.js'));ux=fs.readFileSync(path.join(stage,'src/Probe/index.ux'),'utf8');
}finally{
  assert.equal(path.dirname(fs.realpathSync(stage)),base);
  fs.rmSync(stage,{recursive:true,force:true});
}
async function rig(duration){
  let now=1000000,held=false;const files=new Map(),pending=[];
  const file={list:o=>o.success({fileList:[...files.keys()].map(uri=>({uri}))}),
    readText:o=>files.has(o.uri)?o.success({text:files.get(o.uri)}):o.fail('missing',301),
    writeText:o=>{const done=()=>{files.set(o.uri,o.text);o.success();};held?pending.push(done):done();},
    delete:o=>{files.delete(o.uri);o.success();}};
  const store=core.createStore(file,{now:()=>now});
  const session=await store.start({sensorPath:'generic',interval:'high',durationSeconds:duration});
  const objects=()=>[...files.values()].map(JSON.parse);
  return {store,session,files,time:n=>{now=1000000+n;},hold:v=>{held=v;},
    flush:()=>{while(pending.length)pending.shift()();},
    push:()=>session.push({x:0.125,y:-0.25,z:9.75},'visible',now),
    blocks:()=>objects().filter(o=>o.kind==='block'),head:()=>objects().find(o=>o.kind==='head'),
    tail:()=>objects().find(o=>o.kind==='tail')};
}

test('30-minute synthetic 30000-row capture stays inside unchanged file/frame/row bounds',async()=>{
  const r=await rig(1800);let maxBuffered=0;
  for(let dt=0;dt<=1800000;dt+=10){
    r.time(dt);if(dt<1800000&&dt%60===0)r.push();if(dt%250===0)r.session.tick();
    maxBuffered=Math.max(maxBuffered,r.session.state().buffered);
  }
  const tail=r.tail();assert.equal(tail.stop_reason,'duration');assert.equal(tail.persisted,30000);
  assert.equal(tail.count,30000);assert.equal(r.session.state().status,'sealed');
  assert.deepEqual(tail.quality.warnings,[]);assert.ok(maxBuffered<=512);
  assert.ok(tail.blocks<300&&tail.blocks<=399,'all existing encoder/decoder bounds must remain valid');
  const inv=await r.store.inventory(r.session.state().id);assert.ok(inv.files.length<=401);
  let maxFrames=0;for(let i=0;i<inv.files.length;i++){
    const text=await r.store.readPart(inv.id,inv.files[i]);assert.ok(text.length<=65536);
    maxFrames=Math.max(maxFrames,core.frames(inv.id,i+1,text).length);
  }
  assert.ok(maxFrames<=219);assert.equal(r.blocks().flatMap(b=>b.rows).length,30000);
  assert.equal(r.head().metadata.storage_policy.timed_flush_ms,8000);
});

test('long mode at a low arrival rate flushes after 8 seconds without waiting for 128 rows',async()=>{
  const r=await rig(1800);
  for(let dt=0;dt<8000;dt+=250){r.time(dt);if(dt%1000===0)r.push();r.session.tick();}
  assert.equal(r.blocks().length,0);r.time(8000);r.push();r.session.tick();
  assert.equal(r.blocks().length,1);assert.equal(r.blocks()[0].rows.length,9);
  r.session.stop('manual');assert.equal(r.session.state().status,'sealed');
});

test('existing short durations preserve their 2-second timed flush and expose its actual policy',async()=>{
  const r=await rig(60);
  for(let dt=0;dt<2000;dt+=250){r.time(dt);if(dt%1000===0)r.push();r.session.tick();}
  assert.equal(r.blocks().length,0);r.time(2000);r.push();r.session.tick();
  assert.equal(r.blocks().length,1);assert.equal(r.head().metadata.storage_policy.timed_flush_ms,2000);
  r.session.stop('manual');
});

test('128 accepted rows still trigger an immediate block before the long timer',async()=>{
  const r=await rig(1800);for(let i=0;i<128;i++){r.time(i*60);r.push();}
  assert.equal(r.blocks().length,1);assert.equal(r.blocks()[0].rows.length,128);
  assert.equal(r.head().metadata.max_buffered_rows,512);r.session.stop('manual');
});

test('long mode preserves silence and write-timeout failures rather than extending monitor deadlines',async()=>{
  const r=await rig(1800);r.push();r.time(3250);r.session.tick();
  assert.equal(r.tail().stop_reason,'sensor_silence');
  const w=await rig(1800);w.hold(true);for(let i=0;i<128;i++){w.time(i*60);w.push();}
  w.time(7620+8101);w.session.tick();assert.equal(w.session.state().stop_reason,'write_timeout');
  w.hold(false);w.flush();assert.equal(w.session.state().status,'failed');
});

test('long mode preserves bounded buffers on a stalled disk and never accepts the deadline callback',async()=>{
  const r=await rig(1800);r.hold(true);for(let i=0;i<600;i++){r.time(i*60);r.push();}
  assert.equal(r.session.state().stop_reason,'queue_overflow');assert.equal(r.session.state().count,512);
  assert.ok(r.session.state().buffered<=512);r.hold(false);r.flush();
  const d=await rig(1800);d.push();d.time(1800000);assert.equal(d.push(),false);
  assert.equal(d.session.state().count,1);assert.notEqual(d.tail().stop_reason,'duration');
});

test('unsupported durations remain refused and the UI labels 30 minutes without test entries',async()=>{
  await assert.rejects(()=>rig(1801),/设置/);
  assert.match(ux,/2,10,30,60,180,300,1800/);assert.match(ux,/分钟/);
  const template=ux.split('</template>')[0];assert.doesNotMatch(template,/onclick="(?:openInput|startInput|inspectStorage)"/);
});
