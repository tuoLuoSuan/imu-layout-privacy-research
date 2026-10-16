const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.join(__dirname,'..'),core=require('../variants/research-recorder/src/common/research.js');
const modulePath=path.join(root,'variants/catalog-recorder/src/common/record-catalog.js');
function rig(n=40){
 const files=new Map(),calls={list:0,read:[],write:0,delete:0};
 for(let i=0;i<n;i++){
  const id=String(1000+i)+'_abcdef',p='internal://files/s5r_'+id;
  files.set(p+'_head.json',JSON.stringify({kind:'head',schema_version:2,session_id:id,started_epoch_ms:1000}));
  files.set(p+'_b0000.json','{}');
  files.set(p+'_tail.json',JSON.stringify({kind:'tail',schema_version:2,session_id:id,blocks:1,persisted:i+1,stopped_epoch_ms:2000,stop_reason:'duration',quality:{warnings:[]}}));
 }
 const file={list:o=>{calls.list++;o.success({fileList:[...files.keys()].map(uri=>({uri}))});},readText:o=>{calls.read.push(o.uri);files.has(o.uri)?o.success({text:files.get(o.uri)}):o.fail('missing',404);},writeText:o=>{calls.write++;files.set(o.uri,o.text);o.success();},delete:o=>{calls.delete++;files.delete(o.uri);o.success();}};
 const base=core.createStore(file),store=fs.existsSync(modulePath)?require(modulePath).wrap(base,file,require('../variants/directory-uri-fix/src/common/directory-entries.js').normalize):base;
 return {files,calls,file,base,store};
}
test('40 records list once without eagerly reading any head or tail',async()=>{
 const r=rig(),items=await r.store.list(false);assert.equal(items.length,40);assert.equal(r.calls.list,1);assert.equal(r.calls.read.length,0);assert.equal(items[0].id,'1039_abcdef');
});
test('selected summary reads two JSONs, no repeated directory or sample blocks; revisit uses bounded cache',async()=>{
 const r=rig();await r.store.list(false);const a=await r.store.describe('1039_abcdef');assert.equal(a.count,40);assert.equal(a.state,'sealed');
 assert.equal(r.calls.list,1);assert.equal(r.calls.read.length,2);assert.ok(r.calls.read.every(p=>/_head.json$|_tail.json$/.test(p)));
 await r.store.describe('1038_abcdef');await r.store.describe('1039_abcdef');assert.equal(r.calls.read.length,4);
});
test('trash filter and deleting marker are resolved before metadata reads',async()=>{
 const r=rig(3);r.files.set('internal://files/s5r_1002_abcdef_trash.json','{}');r.files.set('internal://files/s5r_1001_abcdef_purge.json','{}');
 assert.deepEqual((await r.store.list(false)).map(x=>x.id),['1000_abcdef']);assert.equal(r.calls.read.length,0);
 const trash=await r.store.list(true);assert.equal(trash.length,2);assert.equal((await r.store.describe('1001_abcdef')).state,'deleting');assert.equal(r.calls.read.length,0);
});
test('interrupted, corrupt and missing-block sessions remain visible without changing files',async()=>{
 const r=rig(3);r.files.delete('internal://files/s5r_1000_abcdef_tail.json');r.files.set('internal://files/s5r_1001_abcdef_head.json','broken');r.files.set('internal://files/s5r_1002_abcdef_b0002.json','{}');
 await r.store.list(false);assert.equal((await r.store.describe('1000_abcdef')).state,'interrupted');assert.equal((await r.store.describe('1001_abcdef')).state,'corrupt');assert.equal((await r.store.describe('1002_abcdef')).state,'corrupt');
 assert.equal(r.calls.write+r.calls.delete,0);
});
test('warm cache never authorizes export or mutation and refresh detects structural changes',async()=>{
 const r=rig(1);await r.store.list(false);await r.store.describe('1000_abcdef');r.files.delete('internal://files/s5r_1000_abcdef_b0000.json');
 await assert.rejects(()=>r.store.inspect('1000_abcdef'));await r.store.list(false);assert.equal((await r.store.describe('1000_abcdef')).state,'corrupt');
});
test('mutation invalidates advisory cache but executes the original store safety checks',async()=>{
 const r=rig(1);await r.store.list(false);await r.store.describe('1000_abcdef');await r.store.trash('1000_abcdef');
 assert.ok(r.calls.list>1);assert.ok(r.files.has('internal://files/s5r_1000_abcdef_trash.json'));assert.equal((await r.store.list(false)).length,0);assert.equal((await r.store.list(true)).length,1);
 await r.store.restore('1000_abcdef');await r.store.list(false);const reads=r.calls.read.length;await r.store.describe('1000_abcdef');assert.equal(r.calls.read.length,reads+2);
 await assert.rejects(()=>r.store.purge('1000_abcdef','1000_abcdef'));assert.ok(r.files.has('internal://files/s5r_1000_abcdef_head.json'));
});
test('cache holds at most eight summaries and cold directory failures never fall back to old results',async()=>{
 const r=rig(10);const items=await r.store.list(false);for(const i of items)await r.store.describe(i.id);
 const reads=r.calls.read.length;await r.store.describe(items[0].id);assert.equal(r.calls.read.length,reads+2);
 r.file.list=o=>o.fail('disk',5);await assert.rejects(()=>r.store.list(false));await assert.rejects(()=>r.store.describe(items[0].id));
});
