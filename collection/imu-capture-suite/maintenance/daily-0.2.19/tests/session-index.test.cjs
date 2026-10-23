const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const records=require('../src/common/records.js'),{fixture,page,settle}=require('./fixtures.cjs');
const modulePath=path.join(__dirname,'../src/common/session-index.js'),ROOT='internal://files/';
test('complete sessions gain a root locator without changing capture files',async()=>{
 assert.ok(fs.existsSync(modulePath),'session-index module required');const index=require(modulePath),f=fixture(),before=[...f.files];
 f.file.writeText=o=>{f.files.set(o.uri,o.text);o.success();};const t=f.targets[0];
 const s=await index.remember(f.file,{phase:'complete',native_sid:t.native_sid,sid:t.sid,session_root_uri:f.dir(0)});
 assert.equal(s.status,'saved');for(const [u,text] of before)assert.equal(f.files.get(u),text);
 assert.ok([...f.files.keys()].some(u=>u.startsWith(ROOT+'s5loc_')));assert.equal(f.calls.delete.length,0);
});
test('a root locator recovers a session even when both native directory interfaces omit its directory',async()=>{
 const f=fixture(),t=f.targets[0],uri=ROOT+'s5loc_'+t.native_sid+'_'+t.sid+'.json';
 f.files.set(uri,JSON.stringify({schema:1,kind:'session_locator',native_sid:t.native_sid,sid:t.sid,dir:f.dir(0)}));
 const list=f.file.list;f.file.list=o=>o.uri===ROOT?o.success({fileList:[{uri}]}):list(o);
 const a=records.create({file:f.file}),items=await a.scan();assert.equal(items.length,1);assert.equal((await a.summary(items[0].id)).complete,true);assert.equal(f.calls.delete.length,0);
});
test('a forged locator cannot grant deletion scope or import a foreign path',async()=>{
 const f=fixture(),t=f.targets[0],uri=ROOT+'s5loc_'+t.native_sid+'_'+t.sid+'.json';
 f.files.set(uri,JSON.stringify({schema:1,kind:'session_locator',native_sid:t.native_sid,sid:t.sid,dir:'internal://cache/'}));
 f.file.list=o=>o.success({fileList:o.uri===ROOT?[{uri}]:[]});const a=records.create({file:f.file});assert.equal((await a.scan()).length,0);assert.equal(f.calls.delete.length,0);assert.ok(f.calls.read.every(u=>u.startsWith(ROOT)));
});
test('locator write failure does not rewrite a completed acquisition as failed',async()=>{
 assert.ok(fs.existsSync(modulePath));const index=require(modulePath),f=fixture(),t=f.targets[0],s={phase:'complete',native_sid:t.native_sid,sid:t.sid,session_root_uri:f.dir(0)};
 f.file.writeText=o=>o.fail('no space',300);const r=await index.remember(f.file,s);assert.equal(r.status,'unavailable');assert.equal(s.phase,'complete');assert.equal(f.calls.delete.length,0);
});
test('locator write is not started for an unfinished acquisition',async()=>{
 assert.ok(fs.existsSync(modulePath));const f=fixture();f.file.writeText=()=>{throw Error('no early writes');};
 assert.equal((await require(modulePath).remember(f.file,{phase:'recording'})).status,'skipped');assert.equal(f.calls.delete.length,0);
});
test('an existing different locator is never overwritten as a shortcut',async()=>{
 const index=require(modulePath),f=fixture(),t=f.targets[0],uri=ROOT+'s5loc_'+t.native_sid+'_'+t.sid+'.json';f.files.set(uri,'unrecognized content');
 f.file.writeText=()=>{throw Error('must preserve unknown existing metadata');};
 const r=await index.remember(f.file,{phase:'complete',native_sid:t.native_sid,sid:t.sid,session_root_uri:f.dir(0)});
 assert.equal(r.status,'unavailable');assert.equal(f.files.get(uri),'unrecognized content');assert.equal(f.calls.delete.length,0);
});
test('a stale locator whose real head no longer exists cannot invent a selectable record',async()=>{
 const f=fixture(),t=f.targets[0],uri=ROOT+'s5loc_'+t.native_sid+'_'+t.sid+'.json';f.files.clear();f.files.set(uri,JSON.stringify({schema:1,kind:'session_locator',native_sid:t.native_sid,sid:t.sid,dir:f.dir(0)}));
 f.file.list=o=>o.success({fileList:o.uri===ROOT?[{uri}]:[]});const a=records.create({file:f.file});assert.equal((await a.scan()).length,0);assert.equal(f.calls.delete.length,0);
});
