const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),candidate=path.join(root,'tools/build_catalog_performance_source.cjs');
const tmp=fs.realpathSync(os.tmpdir()),stage=fs.mkdtempSync(path.join(tmp,'imus5-catalog-performance-test-'));
let catalog,core,ux;
try{require(fs.existsSync(candidate)?candidate:path.join(root,'tools/build_runtime_timing_source.cjs')).prepareStage(stage);
 catalog=require(path.join(stage,'src/common/record-catalog.js'));core=require(path.join(stage,'src/common/research.js'));ux=fs.readFileSync(path.join(stage,'src/Probe/index.ux'),'utf8');
}finally{assert.equal(path.dirname(fs.realpathSync(stage)),tmp);fs.rmSync(stage,{recursive:true,force:true});}
function rig(n=26){
 const files=new Map(),calls={list:0,read:0,write:0,delete:0},pending=[];
 for(let i=0;i<n;i++){const id=String(1000+i)+'_abcdef',p='internal://files/s5r_'+id;
  files.set(p+'_head.json',JSON.stringify({kind:'head',schema_version:2,session_id:id,started_epoch_ms:1000}));files.set(p+'_b0000.json','{}');
  files.set(p+'_tail.json',JSON.stringify({kind:'tail',session_id:id,blocks:1,persisted:i+1,stopped_epoch_ms:2000,quality:{warnings:[]}}));}
 const file={list:o=>{calls.list++;o.success({fileList:[...files.keys()].map(uri=>({uri:uri.replace('files/','files//')}))});},readText:o=>{calls.read++;files.has(o.uri)?o.success({text:files.get(o.uri)}):o.fail('missing',404);},writeText:o=>{calls.write++;files.set(o.uri,o.text);o.success();},delete:o=>{calls.delete++;files.delete(o.uri);o.success();}};
 const base=core.createStore(file,{now:()=>1000000}),store=catalog.wrap(base,file);
 return {files,file,calls,base,store,pending};
}
async function settle(){for(let i=0;i<8;i++)await new Promise(setImmediate);}
function pageRig(n=26){const r=rig(n),context={sensor:{},sensorCapture:{},screenGuard:{},file:r.file,research:core,recordCatalog:catalog,legacyCore:{},transfer:{},interconnect:{},inputProbe:{},storageDiagnostic:{},Date,Math,JSON,Promise,setTimeout,clearTimeout,setInterval:()=>1,clearInterval(){},require:()=>{throw Error('list must not alter screen');}};
 vm.createContext(context);vm.runInContext(ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result='),context);
 r.page=Object.assign({},context.result.private,context.result);r.page.onInit();return r;}
test('26 summaries survive warm return while explicit refresh still scans',async()=>{
 const r=rig();const items=await r.store.list(false);for(const item of items)await r.store.describe(item.id);
 await r.store.list(false,{reuse:true});for(const item of items)await r.store.describe(item.id);
 assert.equal(r.calls.list,1);assert.equal(r.calls.read,52);assert.equal(r.store.catalogState().source,'cached');
 await r.store.list(false);assert.equal(r.calls.list,2);assert.equal(r.store.catalogState().source,'fresh');
});
test('39/40/41 can browse; window never hides overflow and old core list is bypassed',async()=>{
 for(const n of [39,40,41]){const r=rig(n);r.base.list=()=>{throw Error('base list should not run');};const s=catalog.wrap(r.base,r.file);
  const a=await s.list(false);assert.equal(a.length,Math.min(n,40));assert.equal(s.catalogState().total,n);
  if(n===41){assert.equal((await s.list(false,{reuse:true,offset:40})).length,1);assert.equal(r.calls.list,1);}
 }
});
test('capacity uses all heads including trash and rejects before any head write',async()=>{
 const r=rig(40);r.files.set('internal://files/s5r_1039_abcdef_trash.json','{}');assert.equal((await r.store.list(false)).length,39);
 assert.equal(r.store.catalogState().used,40);assert.equal(r.store.catalogState().trashed,1);
 await assert.rejects(r.store.start({durationSeconds:60,sensorPath:'generic',interval:'high'}),/回收区.*占/);assert.equal(r.calls.write,0);
 const q=rig(39);await q.store.start({durationSeconds:60,sensorPath:'generic',interval:'high'});assert.equal(q.calls.write,1);
});
test('export and trash always rescan source despite warm advisory cache',async()=>{
 const r=rig(40);await r.store.list(false);await r.store.describe('1039_abcdef');const before=r.calls.list;await r.store.inventory('1039_abcdef');assert.ok(r.calls.list>before);
 r.files.set('internal://files/s5r_1039_abcdef_b0002.json','{}');await assert.rejects(r.store.trash('1039_abcdef'));assert.equal(r.calls.write,0);
});
test('restore checks live source and fails visibly without deleting a marker on bad source',async()=>{
 const r=rig(1);r.files.set('internal://files/s5r_1000_abcdef_trash.json','{}');await r.store.list(true);await r.store.describe('1000_abcdef');
 r.files.delete('internal://files/s5r_1000_abcdef_head.json');await assert.rejects(r.store.restore('1000_abcdef'));assert.equal(r.calls.delete,0);
});
test('failed refresh invalidates cached listing and cannot silently fall back',async()=>{
 const r=rig();await r.store.list(false);r.file.list=o=>o.fail('disk',5);await assert.rejects(r.store.list(false));await assert.rejects(r.store.list(false,{reuse:true}));await assert.rejects(r.store.describe('1025_abcdef'));
});
test('late list cannot repopulate a cache invalidated by local mutation',async()=>{
 const r=rig();r.file.list=o=>r.pending.push(o);const list=r.store.list(false);const outcome=list.then(()=>false,()=>true);
 r.store.invalidateCatalog();r.pending[0].success({fileList:[...r.files.keys()].map(uri=>({uri}))});assert.equal(await outcome,true);assert.equal(r.store.catalogState().available,false);
});
test('late summary cannot repopulate invalidated snapshot',async()=>{
 const r=rig();await r.store.list(false);let pending;r.file.readText=o=>{pending=o;};const p=r.store.describe('1025_abcdef'),out=p.then(()=>false,()=>true);await settle();
 r.store.invalidateCatalog();pending.success({text:r.files.get(pending.uri)});await settle();if(pending.uri.endsWith('_tail.json'))pending.success({text:r.files.get(pending.uri)});
 assert.equal(await out,true);assert.equal(r.store.catalogState().available,false);
});
test('mutation completion also invalidates snapshots created while it was pending',async()=>{
 const r=rig(1);let resolve;r.base.trash=()=>new Promise(ok=>{resolve=ok;});const s=catalog.wrap(r.base,r.file);const p=s.trash('1000_abcdef');await settle();await s.list(false);resolve();await p;
 assert.equal(s.catalogState().available,false);
});
test('actual page warm return, visible refresh and trash toggle use intentional reuse',async()=>{
 const r=pageRig();r.page.showRecords();await settle();assert.equal(r.page.recordPosition,'1 / 26');assert.equal(r.calls.list,1);assert.equal(r.calls.read,2);
 r.page.showCollect();r.page.showRecords();await settle();assert.equal(r.calls.list,1);assert.match(r.page.catalogNote,/缓存/);
 r.page.reloadRecords();await settle();assert.equal(r.calls.list,2);assert.match(r.page.catalogNote,/已刷新/);
 r.page.toggleTrash();await settle();assert.equal(r.calls.list,2);assert.match(ux,/onclick="reloadRecords"/);
});
test('actual page crosses overflow window and wraps both directions without dropping records',async()=>{
 const r=pageRig(41);r.page.showRecords();await settle();assert.equal(r.page.recordPosition,'1 / 41');
 r.page.previousRecord();await settle();assert.equal(r.page.recordPosition,'41 / 41');r.page.nextRecord();await settle();assert.equal(r.page.recordPosition,'1 / 41');
 for(let i=0;i<40;i++){r.page.nextRecord();await settle();}assert.equal(r.page.recordPosition,'41 / 41');assert.equal(r.calls.list,1);
});
test('actual page shows capacity separately from corruption; refresh error clears actionable selection',async()=>{
 const r=pageRig(40);r.files.set('internal://files/s5r_1039_abcdef_tail.json','bad');r.page.showRecords();await settle();
 assert.match(r.page.recordQuality,/损坏/);assert.match(r.page.capacityText,/40.*回收区.*占/);
 r.file.list=o=>o.fail('disk',5);r.page.reloadRecords();await settle();assert.equal(r.page.alert,true);assert.equal(r.page._items.length,0);assert.match(r.page.catalogNote,/失败/);
});
test('unchanged corrupt/interrupted sessions remain visible; diagnostics stay in memory',async()=>{
 const r=rig(3);r.files.delete('internal://files/s5r_1000_abcdef_tail.json');r.files.set('internal://files/s5r_1001_abcdef_head.json','bad');
 assert.equal((await r.store.list(false)).length,3);assert.equal((await r.store.describe('1000_abcdef')).state,'interrupted');assert.equal((await r.store.describe('1001_abcdef')).state,'corrupt');
 const d=r.store.catalogState();assert.ok(d.timing.native_list_ms>=0);assert.ok(d.timing.organize_ms>=0);assert.ok(d.timing.summary_ms>=0);assert.equal(r.calls.write+r.calls.delete,0);
});
test('refresh rechecks content even when filenames are unchanged',async()=>{
 const r=rig(1);await r.store.list(false);assert.equal((await r.store.describe('1000_abcdef')).state,'sealed');
 r.files.set('internal://files/s5r_1000_abcdef_head.json','bad');await r.store.list(false,{reuse:true});assert.equal((await r.store.describe('1000_abcdef')).state,'sealed');
 await r.store.list(false);assert.equal((await r.store.describe('1000_abcdef')).state,'corrupt');
});
test('latest refresh wins and late earlier failure cannot clear its snapshot',async()=>{
 const r=rig(1);r.file.list=o=>r.pending.push(o);const a=r.store.list(false).then(()=>false,()=>true),b=r.store.list(false);
 r.pending[1].success({fileList:[...r.files.keys()].map(uri=>({uri}))});await b;r.pending[0].fail('old',5);assert.equal(await a,true);assert.equal(r.store.catalogState().available,true);
});
test('successful trash/restore invalidate warm results; purge is live and confirmation guarded',async()=>{
 const r=rig(1);await r.store.list(false);await r.store.describe('1000_abcdef');await r.store.trash('1000_abcdef');assert.equal(r.store.catalogState().available,false);
 assert.equal((await r.store.list(false,{reuse:true})).length,0);assert.equal((await r.store.list(true,{reuse:true})).length,1);
 await r.store.restore('1000_abcdef');assert.equal(r.store.catalogState().available,false);assert.equal((await r.store.list(false,{reuse:true})).length,1);
 await assert.rejects(r.store.purge('1000_abcdef','wrong'));assert.equal(r.calls.delete,1);
 await r.store.trash('1000_abcdef');r.files.set('internal://files/s5r_1000_abcdef_tail.json','bad');const deletes=r.calls.delete;
 await assert.rejects(r.store.purge('1000_abcdef','1000_abcdef'));assert.equal(r.calls.delete,deletes);
});
test('page hide cancels only catalog UI, and late read cannot replace new selection',async()=>{
 const r=pageRig(2);let first;r.file.list=o=>{first=o;};r.page.showRecords();r.page.onHide();assert.equal(r.page.loading,false);
 r.file.list=o=>o.success({fileList:[...r.files.keys()].map(uri=>({uri}))});r.page.onShow();r.page.showRecords();await settle();r.page.nextRecord();await settle();const title=r.page.recordTitle;
 first.success({fileList:[]});await settle();assert.equal(r.page.recordTitle,title);assert.equal(r.page.recordPosition,'2 / 2');
});
test('41st record remains exportable and bounded summary cache evicts older entries',async()=>{
 const r=rig(41);const first=await r.store.list(false);for(const item of first)await r.store.describe(item.id);
 const overflow=await r.store.list(false,{reuse:true,offset:40});await r.store.describe(overflow[0].id);const reads=r.calls.read;await r.store.describe(first[0].id);assert.equal(r.calls.read,reads+2);
 const before=r.calls.list,inv=await r.store.inventory(overflow[0].id);assert.equal(inv.id,overflow[0].id);assert.ok(r.calls.list>before);
});
test('resume after hide during list reloads the cancelled display without another tab tap',async()=>{
 const r=pageRig(2);let first;r.file.list=o=>{first=o;};r.page.showRecords();r.page.onHide();
 r.file.list=o=>o.success({fileList:[...r.files.keys()].map(uri=>({uri}))});r.page.onShow();await settle();
 assert.equal(r.page.recordPosition,'1 / 2');assert.match(r.page.recordDetail,/2条/);first.success({fileList:[]});await settle();assert.equal(r.page.recordPosition,'1 / 2');
});
