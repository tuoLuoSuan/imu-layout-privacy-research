const test=require('node:test'),assert=require('node:assert/strict');
const records=require('../src/common/records.js');
function setup(){
 const native='11111111-1111-4111-8111-111111111111',sid='j_a',name='s5joint_'+native+'_'+sid,dir='internal://files/'+name+'/',p='s5joint_'+sid+'_';
 const end={p:'J_END1',native_sid:native,sid,count:2,blocks:1,start_ms:100,stop_ms:1000,clock_observations:1,stop_reason:'duration'};
 const head={kind:'head',schema_version:1,sid,native_sid:native,started_epoch_ms:100,requested_duration_ms:120000,app_version:'0.2.5',storage_strategy:'isolated_session_directory',storage_root_uri:dir,sensor_path:'generic',requested_interval:'high',acceleration_unit:'unknown',axis_convention:'unverified',hardware_timestamp:false,wrist:'not_recorded'};
 const data=new Map([[dir+p+'head.json',JSON.stringify(head)],[dir+p+'b0000.json',JSON.stringify([[0,100,1,2,3],[1,160,2,3,4]])],[dir+p+'tail.json',JSON.stringify(end)],['internal://files/legacy.json','preserve']]);
 const calls={list:[],read:[],delete:[]};
 const file={list(o){calls.list.push(o.uri);o.success({fileList:o.uri==='internal://files/'?[{uri:dir},{uri:'internal://files/legacy.json'}]:[...data.keys()].filter(u=>u.startsWith(o.uri)).map(uri=>({uri}))});},readText(o){calls.read.push(o.uri);data.has(o.uri)?o.success({text:data.get(o.uri)}):o.fail('missing',301);},delete(o){calls.delete.push(o.uri);data.delete(o.uri);o.success({});}};
 return {api:records.create({file}),data,calls,name,dir,p};
}
test('record scan is read-only and does not include legacy/unrelated files',async()=>{const r=setup(),list=await r.api.scan();assert.equal(list.length,1);assert.equal(list[0].id,r.name);assert.equal(r.calls.delete.length,0);});
test('selected summary reads metadata but never deletes',async()=>{const r=setup();await r.api.scan();const s=await r.api.summary(r.name);assert.equal(s.complete,true);assert.equal(s.rows,2);assert.equal(r.calls.delete.length,0);});
test('deletion preparation refuses absent export confirmation',async()=>{const r=setup();await r.api.scan();await assert.rejects(()=>r.api.prepareDelete(r.name,false));assert.equal(r.calls.delete.length,0);});
test('generic cleanup labels export as participant confirmed, not PC verified',async()=>{const r=setup();await r.api.scan();const s=await r.api.prepareDelete(r.name,true);assert.equal(s.backup_basis,'user_confirmed_export');assert.equal(s.phase,'ready');assert.equal(r.calls.delete.length,0);});
test('explicit selected-record purge keeps unrelated data',async()=>{const r=setup();await r.api.scan();const s=await r.api.prepareDelete(r.name,true);await r.api.purge({token:s.token,preparedId:s.prepared_id,confirmBackup:true,confirmPermanent:true});assert.equal(r.calls.delete.length,3);assert.equal(r.data.get('internal://files/legacy.json'),'preserve');});
test('unknown target not present in scan is rejected',async()=>{const r=setup();await r.api.scan();await assert.rejects(()=>r.api.prepareDelete('../elsewhere',true));assert.equal(r.calls.delete.length,0);});
test('incomplete records are retained rather than called backed up',async()=>{const r=setup();r.data.delete(r.dir+r.p+'tail.json');await r.api.scan();const s=await r.api.summary(r.name);assert.equal(s.complete,false);await assert.rejects(()=>r.api.prepareDelete(r.name,true));assert.equal(r.calls.delete.length,0);});
test('unrecognized files inside selected directory block deletion',async()=>{const r=setup();r.data.set(r.dir+'not-backed-up.json','keep');await r.api.scan();await assert.rejects(()=>r.api.prepareDelete(r.name,true));assert.equal(r.calls.delete.length,0);});
test('bad row order is rejected before cleanup',async()=>{const r=setup();r.data.set(r.dir+r.p+'b0000.json',JSON.stringify([[3,100,1,2,3],[4,160,2,3,4]]));await r.api.scan();await assert.rejects(()=>r.api.prepareDelete(r.name,true));assert.equal(r.calls.delete.length,0);});
