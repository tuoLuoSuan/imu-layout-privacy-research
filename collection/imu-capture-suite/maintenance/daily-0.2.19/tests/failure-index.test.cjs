const test=require('node:test'),assert=require('node:assert/strict');
const {fixture,page,settle}=require('./fixtures.cjs');
test('terminal failure stores only a future discovery identity, not during recording',async()=>{
 const f=fixture(),catalog=require('../src/common/catalog-index.js');f.files.delete('internal://files/s5catalog_v2.json');f.file.writeText=o=>{f.files.set(o.uri,o.text);o.success();};const before=new Map(f.files),t=f.targets[0],p=page('Probe',f),s={native_sid:t.native_sid,sid:t.sid,session_root_uri:f.dir(0),count:2,elapsed_ms:900,clock_observations:1};p.update({...s,phase:'recording'},0);await settle();assert.equal(f.files.has('internal://files/s5catalog_v2.json'),false);p.update({...s,phase:'failed',error:'simulated failure'},0);await settle();assert.equal((await catalog.load(f.file)).hints.length,1);for(const [u,text] of before)assert.equal(f.files.get(u),text);assert.equal(f.calls.delete.length,0);p.onDestroy();
});
