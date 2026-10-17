const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),builder=path.join(root,'tools/build_lifecycle_reporting_source.cjs'),tmp=fs.realpathSync(os.tmpdir());
const stage=fs.mkdtempSync(path.join(tmp,'imus5-lifecycle-test-'));let capture,core,ux,manifest,catalog,screen;
try{require(fs.existsSync(builder)?builder:path.join(root,'tools/build_catalog_performance_source.cjs')).prepareStage(stage);
 capture=require(path.join(stage,'src/common/sensor-capture.js'));core=require(path.join(stage,'src/common/research.js'));catalog=require(path.join(stage,'src/common/record-catalog.js'));screen=require(path.join(stage,'src/common/screen-guard.js'));
 ux=fs.readFileSync(path.join(stage,'src/Probe/index.ux'),'utf8');manifest=JSON.parse(fs.readFileSync(path.join(stage,'src/manifest.json')));
}finally{assert.equal(path.dirname(fs.realpathSync(stage)),tmp);fs.rmSync(stage,{recursive:true,force:true});}
const POLICY={schema_version:1,mode:'lifecycle_only',raw_callback_capture:'unchanged',final_report:'before_seal'};
const value={ACCELEROMETER:{x:.125,y:-.25,z:9.75}},settle=async()=>{for(let i=0;i<4;i++)await new Promise(setImmediate);};
function driverRig(mode){let cb,notices=0,unsubs=0,values=0;const d=capture.create({DATA_TYPES:{ACCELEROMETER:2},subscribe:o=>{cb=o.callback;return 129;},unsubscribe:()=>unsubs++},
 {reportMode:mode,now:()=>1000,onChange:()=>notices++,onValue:()=>{values++;return true;}});
 return {d,start:()=>d.start({sensorPath:'generic',interval:'high'}),emit:()=>cb(value),counts:()=>({notices,unsubs,values})};}
test('explicit lifecycle mode suppresses normal reports but preserves every callback and terminal counters',()=>{
 const r=driverRig('lifecycle_only');r.start();for(let i=0;i<992;i++)r.emit();assert.equal(r.counts().notices,1);r.d.stop();
 assert.deepEqual(r.counts(),{notices:2,unsubs:1,values:992});assert.equal(r.d.state().accepted_rows,992);assert.equal(r.d.state().fractional_xyz_scalars,2976);
});
test('default mode preserves old per-callback reporting and unknown mode fails before subscribing',()=>{
 const r=driverRig(undefined);r.start();r.emit();r.emit();r.d.stop();assert.equal(r.counts().notices,4);
 assert.throws(()=>driverRig('typo'),/report mode/);
});
test('manifest, recording head and real page explicitly declare the same policy',async()=>{
 const files=[];await core.createStore({list:o=>o.success({fileList:[]}),writeText:o=>{files.push(JSON.parse(o.text));o.success();}},{now:()=>1000}).start({sensorPath:'generic',interval:'high',durationSeconds:600});
 assert.equal(manifest.versionName,'0.4.12');assert.equal(manifest.versionCode,21);assert.deepEqual(files[0].metadata.acquisition_reporting_policy,POLICY);
 assert.match(ux,/reportMode:'lifecycle_only'/);assert.match(ux,/v0\.4\.12/);assert.match(ux,/reloadRecords/);
});
function pageRig(mode,options={}){
 let clock=1000000,native,reportCount=0,unsubs=0,nextTimer=0;const files=new Map(),intervals=new Map(),timers=new Map(),screens=[],actualModes=[];
 const dispatch=fn=>options.asyncWrites?queueMicrotask(fn):fn();
 const file={list:o=>dispatch(()=>o.success({fileList:[...files.keys()].map(uri=>({uri}))})),readText:o=>dispatch(()=>files.has(o.uri)?o.success({text:files.get(o.uri)}):o.fail('missing',404)),writeText:o=>dispatch(()=>{files.set(o.uri,o.text);o.success();})};
 const sensor={DATA_TYPES:{ACCELEROMETER:2},subscribe:o=>{native=o;if(options.nativeFail)o.fail('exact native fail',203);if(options.syncCallback)o.callback(value);if(options.throwSubscribe)throw Error('subscribe exception');return 129;},unsubscribe:h=>{assert.equal(h,129);unsubs++;if(options.throwUnsubscribe)throw Error('unsubscribe exception');}};
 const context={sensor,file,recordCatalog:catalog,research:Object.assign({},core,{createStore:f=>core.createStore(f,{now:()=>clock})}),
  sensorCapture:{create:(sensor,env)=>{actualModes.push(env.reportMode);return capture.create(sensor,Object.assign({},env,{reportMode:mode===undefined?env.reportMode:mode,onChange:r=>{reportCount++;env.onChange(r);}}));}},
  screenGuard:screen,inputProbe:{},storageDiagnostic:{},legacyCore:{},transfer:{},interconnect:{},Math,JSON,Promise,Date:{now:()=>clock},
  setTimeout:(fn,delay)=>{const id=++nextTimer;timers.set(id,{fn,delay});return id;},clearTimeout:id=>timers.delete(id),setInterval:fn=>{const id=++nextTimer;intervals.set(id,fn);return id;},clearInterval:id=>intervals.delete(id),
  require:()=>({setKeepScreenOn:o=>{screens.push(o.keepScreenOn);dispatch(()=>o.success());}})};
 vm.createContext(context);vm.runInContext(ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result='),context);
 const page=Object.assign({},context.result.private,context.result);page.onInit();
 return {page,files,screens,timers,actualModes,clock:t=>{clock=t;},tick:()=>{for(const fn of [...intervals.values()])fn();},emit:v=>native.callback(v||value),fail:()=>native.fail('late native fail',203),reports:()=>reportCount,unsubs:()=>unsubs};
}
async function session(mode,scenario,asyncWrites=false){
 const originalRandom=Math.random;Math.random=()=>.125;
 try{
  const r=pageRig(mode,{asyncWrites,nativeFail:scenario==='native_fail',syncCallback:scenario==='sync_callback',throwUnsubscribe:scenario==='unsubscribe_exception',throwSubscribe:scenario==='subscribe_exception'});
  r.page.durationSeconds=scenario==='duration'?10:600;r.page.startRecording();await settle();
  if(!['native_fail','subscribe_exception'].includes(scenario)){
   const limit=scenario==='duration_long'||scenario==='slow_long'?600000:12000;
   for(let dt=0;dt<=limit;dt+=10){
    r.clock(1000000+dt);
    const stop=scenario==='gap1510'&&dt>=3000&&dt<4450;
    if(dt%(scenario==='slow_long'?200:60)===0&&!stop&&scenario!=='silence'){r.emit(scenario==='invalid'&&dt===3000?{ACCELEROMETER:{x:null,y:1,z:2}}:value);await settle();}
    if(dt%250===0){r.tick();await settle();}
    if(scenario==='hidden'&&dt===5000){r.page.onHide();await settle();break;}
    if(scenario==='destroy'&&dt===5000){r.page.onDestroy();await settle();break;}
    if(scenario==='native_late_fail'&&dt===5000){r.fail();await settle();break;}
    if(r.page._session.state().status==='sealed')break;
   }
   if(r.page._session.state().status==='recording'){r.page.stopRecording();await settle();}
  }
  await settle();const parts=[...r.files.values()].map(JSON.parse),tail=parts.find(x=>x.kind==='tail');assert.ok(tail,scenario);assert.equal(r.page._session.state().status,'sealed');
  return {r,tail,parts,bytes:JSON.stringify([...r.files.entries()])};
 }finally{Math.random=originalRandom;}
}
for(const scenario of ['manual','duration','duration_long','slow_long','silence','gap1510','invalid','native_fail','native_late_fail','sync_callback','hidden','destroy','unsubscribe_exception','subscribe_exception']){
 test('actual staged controller with tick: '+scenario+' keeps all bytes and final observations across modes',async()=>{
  for(const asyncWrites of [false,true]){
   const a=await session('per_callback',scenario,asyncWrites),b=await session('lifecycle_only',scenario,asyncWrites);
   assert.equal(b.bytes,a.bytes,scenario+' async='+asyncWrites);assert.equal(b.tail.acquisition_observation.accepted_rows,b.tail.persisted);
   assert.equal(b.tail.acquisition_observation.callback_count,a.tail.acquisition_observation.callback_count);assert.deepEqual(b.r.screens,[true,false]);assert.deepEqual(b.r.actualModes,['lifecycle_only']);
   if(!['subscribe_exception'].includes(scenario))assert.equal(b.r.unsubs(),1);
   if(scenario==='gap1510')assert.ok(b.tail.quality.warnings.includes('callback_gap_over_1s'));
   if(scenario==='manual')assert.ok(b.r.reports()<a.r.reports());
   if(scenario==='duration_long'){assert.equal(b.tail.persisted,10000);assert.equal(b.tail.acquisition_observation.callback_count,10001);assert.deepEqual(b.tail.quality.warnings,[]);}
   if(scenario==='slow_long'){assert.equal(b.tail.persisted,3000);assert.equal(b.tail.acquisition_observation.callback_count,3001);assert.deepEqual(b.tail.quality.warnings,[]);}
   if(scenario==='silence'){assert.equal(b.tail.persisted,0);assert.equal(b.tail.stop_reason,'sensor_silence');}
  }
 });
}
test('late callback after sealing cannot change rows, terminal report or persisted source',async()=>{
 const {r,bytes}=await session('lifecycle_only','manual',true);const n=r.reports();r.emit();await settle();assert.equal(JSON.stringify([...r.files.entries()]),bytes);assert.equal(r.reports(),n);
});
