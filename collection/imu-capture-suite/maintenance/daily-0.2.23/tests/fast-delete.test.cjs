const test=require('node:test'),assert=require('node:assert/strict');
const {fixture,page,settle}=require('./fixtures.cjs');
const consent=s=>({token:s.token,preparedId:s.prepared_id,confirmBackup:true,confirmUnbackedLoss:true,confirmFailedRecord:true,confirmPartial:true,confirmPermanent:true});
function api(f){return require('../src/common/records-fast-delete.js').create({file:f.file,recoveryDirectories:f.targets.map((t,i)=>f.dir(i))});}

test('ordinary preparation and deletion never read payloads or get directories',async()=>{
 const f=fixture(),read=f.file.readText;f.file.readText=o=>{assert.doesNotMatch(o.uri,/_b\d{4}\.json$/);read(o);};f.file.get=()=>{throw Error('native get must not run');};
 const a=api(f),ids=(await a.scan()).map(x=>x.id),s=await a.prepareSelection(ids);
 assert.equal(f.calls.delete.length,0);assert.equal(s.files,6);assert.equal(s.content_verified,false);
 const result=await a.purge(consent(s));assert.equal(result.delete_acknowledged,6);assert.equal(result.verified_absent_files,0);
 assert.equal(result.verification_mode,'system_acknowledgement_only');assert.equal(f.calls.list.length,0);
 assert.equal(f.files.get('internal://files/unrelated.json'),'keep');a.forgetDeleted(ids);
});

test('selection is constrained to current owned identities',async()=>{
 const f=fixture(),a=api(f),ids=(await a.scan()).map(x=>x.id);
 for(const bad of [[],[ids[0],ids[0]],['../foreign'],['s5joint_other_j_1']])await assert.rejects(()=>a.prepareSelection(bad));
 assert.equal(f.calls.delete.length,0);
});

test('all selected metadata is rechecked before first irreversible call',async()=>{
 const f=fixture(),a=api(f),ids=(await a.scan()).map(x=>x.id),s=await a.prepareSelection(ids);
 const uri=f.dir(1)+f.prefix(1)+'head.json',h=JSON.parse(f.files.get(uri));h.started_epoch_ms++;f.files.set(uri,JSON.stringify(h));
 await assert.rejects(()=>a.purge(consent(s)),/身份|改变/);assert.equal(f.calls.delete.length,0);
});

test('payload content is deliberately not an integrity gate in ordinary delete',async()=>{
 const f=fixture(),a=api(f),ids=(await a.scan()).map(x=>x.id),s=await a.prepareSelection(ids);
 f.files.set(f.dir(0)+f.prefix(0)+'b0000.json','changed payload; user selected this exact record');
 await a.purge(consent(s));assert.equal(f.calls.delete.length,6);
});

test('partial native failure stops after first failed request and retains uncertainty',async()=>{
 const f=fixture(),a=api(f),ids=(await a.scan()).map(x=>x.id),s=await a.prepareSelection(ids);
 f.file.delete=o=>{f.calls.delete.push(o.uri);o.fail('native failure',5);};
 await assert.rejects(()=>a.purge(consent(s)));assert.equal(f.calls.delete.length,1);assert.equal(a.state().uncertain,true);assert.equal(a.state().removed_ids.length,0);
});

test('a delete acknowledgement is not falsely converted to verified absence',async()=>{
 const f=fixture(),a=api(f),ids=(await a.scan()).map(x=>x.id),s=await a.prepareSelection(ids),old=new Map(f.files);
 f.file.delete=o=>{f.calls.delete.push(o.uri);o.success({});};
 const r=await a.purge(consent(s));assert.equal(r.delete_acknowledged,6);assert.equal(r.verified_absent_files,0);for(const [u,v] of old)assert.equal(f.files.get(u),v);
});

test('missing declared block is separately counted, not a failure or invented deletion',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'b0000.json');const del=f.file.delete;
 f.file.delete=o=>{if(!f.files.has(o.uri)){f.calls.delete.push(o.uri);o.fail('missing',301);}else del(o);};
 const a=api(f),ids=(await a.scan()).map(x=>x.id),s=await a.prepareSelection(ids),r=await a.purge(consent(s));
 assert.equal(r.already_absent_files,1);assert.equal(r.delete_acknowledged,5);assert.equal(r.verified_absent_files,0);
});

test('unfinished record uses finite exact file names and explicit loss consent',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');const a=api(f),id=(await a.scan()).find(x=>x.id.endsWith('_j_1')).id,s=await a.prepareSelection([id]);
 assert.equal(s.incomplete_sessions,1);await assert.rejects(()=>a.purge({...consent(s),confirmUnbackedLoss:false}));assert.equal(f.calls.delete.length,0);
 await a.purge(consent(s));assert.equal(f.calls.delete.length,2);assert.equal(f.files.get(f.dir(1)+f.prefix(1)+'b0000.json').length>0,true);
});

test('unfinished record with a foreign listed path is preserved',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');const a=api(f),id=(await a.scan()).find(x=>x.id.endsWith('_j_1')).id;
 f.file.list=o=>o.success({fileList:[{uri:'internal://files/foreign.json'}]});await assert.rejects(()=>a.prepareSelection([id]),/路径|文件|目录/);assert.equal(f.calls.delete.length,0);
});

test('unfinished record accepts a selected root-relative path without stripping foreign namespaces',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');
 f.file.list=o=>o.success({fileList:[...f.files.keys()].filter(u=>u.startsWith(o.uri)).map(uri=>({uri:uri.slice('internal://files/'.length)}))});
 const a=api(f),id=(await a.scan()).find(x=>x.id.endsWith('_j_1')).id,s=await a.prepareSelection([id]);
 await a.purge(consent(s));assert.equal(f.calls.delete.length,2);assert.ok(f.calls.delete.every(u=>u.startsWith(f.dir(0))));
});

test('mis-scoped list may use a single read-only get of the exact selected directory',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');const gets=[];
 f.file.list=o=>o.success({fileList:[{uri:f.dir(1)}]});
 f.file.get=o=>{gets.push(o.uri);assert.equal(o.recursive,true);o.success({uri:o.uri,type:'dir',subFiles:[...f.files.keys()].filter(u=>u.startsWith(o.uri)).map(uri=>({uri}))});};
 const a=api(f),id=(await a.scan()).find(x=>x.id.endsWith('_j_1')).id,s=await a.prepareSelection([id]);
 assert.equal(f.calls.delete.length,0);await a.purge(consent(s));assert.equal(f.calls.delete.length,2);assert.ok(gets.length<=2);assert.ok(gets.every(u=>u===f.dir(0)));
 assert.ok(f.files.has(f.dir(1)+f.prefix(1)+'head.json'));
});

test('unknown leaf inside the selected directory still refuses deletion without fallback',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');f.files.set(f.dir(0)+'unknown.json','keep');
 f.file.get=()=>{throw Error('Unknown same-directory files must not be ignored')};
 const a=api(f),id=(await a.scan()).find(x=>x.id.endsWith('_j_1')).id;
 await assert.rejects(()=>a.prepareSelection([id]),/未知|路径|目录/);assert.equal(f.calls.delete.length,0);assert.equal(f.files.get(f.dir(0)+'unknown.json'),'keep');
});

test('a foreign get directory or child cannot authorize any deletion',async()=>{
 for(const mode of ['parent','child']){
  const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');f.file.list=o=>o.success({fileList:[{uri:f.dir(1)}]});
  f.file.get=o=>o.success({uri:mode==='parent'?f.dir(1):o.uri,type:'dir',subFiles:[{uri:f.dir(1)+f.prefix(1)+'head.json'}]});
  const a=api(f),id=(await a.scan()).find(x=>x.id.endsWith('_j_1')).id;await assert.rejects(()=>a.prepareSelection([id]),/路径|目录/);assert.equal(f.calls.delete.length,0);
 }
});

test('actual page file lane preserves selected root-relative children',async()=>{
 const f=fixture(),p=page('Manage',f),ids=await p._engine.scan(),id=ids.find(x=>x.id.endsWith('_j_1')).id;
 f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');
 f.file.list=o=>{o.success({fileList:[...f.files.keys()].filter(u=>u.startsWith(o.uri)).map(uri=>({uri:uri.slice('internal://files/'.length)}))});if(o.complete)o.complete();};
 const s=await p._engine.prepareSelection([id]);await p._engine.purge(consent(s));
 assert.equal(f.calls.delete.length,2);assert.ok(f.calls.delete.every(u=>u.startsWith(f.dir(0))));p.onDestroy();
});

test('actual page file lane refuses a get reply claiming a foreign directory',async()=>{
 const f=fixture();f.file.get=()=>{throw Error('Unexpected early get')};
 const p=page('Manage',f),ids=await p._engine.scan(),id=ids.find(x=>x.id.endsWith('_j_1')).id;
 f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');
 f.file.list=o=>{o.success({fileList:[{uri:f.dir(1)}]});if(o.complete)o.complete();};
 f.file.get=o=>{o.success({type:'dir',uri:f.dir(1),subFiles:[{uri:f.dir(0)+f.prefix(0)+'head.json'}]});if(o.complete)o.complete();};
 await assert.rejects(()=>p._engine.prepareSelection([id]),/目录|位置|路径/);assert.equal(f.calls.delete.length,0);p.onDestroy();
});

test('cancel invalidates approval and a late delete callback cannot continue batch',async()=>{
 const f=fixture(),a=api(f),ids=(await a.scan()).map(x=>x.id),s=await a.prepareSelection(ids);let pending;
 f.file.delete=o=>{f.calls.delete.push(o.uri);pending=o;};const work=a.purge(consent(s));for(let i=0;i<20&&!pending;i++)await settle();assert.ok(pending);
 a.cancel();pending.success({});await assert.rejects(()=>work,/停止|改变|取消/);assert.equal(f.calls.delete.length,1);assert.equal(a.state().removed_ids.length,0);assert.equal(a.state().uncertain,true);
});

test('head is removed last and unrelated files remain byte-identical',async()=>{
 const f=fixture(),a=api(f),id=(await a.scan()).find(x=>x.id.endsWith('_j_1')).id,s=await a.prepareSelection([id]);
 const other=new Map([...f.files].filter(([u])=>!u.startsWith(f.dir(0))));await a.purge(consent(s));assert.ok(f.calls.delete.at(-1).endsWith('_head.json'));
 for(const [u,v] of other)assert.equal(f.files.get(u),v);
});

test('final click is serialized and explicit confirmation remains required',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();p.toggleAll();await p.primary();assert.equal(p.stage,'confirm');assert.equal(f.calls.delete.length,0);
 await Promise.all([p.primary(),p.primary()]);assert.equal(f.calls.delete.length,6);assert.equal(p.totalCount,0);assert.match(p.message,/系统.*确认/);assert.doesNotMatch(p.message,/已核实/);p.onDestroy();
});

test('index I/O failure is reported as failure, never an empty collection',async()=>{
 const f=fixture(),read=f.file.readText;f.file.readText=o=>o.uri.endsWith('s5catalog_v2.json')?o.fail('unconfirmed native request',-2):read(o);
 const a=api(f);await assert.rejects(()=>a.scan(),/索引读取未确认/);assert.equal(a.state().phase,'error');assert.equal(f.calls.delete.length,0);
});

test('metadata changed during an earlier deletion stops the next record',async()=>{
 const f=fixture(),a=api(f),ids=(await a.scan()).map(x=>x.id),s=await a.prepareSelection(ids),del=f.file.delete;
 f.file.delete=o=>{if(o.uri===f.dir(0)+f.prefix(0)+'head.json'){const uri=f.dir(1)+f.prefix(1)+'head.json',h=JSON.parse(f.files.get(uri));h.app_version='changed';f.files.set(uri,JSON.stringify(h));}del(o);};
 await assert.rejects(()=>a.purge(consent(s)),/改变/);assert.equal(f.calls.delete.length,3);assert.equal(a.state().removed_ids.length,1);
});

test('legacy flat layout still deletes only the exact selected prefix without root enumeration',async()=>{
 const f=fixture(),t=f.targets[0],root='internal://files/',prefix=f.prefix(0),head=JSON.parse(f.files.get(f.dir(0)+prefix+'head.json'));
 delete head.storage_strategy;delete head.storage_root_uri;
 for(const [u,v] of [...f.files])if(u.startsWith(f.dir(0))){f.files.set(root+u.slice(f.dir(0).length),u.endsWith('head.json')?JSON.stringify(head):v);f.files.delete(u);}
 f.files.set(root+'s5catalog_v2.json',JSON.stringify({schema:2,hints:[[t.native_sid,t.sid,'f']]}));
 const a=require('../src/common/records-fast-delete.js').create({file:f.file,recoveryDirectories:[]}),id=(await a.scan())[0].id,s=await a.prepareSelection([id]);
 await a.purge(consent(s));assert.equal(f.calls.list.length,0);assert.equal(f.calls.delete.length,3);
 assert.ok(f.calls.delete.every(u=>u.startsWith(root+prefix)));assert.equal(f.files.get(root+'unrelated.json'),'keep');
});

test('native delete timeout stops the lane and never starts a second request',async()=>{
 const f=fixture(),timers=[];let pending;
 const a=require('../src/common/records-fast-delete.js').create({file:f.file,recoveryDirectories:f.targets.map((t,i)=>f.dir(i)),setTimeout:fn=>{timers.push(fn);return fn;},clearTimeout:()=>{}});
 const ids=(await a.scan()).map(x=>x.id),s=await a.prepareSelection(ids);
 f.file.delete=o=>{f.calls.delete.push(o.uri);pending=o;};const work=a.purge(consent(s));
 for(let i=0;i<20&&!pending;i++)await settle();assert.ok(pending);timers.at(-1)();
 await assert.rejects(()=>work,/超时/);assert.equal(f.calls.delete.length,1);assert.equal(a.state().uncertain,true);
 await assert.rejects(()=>a.scan(),/未确认/);assert.equal(f.calls.delete.length,1);
});
