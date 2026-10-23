const test=require('node:test'),assert=require('node:assert/strict');
const records=require('../src/common/records.js'),{fixture}=require('./fixtures.cjs');
const ROOT='internal://files/';
const consent=s=>({token:s.token,preparedId:s.prepared_id,confirmBackup:true,confirmUnbackedLoss:true,confirmFailedRecord:true,confirmPartial:true,confirmPermanent:true});
function setup(){
 const f=fixture(),t=f.targets[0],source=f.dir(0),prefix=f.prefix(0);
 for(const [u,text] of [...f.files])if(u.startsWith(source)){f.files.delete(u);let value=text;if(u.endsWith('_head.json')){const h=JSON.parse(text);delete h.storage_root_uri;delete h.storage_strategy;h.app_version='0.2.3';value=JSON.stringify(h);}f.files.set(ROOT+u.slice(source.length),value);}
 f.mode='normal';let rootCalls=0;const stale=[];
 f.file.list=o=>{f.calls.list.push(o.uri);let uris=[];for(const u of f.files.keys())if(u.startsWith(o.uri)){const r=u.slice(o.uri.length),i=r.indexOf('/'),name=i<0?u:o.uri+r.slice(0,i+1);if(!uris.includes(name))uris.push(name);}
  if(o.uri===ROOT){rootCalls++;if(!stale.length)stale.push(...uris);if(rootCalls>=3&&f.mode==='omit')uris=uris.filter(u=>u!==ROOT+prefix+'b0000.json');if(rootCalls>=3&&f.mode==='empty')uris=[];if(f.mode==='stale_after_delete'&&f.calls.delete.length)uris=stale;}
  o.success({fileList:uris.map(uri=>({uri}))});
 };
 f.id='flat:'+t.sid;f.block=ROOT+prefix+'b0000.json';f.api=records.create({file:f.file});return f;
}
test('a file omitted from a later list is admitted only after all snapshot bytes still match',async()=>{
 const f=setup();await f.api.scan();f.mode='omit';const s=await f.api.prepareSelection([f.id]);assert.equal(s.phase,'ready');assert.equal(s.files,3);assert.equal(f.calls.delete.length,0);await f.api.purge(consent(s));assert.ok(f.api.state().listing_omission_observations>=1);assert.equal(f.calls.delete.length,3);assert.equal(f.files.get(ROOT+'unrelated.json'),'keep');assert.equal(f.api.state().verified_absent_files,3);
});
test('an empty repeated list cannot hide the selected live snapshot or skip its hash checks',async()=>{
 const f=setup();await f.api.scan();f.mode='empty';const s=await f.api.prepareSelection([f.id]);assert.equal(s.files,3);await f.api.purge(consent(s));assert.equal(f.calls.delete.length,3);assert.ok(!f.files.has(f.block));
});
test('a genuinely missing snapshot member stops before any delete, with exact missing evidence',async()=>{
 const f=setup();await f.api.scan();const s=await f.api.prepareSelection([f.id]);f.files.delete(f.block);await assert.rejects(()=>f.api.purge(consent(s)));assert.equal(f.calls.delete.length,0);const state=f.api.state();assert.equal(state.last_inspection.expected_files,3);assert.equal(state.last_inspection.listed_files,2);assert.equal(state.last_inspection.missing_file,'b0000.json');assert.equal(state.last_inspection.read_error_code,301);
});
test('an omitted member whose bytes changed never receives deletion credit',async()=>{
 const f=setup();await f.api.scan();const s=await f.api.prepareSelection([f.id]);f.mode='omit';f.files.set(f.block,'changed');await assert.rejects(()=>f.api.purge(consent(s)));assert.equal(f.calls.delete.length,0);
});
test('unknown same-SID files still block the complete selected batch even if another member is omitted',async()=>{
 const f=setup();await f.api.scan();const s=await f.api.prepareSelection([f.id]);f.mode='omit';f.files.set(ROOT+f.prefix(0)+'unknown.json','keep');await assert.rejects(()=>f.api.purge(consent(s)));assert.equal(f.calls.delete.length,0);
});
test('stale directory entries after native deletion are checked by explicit not-found reads',async()=>{
 const f=setup();await f.api.scan();const s=await f.api.prepareSelection([f.id]);f.mode='stale_after_delete';await f.api.purge(consent(s));assert.equal(f.calls.delete.length,3);assert.equal(f.api.state().verified_absent_files,3);assert.equal(f.api.state().phase,'complete');
});
test('native success without actual removal cannot pass an empty-list verification',async()=>{
 const f=setup();await f.api.scan();const s=await f.api.prepareSelection([f.id]);f.mode='empty';f.file.delete=o=>{f.calls.delete.push(o.uri);o.success();};await assert.rejects(()=>f.api.purge(consent(s)));assert.equal(f.api.state().phase,'error');assert.equal(f.api.state().uncertain,true);assert.equal(f.api.state().verified_absent_files,0);assert.ok(f.files.has(f.block));
});
test('I/O failure during final absence checks is unknown, never mistaken for missing',async()=>{
 const f=setup();await f.api.scan();const s=await f.api.prepareSelection([f.id]),read=f.file.readText;f.file.readText=o=>f.calls.delete.length===3&&o.uri.startsWith(ROOT+f.prefix(0))?o.fail('io',300):read(o);await assert.rejects(()=>f.api.purge(consent(s)));assert.equal(f.api.state().phase,'error');assert.equal(f.api.state().uncertain,true);
});
test('the safe count error is observable with phase, target and expected/listed counts',async()=>{
 const f=setup();await f.api.scan();const s=await f.api.prepareSelection([f.id]);f.files.delete(f.block);await assert.rejects(()=>f.api.purge(consent(s)));assert.equal(f.api.state().delete_requests,0);assert.equal(f.api.state().delete_acknowledged,0);assert.equal(f.api.state().last_inspection.phase,'rechecking');
});
