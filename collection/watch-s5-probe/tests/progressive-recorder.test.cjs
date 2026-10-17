const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),candidate=path.join(root,'tools/build_progressive_recorder_source.cjs');
const base=fs.realpathSync(os.tmpdir()),stage=fs.mkdtempSync(path.join(base,'imus5-progressive-test-'));
let core,ux;
try{
  require(fs.existsSync(candidate)?candidate:path.join(root,'tools/build_long_recorder_source.cjs')).prepareStage(stage);
  core=require(path.join(stage,'src/common/research.js'));ux=fs.readFileSync(path.join(stage,'src/Probe/index.ux'),'utf8');
}finally{assert.equal(path.dirname(fs.realpathSync(stage)),base);fs.rmSync(stage,{recursive:true,force:true});}
async function rig(duration){
  let time=1000000;const files=new Map();
  const file={list:o=>o.success({fileList:[...files.keys()].map(uri=>({uri}))}),
    writeText:o=>{files.set(o.uri,o.text);o.success();},readText:o=>o.success({text:files.get(o.uri)})};
  const store=core.createStore(file,{now:()=>time});
  const session=await store.start({durationSeconds:duration,interval:'high',sensorPath:'generic'});
  const objects=()=>[...files.values()].map(JSON.parse);
  return {session,store,time:dt=>{time=1000000+dt;},push:()=>session.push({x:0.125,y:2.5,z:9.75},'visible',time),
    head:()=>objects().find(v=>v.kind==='head'),tail:()=>objects().find(v=>v.kind==='tail'),
    blocks:()=>objects().filter(v=>v.kind==='block')};
}
for(const seconds of [600,900,1200])test(`intermediate ${seconds/60}-minute option uses the final long-mode policy and seals every synthetic row`,async()=>{
  const r=await rig(seconds);
  for(let dt=0;dt<=seconds*1000;dt+=10){r.time(dt);if(dt<seconds*1000&&dt%60===0)r.push();if(dt%250===0)r.session.tick();}
  assert.equal(r.head().metadata.storage_policy.timed_flush_ms,8000);
  assert.equal(r.tail().count,seconds*1000/60);assert.equal(r.tail().persisted,r.tail().count);
  assert.equal(r.tail().stop_reason,'duration');assert.deepEqual(r.tail().quality.warnings,[]);
  assert.ok(r.tail().blocks<=399);const inv=await r.store.inventory(r.session.state().id);assert.ok(inv.files.length<=401);
});
test('five-minute mode keeps the old timed flush while ten-minute mode uses the same 8 seconds as thirty',async()=>{
  for(const [seconds,period] of [[300,2000],[600,8000],[1800,8000]]){
    const r=await rig(seconds);
    for(let dt=0;dt<period;dt+=250){r.time(dt);if(dt%1000===0)r.push();r.session.tick();}
    assert.equal(r.blocks().length,0);r.time(period);r.push();r.session.tick();
    assert.equal(r.blocks().length,1);assert.equal(r.head().metadata.storage_policy.timed_flush_ms,period);r.session.stop('manual');
  }
});
test('all intermediate settings render minutes from the actual page setting controller',()=>{
  const ctx={};vm.createContext(ctx);vm.runInContext(ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result='),ctx);
  const lists=vm.runInNewContext(ux.match(/this\._lists=(\[[^\n]+\]);/)[1]);
  for(const seconds of [600,900,1200,1800]){
    const p={_lists:lists,_values:[lists[0].indexOf(seconds),0,0,0,0,0,0],settingIndex:0};
    assert.ok(p._values[0]>=0);ctx.result.renderSetting.call(p);
    assert.equal(p.settingValue,String(seconds/60)+' 分钟');assert.equal(p.durationSeconds,seconds);
  }
});
