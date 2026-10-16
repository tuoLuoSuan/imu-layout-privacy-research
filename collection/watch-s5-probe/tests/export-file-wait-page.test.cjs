const fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const test=require('node:test'),assert=require('node:assert/strict');
const file=path.join(__dirname,'export-screen-page.test.cjs');
const original=fs.readFileSync(file,'utf8');
let source=original.replace("candidate=path.join(root,'tools/build_export_screen_source.cjs')","candidate=path.join(root,'tools/build_export_file_wait_source.cjs')")
 .replace("fs.existsSync(candidate)?candidate:'../tools/build_catalog_recorder_source.cjs'","fs.existsSync(candidate)?candidate:'../tools/build_export_screen_source.cjs'");
function load(code){const m=new Module(file,module);m.filename=file;m.paths=Module._nodeModulePaths(__dirname);m._compile(code+'\nmodule.exports={rig,settle,start};',file);return m.exports;}
// The old thirteen screen lifecycle assertions also execute against this profile.
load(source);
let prefix=source.split("test('wireless")[0];
prefix=prefix.replace('setTimeout:fn=>{const id=++next;timers.set(id,fn);return id;}',
 'setTimeout:(fn,delay)=>{const id=++next;timers.set(id,{fn,delay,due:now+delay});return id;}');
prefix=prefix.replace("transfer:require('../variants/research-transfer/src/common/transfer.js')",
 "transfer:{createSender:o=>require('../variants/research-transfer/src/common/transfer.js').createSender(Object.assign({},o,{now:()=>now}))}");
const {rig,settle,start}=load(prefix);
async function advance(r,target){let count=0;for(;;){const list=[...r.timers].filter(([id,t])=>t.due<=target).sort((a,b)=>a[1].due-b[1].due||a[0]-b[0]);
 if(!list.length)break;assert.ok(++count<1000);const[id,t]=list[0];r.timers.delete(id);r.time(t.due);t.fn();await settle();}r.time(target);await settle();}
async function released(r){const s=r.screens.at(-1);assert.equal(s.keepScreenOn,false);s.success();await settle();assert.equal(r.p._exportScreenPending,false);}

test('wireless file inventory has an 8s engineering deadline and truthful release state',async()=>{
 const r=rig();r.p._store.inventory=()=>new Promise(()=>{});await start(r);
 await advance(r,8999);assert.equal(r.screens.length,1);await advance(r,9000);
 assert.equal(r.p.transferring,false);assert.equal(r.p.alert,true);assert.match(r.p.transferStatus,/读取.*超时/);
 assert.doesNotMatch(r.p.transferStatus,/已释放/);assert.equal(r.messages.length,0);await released(r);
 assert.equal(r.p._lastExportScreen.file_wait.timeouts,1);assert.equal(r.p._lastExportScreen.file_wait.last.phase,'inventory');
});
test('wireless part loading gets its own deadline rather than a total export limit',async()=>{
 const r=rig();r.p._store.readPart=()=>new Promise(()=>{});await start(r);r.time(7000);r.ack();await settle();
 await advance(r,14999);assert.equal(r.screens.length,1);await advance(r,15000);await released(r);
 assert.equal(r.p._lastExportScreen.file_wait.last.phase,'readPart');assert.equal(r.p._sender.state().status,'failed');
});
test('QR inventory timeout exits without leaving an empty QR screen',async()=>{
 const r=rig();r.p._store.inventory=()=>new Promise(()=>{});await start(r,true);await advance(r,9000);await released(r);
 assert.equal(r.p.exportMode,false);assert.equal(r.p.loading,false);assert.equal(r.p.alert,true);assert.match(r.p.status,/读取.*超时/);
});
test('QR viewing stays unbounded; only a newly pending file read times out',async()=>{
 const r=rig();await start(r,true);await advance(r,301000);assert.equal(r.p.exportMode,true);assert.equal(r.screens.length,1);
 r.p._store.readPart=()=>new Promise(()=>{});r.p.nextPart();await settle();
 await advance(r,308999);assert.equal(r.screens.length,1);await advance(r,309000);await released(r);
 assert.equal(r.p.exportMode,false);assert.match(r.p.status,/读取.*超时/);
});
test('each successful read can use almost 8s while total QR session exceeds 8s',async()=>{
 const r=rig();let resolve;r.p._store.inventory=()=>new Promise(ok=>{resolve=ok;});await start(r,true);
 await advance(r,8900);resolve({id:'1000_abcdef',files:['s5r_1000_abcdef_head.json','s5r_1000_abcdef_tail.json']});await settle();
 r.p._store.readPart=()=>new Promise(ok=>{resolve=ok;});r.p.nextPart();await settle();
 await advance(r,16800);resolve('{"kept":"original"}');await settle();assert.equal(r.p.exportMode,true);
 await advance(r,100000);assert.equal(r.screens.length,1);r.p.closeExport();await settle();await released(r);
 assert.equal(r.p._lastExportScreen.file_wait.timeouts,0);
});
test('cancel clears file waits; late old success or failure cannot overwrite a newer export',async()=>{
 for(const fail of [false,true]){const r=rig();let done,reject;r.p._store.inventory=()=>new Promise((a,b)=>{done=a;reject=b;});await start(r,true);
  r.p.onHide();await settle();await released(r);r.p.onShow();
  r.p._store.inventory=()=>Promise.resolve({id:'1000_abcdef',files:['s5r_1000_abcdef_head.json']});
  r.p.openQrExport();await settle();r.screens.at(-1).success();await settle();r.p.status='new export';
  fail?reject(Error('old read failed')):done({id:'1000_abcdef',files:[]});await settle();await advance(r,20000);
  assert.equal(r.p.status,'new export');assert.equal(r.p.exportMode,true);r.p.closeExport();await settle();await released(r);
 }
});
test('timed-out read result cannot revive a closed page or replace the reported failure',async()=>{
 const r=rig();let done;r.p._store.inventory=()=>new Promise(a=>{done=a;});await start(r,true);await advance(r,9000);await released(r);
 const before=r.p.status;done({id:'1000_abcdef',files:[]});await settle();assert.equal(r.p.status,before);assert.equal(r.p.exportMode,false);
});
test('QR read error survives an additional screen release failure',async()=>{
 const r=rig();r.p._store.inventory=()=>new Promise(()=>{});await start(r,true);await advance(r,9000);
 r.screens[1].fail('release failed',47);await settle();
 assert.match(r.p.status,/读取.*超时/);assert.match(r.p.status,/释放未确认/);
 assert.equal(r.p._lastExportScreen.release.error.code,47);
});
test('synchronous file throw preserves its error and records a failed read',async()=>{
 const r=rig();r.p._store.inventory=()=>{throw Error('controlled disk exception');};await start(r);
 assert.match(r.p.transferStatus,/controlled disk exception/);await released(r);
 assert.equal(r.p._lastExportScreen.file_wait.last.status,'failed');
});
test('cancelled screen acquisition still excludes another owner until cleanup completes',async()=>{
 const r=rig();r.p.startWireless();await settle();r.p.cancelWireless();await settle();r.screens[1].success();await settle();
 r.p.startWireless();assert.equal(r.screens.length,2);r.time(1100);r.screens[0].success();await settle();
 r.screens[2].success();await settle();await advance(r,1150);assert.equal(r.p._exportScreenPending,false);
 assert.equal(r.reads.length+r.messages.length,0);
});
