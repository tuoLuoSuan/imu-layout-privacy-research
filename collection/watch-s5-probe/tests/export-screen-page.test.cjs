const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const root=path.join(__dirname,'..'),candidate=path.join(root,'tools/build_export_screen_source.cjs');
async function settle(){for(let i=0;i<4;i++)await new Promise(setImmediate);}
function rig(options={}){
 const tmp=fs.realpathSync(os.tmpdir()),stage=fs.mkdtempSync(path.join(tmp,'imus5-export-screen-test-'));let profile;
 try{require(fs.existsSync(candidate)?candidate:'../tools/build_catalog_recorder_source.cjs').prepareStage(stage);profile={core:require(path.join(stage,'src/common/research.js')),catalog:require(path.join(stage,'src/common/record-catalog.js')),guard:require(path.join(stage,'src/common/screen-guard.js')),ux:fs.readFileSync(path.join(stage,'src/Probe/index.ux'),'utf8'),manifest:JSON.parse(fs.readFileSync(path.join(stage,'src/manifest.json')))};}
 finally{assert.equal(path.dirname(fs.realpathSync(stage)),tmp);fs.rmSync(stage,{recursive:true,force:true});}
 let now=1000,next=0;const screens=[],messages=[],timers=new Map(),intervals=new Map(),reads=[];
 const connect={getReadyState:o=>options.notReady?o.success({status:0}):options.readyFail?o.fail('no',5):options.readyPending?null:o.success({status:1}),send:o=>{messages.push(o.data);if(options.sendFail)o.fail('no',5);}};
 const brightness={setKeepScreenOn:o=>{screens.push(o);}};
 const context={sensor:{},file:{},research:profile.core,recordCatalog:profile.catalog,screenGuard:profile.guard,sensorCapture:{},inputProbe:{},storageDiagnostic:{},legacyCore:require('../src/common/recorder.js'),transfer:require('../variants/research-transfer/src/common/transfer.js'),interconnect:{instance:()=>connect},Date:{now:()=>now},Math,JSON,Promise,
  setTimeout:fn=>{const id=++next;timers.set(id,fn);return id;},clearTimeout:id=>timers.delete(id),setInterval:fn=>{const id=++next;intervals.set(id,fn);return id;},clearInterval:id=>intervals.delete(id),require:()=>{if(options.missing)throw Error('missing');return brightness;}};
 vm.createContext(context);vm.runInContext(profile.ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result='),context);
 const p=Object.assign({},context.result.private,context.result);p.onInit();p._items=[{id:'1000_abcdef'}];p._store={inventory:()=>{reads.push('inventory');return options.inventoryFail?Promise.reject(Error('disk failed')):Promise.resolve({id:'1000_abcdef',files:['s5r_1000_abcdef_head.json','s5r_1000_abcdef_tail.json']});},readPart:(id,n)=>{reads.push(n);return options.partFail?Promise.reject(Error('part failed')):Promise.resolve('{"kept":"original"}');}};
 return {p,profile,screens,messages,timers,intervals,reads,connect,time:n=>{now=n;},fireTimeouts:()=>{for(const [id,fn] of [...timers]){timers.delete(id);fn();}},tick:()=>{for(const fn of [...intervals.values()])fn();},ack:()=>{const m=messages.at(-1);connect.onmessage({data:JSON.stringify({p:'S5ACK1',t:m.t,s:m.s,i:m.i,o:m.l,c:m.c,state:'part_complete'})});}};
}
async function start(r,qr=false){qr?r.p.openQrExport():r.p.startWireless();await settle();assert.equal(r.screens.length,1,'export must acquire ordinary screen hold');assert.equal(r.screens[0].keepScreenOn,true);assert.equal(r.messages.length+r.reads.length,0);r.screens[0].success();await settle();}
test('wireless acquires before inventory/send and holds across all parts until final receiver ACK',async()=>{
 const r=rig();r.p.openExport();assert.equal(r.screens.length,0);await start(r);r.time(15000);assert.equal(r.messages.length,1);assert.equal(r.screens.length,1);
 for(let i=0;i<3;i++){r.ack();await settle();assert.equal(r.screens.length,i===2?2:1);}assert.equal(r.screens[1].keepScreenOn,false);
 assert.equal(r.p.busy(),true);r.screens[1].success();await settle();assert.equal(r.p.busy(),false);assert.match(r.p.transferStatus,/保存/);assert.deepEqual(r.reads,['inventory','s5r_1000_abcdef_head.json','s5r_1000_abcdef_tail.json']);
});
test('QR stays awake while displayed/paused/paged and releases on explicit return',async()=>{
 const r=rig();await start(r,true);assert.equal(r.p.exportMode,true);assert.equal(r.p.busy(),true);r.p.startRecording();assert.equal(r.screens.length,1);
 r.p.nextPart();await settle();r.p.pauseQr();assert.equal(r.screens.length,1);r.p.closeExport();await settle();assert.equal(r.screens[1].keepScreenOn,false);r.screens[1].success();await settle();assert.equal(r.p.exportMode,false);assert.equal(r.p.busy(),false);
});
test('acquire failure or unavailable method never reads or sends',async()=>{
 for(const missing of [false,true]){const r=rig({missing});r.p.startWireless();await settle();if(!missing){r.screens[0].fail('denied',403);await settle();for(const s of r.screens.slice(1))s.success();await settle();}assert.equal(r.messages.length+r.reads.length,0);assert.equal(r.p.alert,true);assert.match(r.p.transferStatus,/保亮/);}
});
test('double click, cancellation and late acquire cannot start an old transfer',async()=>{
 const r=rig();r.p.startWireless();r.p.startWireless();await settle();assert.equal(r.screens.length,1);r.p.cancelWireless();await settle();assert.equal(r.screens[1].keepScreenOn,false);r.screens[1].success();r.screens[0].success();await settle();for(const s of r.screens.slice(2))s.success();r.fireTimeouts();await settle();assert.equal(r.messages.length+r.reads.length,0);assert.equal(r.p.busy(),false);
});
test('not ready, ready failure, inventory failure and send failure release without deleting',async()=>{
 for(const o of [{notReady:true},{readyFail:true},{inventoryFail:true},{sendFail:true}]){const r=rig(o);await start(r);assert.equal(r.screens[1].keepScreenOn,false);r.screens[1].success();await settle();assert.equal(r.p.busy(),false);assert.ok(r.p.transferStatus.length);}
});
test('ready timeout, disconnect, hide and destroy release and preserve failure text',async()=>{
 for(const event of ['timeout','disconnect','hide','destroy']){const r=rig({readyPending:event==='timeout'});await start(r);if(event==='timeout'){r.time(10001);r.tick();}else if(event==='disconnect')r.connect.onclose();else if(event==='hide')r.p.onHide();else r.p.onDestroy();await settle();assert.equal(r.screens[1].keepScreenOn,false);r.screens[1].success();await settle();assert.equal(r.p.transferring,false);}
});
test('release failure stays visible and is not presented as confirmed screen cleanup',async()=>{
 const r=rig();await start(r);r.p.cancelWireless();await settle();r.screens[1].fail('failed',5);await settle();assert.equal(r.p.alert,true);assert.match(r.p.status,/释放未确认/);assert.equal(r.p._lastExportScreen.release.status,'failed');
});
test('acquire and release timeouts are bounded, visible and do not start data work after cancellation',async()=>{
 const a=rig();a.p.startWireless();await settle();a.fireTimeouts();await settle();assert.equal(a.messages.length+a.reads.length,0);assert.match(a.p.transferStatus,/保亮/);a.screens[1].success();await settle();assert.equal(a.p.busy(),false);
 const b=rig();await start(b);b.p.cancelWireless();await settle();b.fireTimeouts();await settle();assert.match(b.p.status,/释放未确认/);assert.equal(b.p._lastExportScreen.release.status,'timeout');
});
test('QR read failure and leaving its page release the hold without leaving a busy screen',async()=>{
 for(const mode of ['failure','hide']){const r=rig({partFail:mode==='failure'});await start(r,true);if(mode==='failure')r.p.nextPart();else r.p.onHide();await settle();assert.equal(r.screens[1].keepScreenOn,false);r.screens[1].success();await settle();if(mode==='failure')assert.equal(r.p.exportMode,false);assert.equal(r.p._exportScreenPending,false);}
});
test('pending recording release and export release both block starting a new screen owner',async()=>{
 const r=rig();r.p._screenReleasePending=true;r.p.startWireless();await settle();assert.equal(r.screens.length,0);r.p._screenReleasePending=false;await start(r);r.p.cancelWireless();await settle();r.p.startRecording();r.p.startWireless();assert.equal(r.screens.length,2);r.screens[1].success();await settle();assert.equal(r.p._exportScreenPending,false);
});
test('hide after a failed transmission keeps the original failure rather than labelling it user cancellation',async()=>{
 const r=rig({sendFail:true});await start(r);r.screens[1].success();await settle();const before=r.p.transferStatus;r.p.onHide();await settle();assert.equal(r.p.transferStatus,before);assert.doesNotMatch(before,/已取消/);
});
test('late QR inventory after hide cannot reopen an unguarded export page',async()=>{
 const r=rig();let finish;r.p._store.inventory=()=>new Promise(resolve=>{finish=resolve;});await start(r,true);assert.equal(r.p.loading,true);r.p.onHide();await settle();r.screens[1].success();await settle();r.p.onShow();finish({id:'1000_abcdef',files:['s5r_1000_abcdef_head.json']});await settle();assert.equal(r.p.exportMode,false);assert.equal(r.p.loading,false);
});
test('late QR part or failure after hide is ignored and cannot overwrite newer screen state',async()=>{
 for(const fails of [false,true]){const r=rig();await start(r,true);let complete,fail;r.p._store.readPart=()=>new Promise((a,b)=>{complete=a;fail=b;});r.p.nextPart();assert.equal(r.p.loading,true);r.p.onHide();await settle();r.screens[1].success();await settle();r.p.onShow();r.p.status='newer activity';fails?fail(Error('old failure')):complete('{"old":true}');await settle();assert.equal(r.p.exportMode,false);assert.equal(r.p.qrValue,'');assert.equal(r.p.status,'newer activity');}
});
