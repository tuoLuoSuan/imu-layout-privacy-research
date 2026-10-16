const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),vm=require('node:vm');
const inputProbe=require('../variants/input-probe/src/common/input-probe.js');
function page(){
 const base=fs.realpathSync(os.tmpdir()),dir=fs.mkdtempSync(path.join(base,'imus5-input-ui-'));let ux,research;
 try{require('../tools/build_input_probe_source.cjs').prepareStage(dir);ux=fs.readFileSync(path.join(dir,'src/Probe/index.ux'),'utf8');research=require(path.join(dir,'src/common/research.js'));}
 finally{assert.equal(path.dirname(fs.realpathSync(dir)),base);fs.rmSync(dir,{recursive:true,force:true});}
 let decl=0,subscribed=0;const timers=new Map(),files=new Map(),sensor={subscribe(){subscribed++;return 99;},unsubscribe(){},unsubscribeAccelerometer(){}};
 Object.defineProperty(sensor,'DATA_TYPES',{get(){decl++;return {ACCELEROMETER:2};}});
 const file={list:o=>queueMicrotask(()=>o.success({fileList:[]})),writeText:o=>queueMicrotask(()=>{files.set(o.uri,o.text);o.success();})};
 const context={research,inputProbe,sensor,file,storageDiagnostic:{},interconnect:{},legacyCore:{},transfer:{},performance:undefined,Date,Math,JSON,Promise,
  setInterval(fn){const n=timers.size+1;timers.set(n,fn);return n;},clearInterval(n){timers.delete(n);}};
 vm.createContext(context);vm.runInContext(ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result='),context);
 const p=Object.assign({},context.result.private,context.result);p.onInit();return {p,ux,files,timers,get decl(){return decl;},get subscribed(){return subscribed;}};
}
const settle=()=>new Promise(setImmediate);
test('opening home never probes; input page inspects declarations only and does not auto subscribe',()=>{
 const r=page();assert.equal(r.decl,0);assert.match(r.ux,/v0\.4\.0/);r.p.openInput();assert.equal(r.p.inputMode,true);assert.equal(r.decl,1);assert.equal(r.subscribed,0);assert.equal(r.files.size,0);
});
test('probe busy gate blocks recording/settings/navigation and hides stop the candidate exactly once',async()=>{
 const r=page(),p=r.p;p.openInput();p.startInput();p.startInput();await settle();await settle();
 assert.equal(r.subscribed,1);assert.equal(p.busy(),true);p.openSettings();assert.equal(p.settingsMode,false);p.showRecords();assert.equal(p.tab,'collect');
 p.onHide();await settle();await settle();assert.equal(p.inputBusy,false);assert.equal(r.timers.size,0);
 assert.equal([...r.files.values()].map(JSON.parse).find(x=>x.kind==='tail').input_probe.result,'page_hide');
 p.startInput();assert.equal(r.subscribed,1);
});
test('page hide/destroy preserves first terminal transport error; active transfer still cancels',()=>{
 const p=page().p;let status='failed',cancelled=0;
 p._sender={state:()=>({status}),cancel(){cancelled++;status='cancelled';}};p.transferStatus='original receiver rejection';p.transferring=false;
 p.onHide();p.onDestroy();assert.equal(cancelled,0);assert.equal(status,'failed');assert.equal(p.transferStatus,'original receiver rejection');
 const q=page().p;status='sending';q._sender=p._sender;q.transferring=true;q.onHide();assert.equal(cancelled,1);assert.equal(q.transferring,false);
});
