const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const research=require('../variants/research-recorder/src/common/research.js'),diag=require('../variants/storage-diagnostic/src/common/storage-diagnostic.js');
function setup(){
 const builder=path.join(__dirname,'../tools/build_storage_diagnostic_source.cjs');assert.ok(fs.existsSync(builder),'缺少独立0.3.3诊断覆盖层');
 const parent=fs.realpathSync(os.tmpdir()),temp=fs.mkdtempSync(path.join(parent,'imus5-diag-test-'));let ux;
 try{require(builder).prepareStage(temp);ux=fs.readFileSync(path.join(temp,'src/Probe/index.ux'),'utf8');}
 finally{assert.equal(path.dirname(fs.realpathSync(temp)),parent);fs.rmSync(temp,{recursive:true,force:true});}
 const files=new Map();let time=1000,listCalls=0,getCalls=0,hold=false,pending=[];
 const file={
  list(o){listCalls++;const run=()=>o.success({fileList:[...files.keys()].map(uri=>({uri:uri.replace('internal://files/','/synthetic-native/files/')}))});if(hold)pending.push(run);else queueMicrotask(run);},
  get(o){getCalls++;queueMicrotask(()=>o.success({type:'dir',subFiles:[...files.keys()].map(uri=>({uri}))}));},
  writeText(o){queueMicrotask(()=>{files.set(o.uri,o.text);o.success();});},
  readText(o){queueMicrotask(()=>files.has(o.uri)?o.success({text:files.get(o.uri)}):o.fail('missing',301));}
 };
 const sensor={subscribeAccelerometer(o){this.options=o;},unsubscribeAccelerometer(){}};
 const context={research:Object.assign({},research,{createStore:f=>research.createStore(f,{now:()=>time})}),storageDiagnostic:diag,
  sensor,file,transfer:require('../variants/research-transfer/src/common/transfer.js'),interconnect:{},legacyCore:require('../src/common/recorder.js'),Date,Math,JSON,Promise,setInterval:()=>1,clearInterval(){}};
 vm.createContext(context);vm.runInContext(ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result='),context);
 const p=Object.assign({},context.result.private,context.result);p.onInit();
 return {p,sensor,files,setTime:t=>{time=t;},counts:()=>[listCalls,getCalls],hold:()=>{hold=true;},release:()=>{hold=false;pending.splice(0).forEach(f=>f());}};
}
const settle=()=>new Promise(r=>setImmediate(r));

test('synthetic 99-row sealed record remains byte-identical while empty-list diagnostic exposes actual URI response',async()=>{
 const {p,sensor,files,setTime}=setup();p.startRecording();await settle();
 for(let i=0;i<99;i++){setTime(1000+i*20);sensor.options.callback({x:i,y:2,z:3});}
 setTime(3000);p._session.tick();await settle();await settle();
 assert.equal(p.persisted,99);assert.match(p.status,/已保存 99条/);const before=[...files];
 p.showRecords();await settle();assert.equal(p.recordPosition,'0 / 0');
 p.inspectStorage();await settle();assert.equal(p.diagnosticMode,true);assert.equal(p.diagnosticRunning,false);
 assert.ok(p._diagnosticPages.some(v=>v.detail.includes('/synthetic-native/files/')));assert.deepEqual([...files],before);
 p.closeStorage();assert.equal(p.diagnosticMode,false);assert.match(p.status,/已保存 99条/);
});

test('capture and duplicate checks are gated; leaving the page discards late diagnostic results',async()=>{
 const h=setup(),p=h.p;p.startRecording();await settle();const before=h.counts();p.inspectStorage();assert.deepEqual(h.counts(),before);
 p.stopRecording();await settle();await settle();h.hold();p.inspectStorage();const first=h.counts();p.inspectStorage();assert.deepEqual(h.counts(),first);
 p.startRecording();assert.equal(p.recording,false);p.onHide();const status=p.status;h.release();await settle();
 assert.equal(p.status,status);assert.equal(p.diagnosticRunning,false);assert.equal(p._diagnosticPages.length,0);
});
