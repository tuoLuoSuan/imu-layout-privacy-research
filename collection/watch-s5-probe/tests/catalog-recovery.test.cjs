const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const previous=path.join(__dirname,'research-ready.test.cjs');
let harness=fs.readFileSync(previous,'utf8').split("test('independent candidate")[0];
harness=harness.replace('i<30;i++','i<160;i++');
const candidate=path.resolve(__dirname,'../tools/build_catalog_recovery_source.cjs');
harness=harness.replace("path.join(root,'tools/build_research_ready_source.cjs')",JSON.stringify(fs.existsSync(candidate)?candidate:path.resolve(__dirname,'../tools/build_research_ready_source.cjs')));
harness=harness.replace("readText:o=>{calls.read++;", "readText:o=>{calls.read++;if(r.delayRead){r.reads.push(o);return;}");
harness=harness.replace("writeText:o=>{calls.write++;", "writeText:o=>{calls.write++;if(r.delayWrite){r.writes.push({...o,success:()=>{files.set(o.uri,o.text);o.success();}});return;}");
harness=harness.replace("delete:o=>{calls.delete++;files.delete", "delete:o=>{calls.delete++;if(r.failDelete){r.failDelete=false;o.fail('controlled',5);return;}if(r.delayDelete){r.deletes.push(o);return;}files.delete");
harness=harness.replace("screens.push(o.keepScreenOn);o.success();", "screens.push(o.keepScreenOn);if(r.delayScreen){r.screenRequests.push(o);return;}o.success();");
harness=harness.replace('page,files,calls,screens,pending,delayList:false','page,files,calls,screens,pending,reads:[],writes:[],deletes:[],screenRequests:[],delayList:false');
const mod=new Module(previous,module);mod.filename=previous;mod.paths=module.paths;mod._compile(harness+'\nmodule.exports={rig,addSession,settle,sources,manifest};',previous);
const {rig,addSession,settle,sources,manifest}=mod.exports;
module.exports=mod.exports;
const entries=r=>({fileList:[...r.files.keys()].map(uri=>({uri}))});
const plain=v=>JSON.parse(JSON.stringify(v));
async function browse(r){r.page.showRecords();await settle();}
test('0414/version23 keeps four ordinary capabilities',()=>{assert.equal(manifest.versionName,'0.4.14');assert.equal(manifest.versionCode,23);assert.equal(manifest.features.length,4);});
test('9s directory succeeds while awake, selected summary finishes before release',async()=>{
 const r=rig(),id=addSession(r);r.delayList=true;await browse(r);await r.advance(1009000);
 assert.equal(r.page.loading,true);assert.deepEqual(r.screens,[true]);assert.match(r.page.status,/9秒|目录/);
 r.delayRead=true;r.pending[0].success(entries(r));await settle();assert.equal(r.reads.length,1);assert.deepEqual(r.screens,[true]);
 r.delayRead=false;r.reads[0].success({text:r.files.get('internal://files/s5r_'+id+'_head.json')});await settle();
 assert.equal(r.page.recordPosition,'1 / 1');assert.deepEqual(r.screens,[true,false]);assert.equal(r.calls.write+r.calls.delete,0);
});
test('unknown directory fails after30s, never claims zero or deletes',async()=>{
 const r=rig();r.delayList=true;await browse(r);await r.advance(1030000);assert.match(r.page.status,/超时/);
 assert.equal(r.page.loading,false);assert.match(r.page.capacityText,/未知/);assert.deepEqual(r.screens,[true,false]);assert.equal(r.calls.write+r.calls.delete,0);
});
test('concurrent catalog consumers share one scan but use their own mode',async()=>{
 const r=rig(),a=addSession(r),b=addSession(r,1);r.files.set('internal://files/s5r_'+b+'_trash.json','{}');r.delayList=true;
 const first=r.page._store.list(false),second=r.page._store.list(true);await settle();assert.equal(r.calls.list,1);
 r.pending[0].success(entries(r));const [x,y]=await Promise.all([first,second]);assert.equal(x[0].id,a);assert.equal(y[0].id,b);
});
test('records navigation leaves recycle mode; opening performs zero mutations',async()=>{
 const r=rig();addSession(r);r.page.trashMode=true;await browse(r);assert.equal(r.page.trashMode,false);assert.equal(r.page.recordPosition,'1 / 1');assert.equal(r.calls.write+r.calls.delete,0);
});
test('cancelled read releases owner, late list does not replace UI, refresh shares in-flight scan',async()=>{
 const r=rig();addSession(r);r.delayList=true;await browse(r);r.page.reloadRecords();await settle();
 assert.equal(r.page.loading,false);assert.deepEqual(r.screens,[true,false]);const status=r.page.status;
 r.page.reloadRecords();await settle();assert.equal(r.calls.list,1);r.pending[0].success(entries(r));await settle();
 assert.equal(r.page.recordPosition,'1 / 1');assert.notEqual(r.page.status,status);assert.deepEqual(r.screens,[true,false,true,false]);
});
for(const event of ['onHide','onDestroy'])test(event+' prevents late browse UI and releases screen',async()=>{
 const r=rig();addSession(r);r.delayList=true;await browse(r);r.page[event]();await settle();const title=r.page.recordTitle;
 r.pending[0].success(entries(r));await settle();assert.equal(r.page.recordTitle,title);assert.deepEqual(r.screens,[true,false]);
 if(event==='onHide'){r.page.onShow();await settle();assert.equal(r.calls.list,1);}
});
test('late keep-awake acquisition after catalog cancellation must clean before another owner',async()=>{
 const r=rig();addSession(r);r.delayScreen=true;await browse(r);r.page.reloadRecords();await settle();r.page.reloadRecords();await settle();assert.equal(r.calls.list,0);
 r.screenRequests[0].success();await settle();r.screenRequests[1].success();r.screenRequests[2].success();await settle();await r.advance(1000050);
 assert.equal(r.page._exportScreen,null);r.delayScreen=false;r.page.reloadRecords();await settle();assert.equal(r.page.recordPosition,'1 / 1');assert.deepEqual(r.screens,[true,false,false,true,false]);
});
test('batch moves three records with one fresh scan, no block reads or deletes',async()=>{
 const r=rig(),ids=[0,1,2].map(i=>addSession(r,i));const result=await r.page._store.batch('trash',ids,{});
 assert.deepEqual(plain(result.completed),ids);assert.equal(result.error,null);assert.equal(r.calls.list,1);assert.equal(r.calls.read,6);assert.equal(r.calls.write,3);assert.equal(r.calls.delete,0);
});
test('public inspect never accepts caller supplied stale directory entries',async()=>{
 const r=rig(),id=addSession(r);r.delayList=true;let result;r.page._store.inspect(id,[]).then(x=>{result=x;},e=>{result=e;});await settle();assert.equal(r.calls.list,1);assert.equal(result,undefined);
});
test('batch selection is validated before mutation',async()=>{
 const r=rig(),id=addSession(r);for(const ids of [[],[id,id],['../bad']])await assert.rejects(r.page._store.batch('trash',ids,{}));
 await assert.rejects(r.page._store.batch('purge',[id],{confirmed_ids:[]}));assert.equal(r.calls.write+r.calls.delete,0);
});
test('batch stops at first changed/corrupt live head, reports partial completion',async()=>{
 const r=rig(),ids=[0,1,2].map(i=>addSession(r,i));r.files.set('internal://files/s5r_'+ids[1]+'_head.json','{}');const result=await r.page._store.batch('trash',ids,{});
 assert.deepEqual(plain(result.completed),[ids[0]]);assert.equal(result.failed_id,ids[1]);assert.match(result.error,/损坏/);assert.equal(r.calls.write,1);
});
test('batch cancellation waits for current write and never starts next record',async()=>{
 const r=rig(),ids=[0,1].map(i=>addSession(r,i));let cancel=false;r.delayWrite=true;
 const operation=r.page._store.batch('trash',ids,{shouldCancel:()=>cancel});await settle();assert.equal(r.writes.length,1);cancel=true;
 r.writes[0].success();const result=await operation;assert.deepEqual(plain(result.completed),[ids[0]]);assert.equal(result.cancelled,true);assert.equal(r.calls.write,1);
});
test('batch busy rejects start and conflicting mutation, then unlocks',async()=>{
 const r=rig(),id=addSession(r);r.delayWrite=true;const operation=r.page._store.batch('trash',[id],{});await settle();
 await assert.rejects(r.page._store.start({durationSeconds:2}),/整理|批量/);await assert.rejects(r.page._store.restore(id),/整理|批量/);
 r.writes[0].success();await operation;r.delayWrite=false;await r.page._store.restore(id);
});
test('batch permanent deletion needs recycled sealed record and exact ID confirmation',async()=>{
 const r=rig(),a=addSession(r),b=addSession(r,1);let result=await r.page._store.batch('purge',[a],{confirmed_ids:[a]});assert.match(result.error,/回收/);assert.equal(r.calls.delete,0);
 await r.page._store.batch('trash',[a,b],{});r.files.delete('internal://files/s5r_'+b+'_tail.json');result=await r.page._store.batch('purge',[b],{confirmed_ids:[b]});assert.match(result.error,/中断|封口/);assert.equal(r.calls.delete,0);
});
test('purge failure preserves journal and retry completes with one scan per batch',async()=>{
 const r=rig(),ids=[0,1].map(i=>addSession(r,i));await r.page._store.batch('trash',ids,{});r.failDelete=true;
 let result=await r.page._store.batch('purge',ids,{confirmed_ids:ids});assert.equal(result.completed.length,0);assert.ok(r.files.has('internal://files/s5r_'+ids[0]+'_purge.json'));
 const before=r.calls.list;result=await r.page._store.batch('purge',ids,{confirmed_ids:ids});assert.equal(r.calls.list,before+1);assert.equal(result.completed.length,2);assert.equal(r.files.size,0);
});
test('timed-out batch reports uncertain current record, does not advance or retry',async()=>{
 const r=rig(),ids=[0,1].map(i=>addSession(r,i));r.delayWrite=true;const operation=r.page._store.batch('trash',ids,{});await settle();await r.advance(1008000);
 const result=await operation;assert.match(result.error,/超时/);assert.equal(result.uncertain,true);assert.equal(result.failed_id,ids[0]);assert.equal(result.completed.length,0);assert.equal(r.calls.write,1);
});
test('batch UI defaults empty, quick select excludes newest, no mutation until final confirmation',async()=>{
 const r=rig();[0,1,2].map(i=>addSession(r,i));await browse(r);r.page.openBatch();await settle();assert.equal(r.page.batchMode,true);assert.equal(r.page._batchSelected.length,0);
 r.page.selectOlder();assert.deepEqual(plain(r.page._batchSelected).sort(),[addSession(r,0),addSession(r,1)].sort());assert.equal(r.calls.write+r.calls.delete,0);
 r.page.prepareBatch('trash');assert.equal(r.page.confirmMode,true);assert.equal(r.calls.write+r.calls.delete,0);r.page.confirmAction();await settle();assert.equal(r.calls.write,2);assert.deepEqual(r.screens,[true,false,true,false]);
});
test('permanent batch confirmation requires separate external backup acknowledgement',async()=>{
 const r=rig(),id=addSession(r);await r.page._store.batch('trash',[id],{});r.page.trashMode=true;r.page.tab='records';r.page.refreshRecords(true,0,0);await settle();
 r.page.openBatch();r.page.toggleBatchItem();r.page.prepareBatch('purge');r.page.confirmAction();await settle();assert.equal(r.calls.delete,0);
 r.page.acknowledgeBackup();r.page.confirmAction();await settle();assert.equal(r.files.size,0);
});
test('batch UI hide requests stop after current record and keeps lock until current completes',async()=>{
 const r=rig();[0,1,2].forEach(i=>addSession(r,i));await browse(r);r.page.openBatch();r.page.selectOlder();r.page.prepareBatch('trash');r.delayWrite=true;r.page.confirmAction();await settle();
 assert.equal(r.writes.length,1);r.page.onHide();await settle();r.writes[0].success();await settle();assert.equal(r.calls.write,1);assert.equal(r.page._batchRunning,false);assert.deepEqual(r.screens,[true,false,true,false]);
});
test('hidden batch completion is rendered on return without another mutation or scan',async()=>{
 const r=rig();[0,1,2].forEach(i=>addSession(r,i));await browse(r);r.page.openBatch();r.page.selectOlder();r.page.prepareBatch('trash');r.delayWrite=true;r.page.confirmAction();await settle();
 r.page.onHide();r.writes[0].success();await settle();const before={...r.calls};r.page.onShow();await settle();
 assert.equal(r.page.batchRunning,false);assert.equal(r.page.confirmMode,false);assert.match(r.page.status,/1\/2|已停止/);assert.deepEqual(r.calls,before);
});
test('acquire failure terminates catalog loading; next explicit attempt can proceed',async()=>{
 const r=rig();addSession(r);r.delayScreen=true;await browse(r);r.screenRequests[0].fail('controlled',3);await settle();r.screenRequests[1].success();await settle();
 assert.equal(r.page._catalogLoading,false);assert.equal(r.page.loading,false);r.delayScreen=false;r.page.reloadRecords();await settle();assert.equal(r.page.recordPosition,'1 / 1');
});
test('batch cancellation during an entire purge completes its head-last journal before stopping',async()=>{
 const r=rig(),ids=[0,1].map(i=>addSession(r,i));await r.page._store.batch('trash',ids,{});r.delayDelete=true;let cancel=false;
 const work=r.page._store.batch('purge',ids,{confirmed_ids:ids,shouldCancel:()=>cancel});await settle();cancel=true;
 for(let i=0;i<5;i++){const request=r.deletes[i];assert.ok(request);r.files.delete(request.uri);request.success();await settle();}
 const result=await work;assert.deepEqual(plain(result.completed),[ids[0]]);assert.equal(result.cancelled,true);assert.ok(r.files.has('internal://files/s5r_'+ids[1]+'_head.json'));
 assert.ok(r.deletes.at(-2).uri.endsWith('_head.json'));assert.ok(r.deletes.at(-1).uri.endsWith('_purge.json'));
});
test('rejected concurrent single mutation must not clear a live mutation lock',async()=>{
 const r=rig(),id=addSession(r);r.delayWrite=true;const a=r.page._store.trash(id);await settle();
 await assert.rejects(r.page._store.trash(id),/整理/);await assert.rejects(r.page._store.batch('trash',[id],{}),/整理/);
 r.writes[0].success();await a;
});
test('non-selected and original head/block/tail bytes remain after batch trash and restore',async()=>{
 const r=rig(),ids=[0,1,2].map(i=>addSession(r,i)),before=new Map(r.files);
 await r.page._store.batch('trash',ids.slice(1),{});await r.page._store.batch('restore',ids.slice(1),{});
 assert.deepEqual([...r.files],[...before]);
});
test('30s expired browse cannot overwrite later successful explicit directory',async()=>{
 const r=rig();addSession(r);r.delayList=true;await browse(r);await r.advance(1030000);const old=r.pending[0];
 r.delayList=false;addSession(r,1);r.page.reloadRecords();await settle();assert.equal(r.page.recordPosition,'1 / 2');
 old.success({fileList:[]});await settle();assert.equal(r.page.recordPosition,'1 / 2');assert.equal(r.page._store.catalogState().source,'fresh');
});
