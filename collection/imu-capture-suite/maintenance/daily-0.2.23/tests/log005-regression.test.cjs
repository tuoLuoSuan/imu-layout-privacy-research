const test=require('node:test'),assert=require('node:assert/strict');
const {fixture,page}=require('./fixtures.cjs');
const consent=s=>({token:s.token,preparedId:s.prepared_id,confirmBackup:true,confirmUnbackedLoss:true,confirmFailedRecord:true,confirmPermanent:true});

test('back button does not call framework lifecycle hooks on the page instance',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();
 const hook=p.onDestroy;delete p.onDestroy;
 await assert.doesNotReject(async()=>p.secondary());
 assert.equal(p._destroyed,true);assert.equal(f.calls.delete.length,0);
 await Promise.resolve(hook.call(p));
});

test('back button falls back when native replace is unavailable',async()=>{
 const f=fixture(),routes=[];f.router={push:o=>routes.push(o.uri)};const p=page('Manage',f);await p.onShow();delete p.onDestroy;
 await p.secondary();assert.deepEqual(routes,['/Menu']);assert.equal(f.calls.delete.length,0);
});

for(const mode of ['empty','head_omitted'])test('exact get confirms a readable head after '+mode+' list',async()=>{
 const f=fixture(),gets=[];f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');
 f.file.list=o=>o.success({fileList:mode==='empty'?[]:[{uri:f.dir(0)+f.prefix(0)+'b0000.json'}]});
 f.file.get=o=>{gets.push(o.uri);o.success({type:'dir',uri:o.uri,subFiles:[...f.files.keys()].filter(u=>u.startsWith(o.uri)).map(uri=>({uri}))});};
 const a=require('../src/common/records-fast-delete.js').create({file:f.file,recoveryDirectories:f.targets.map((t,i)=>f.dir(i))}),id=(await a.scan()).find(x=>x.id.endsWith('_j_1')).id;
 const state=await a.prepareSelection([id]);assert.equal(f.calls.delete.length,0);await a.purge(consent(state));
 assert.equal(f.calls.delete.length,2);assert.ok(gets.length<=2);assert.ok(gets.every(u=>u===f.dir(0)));assert.ok(f.files.has(f.dir(1)+f.prefix(1)+'head.json'));
});

test('two empty directory results report uncertainty rather than claiming mutation',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');
 f.file.list=o=>o.success({fileList:[]});f.file.get=o=>o.success({type:'dir',uri:o.uri,subFiles:[]});
 const a=require('../src/common/records-fast-delete.js').create({file:f.file,recoveryDirectories:f.targets.map((t,i)=>f.dir(i))}),id=(await a.scan()).find(x=>x.id.endsWith('_j_1')).id;
 await assert.rejects(()=>a.prepareSelection([id]),e=>/目录|名单/.test(e.message)&&!/已改变/.test(e.message));assert.equal(f.calls.delete.length,0);
});

test('tail appearing in unfinished listing is not silently ignored',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');
 f.file.list=o=>o.success({fileList:[{uri:f.dir(0)+f.prefix(0)+'head.json'},{uri:f.dir(0)+f.prefix(0)+'tail.json'}]});
 const a=require('../src/common/records-fast-delete.js').create({file:f.file,recoveryDirectories:f.targets.map((t,i)=>f.dir(i))}),id=(await a.scan()).find(x=>x.id.endsWith('_j_1')).id;
 await assert.rejects(()=>a.prepareSelection([id]),/封口/);assert.equal(f.calls.delete.length,0);
});
