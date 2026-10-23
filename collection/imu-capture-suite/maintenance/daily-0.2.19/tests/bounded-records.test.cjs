const test=require('node:test'),assert=require('node:assert/strict');
const {fixture}=require('./fixtures.cjs');
const core=require('../src/common/records.js');
function api(f){return require('../src/common/records-bounded.js').create({file:f.file,recoveryDirectories:f.targets.map((t,i)=>f.dir(i))});}
const consent=s=>({token:s.token,preparedId:s.prepared_id,confirmBackup:true,confirmUnbackedLoss:true,confirmFailedRecord:true,confirmPartial:true,confirmPermanent:true});
test('fast identity scan never enumerates native root or block directories',async()=>{
 const f=fixture();f.file.list=()=>{throw Error('huge native directory must not be materialized');};f.file.get=f.file.list;const a=api(f),list=await a.scan();assert.equal(list.length,2);for(const e of list){const s=await a.summary(e.id);assert.equal(s.sealed,true);assert.equal(s.complete,false);assert.equal(s.blocks_verified,false);}assert.equal(f.calls.list.length,0);assert.equal(f.calls.delete.length,0);
});
test('tail metadata with a missing block is never advertised complete by fast preview',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'b0000.json');const a=api(f),list=await a.scan(),s=await a.summary(list.find(e=>e.id.endsWith('_j_1')).id);assert.equal(s.sealed,true);assert.equal(s.complete,false);assert.equal(s.blocks_verified,false);
});
test('batch retains only small signatures after preparation, and purge removes selected data',async()=>{
 const f=fixture(),a=api(f),ids=(await a.scan()).map(e=>e.id),s=await a.prepareSelection(ids);assert.equal(s.files,6);assert.equal(s.retained_full_file_records,0);assert.equal(s.retained_signature_records,2);assert.equal(f.calls.delete.length,0);const r=await a.purge(consent(s));assert.equal(r.phase,'complete');assert.equal(r.verified_absent_files,6);a.forgetDeleted(ids);assert.equal(f.calls.delete.length,6);assert.equal(f.files.get('internal://files/unrelated.json'),'keep');
});
test('a later record changed after consent is detected before the first deletion',async()=>{
 const f=fixture(),a=api(f),ids=(await a.scan()).map(e=>e.id),s=await a.prepareSelection(ids);f.files.set(f.dir(1)+f.prefix(1)+'b0000.json','[[0,100,9,2,3],[1,160,2,3,4]]');await assert.rejects(()=>a.purge(consent(s)),/改变/);assert.equal(f.calls.delete.length,0);
});
test('one native deletion error stops the entire bounded batch',async()=>{
 const f=fixture(),a=api(f),ids=(await a.scan()).map(e=>e.id),s=await a.prepareSelection(ids);f.file.delete=o=>{f.calls.delete.push(o.uri);o.fail('native error',5);};await assert.rejects(()=>a.purge(consent(s)));assert.equal(f.calls.delete.length,1);assert.equal(a.state().phase,'error');
});
test('cancelling a prepared batch invalidates its token without changing original bytes',async()=>{
 const f=fixture(),old=new Map(f.files),a=api(f),ids=(await a.scan()).map(e=>e.id),s=await a.prepareSelection(ids);a.cancel();await assert.rejects(()=>a.purge(consent(s)));for(const [u,v] of old)assert.equal(f.files.get(u),v);assert.equal(f.calls.delete.length,0);
});
test('mixed partial and unfinished records keep explicit consent gates',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'b0000.json');f.files.delete(f.dir(1)+f.prefix(1)+'tail.json');const a=api(f),ids=(await a.scan()).map(e=>e.id),s=await a.prepareSelection(ids);assert.equal(s.partial_sessions,1);assert.equal(s.incomplete_sessions,1);await assert.rejects(()=>a.purge({...consent(s),confirmUnbackedLoss:false}));assert.equal(f.calls.delete.length,0);await a.purge(consent(s));assert.equal(f.calls.delete.length,4);
});
test('core can release an idle prepared graph, never exposing it as reusable consent',async()=>{
 const f=fixture(),a=core.create({file:f.file}),ids=(await a.scan()).map(e=>e.id);await a.prepareSelection([ids[0]]);assert.equal(typeof a.releasePrepared,'function');a.releasePrepared();assert.equal(a.state().phase,'idle');assert.equal(f.calls.delete.length,0);
});
test('a newly indexed session can be found without a native root scan',async()=>{
 const f=fixture(),catalog=require('../src/common/catalog-index.js');f.files.delete('internal://files/s5catalog_v2.json');f.file.writeText=o=>{f.files.set(o.uri,o.text);o.success();};const t=f.targets[0];assert.equal((await catalog.add(f.file,[t.native_sid,t.sid,'i'])).ok,true);const a=require('../src/common/records-bounded.js').create({file:f.file,recoveryDirectories:[]}),list=await a.scan();assert.equal(list.length,1);assert.equal(f.calls.list.length,0);
});
test('post-completion recording metadata makes the next session discoverable without root enumeration',async()=>{
 const f=fixture(),index=require('../src/common/session-index.js');f.files.delete('internal://files/s5catalog_v2.json');f.file.writeText=o=>{f.files.set(o.uri,o.text);o.success();};const t=f.targets[0];await index.remember(f.file,{phase:'complete',native_sid:t.native_sid,sid:t.sid,session_root_uri:f.dir(0)});const a=require('../src/common/records-bounded.js').create({file:f.file,recoveryDirectories:[]}),items=await a.scan();assert.equal(items.length,1);assert.equal(f.calls.list.length,0);
});
test('if a later record changes during the batch, only already verified removals are reported',async()=>{
 const f=fixture(),a=api(f),ids=(await a.scan()).map(e=>e.id),s=await a.prepareSelection(ids),del=f.file.delete;f.file.delete=o=>{if(o.uri===f.dir(0)+f.prefix(0)+'tail.json')f.files.set(f.dir(1)+f.prefix(1)+'b0000.json','[[0,100,9,2,3],[1,160,2,3,4]]');del(o);};await assert.rejects(()=>a.purge(consent(s)),/改变/);assert.equal(f.calls.delete.length,3);assert.equal(a.state().removed_ids.length,1);assert.equal(a.state().verified_absent_files,3);
});
