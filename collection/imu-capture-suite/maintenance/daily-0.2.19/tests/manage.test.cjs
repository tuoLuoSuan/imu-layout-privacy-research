const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {fixture,page,settle}=require('./fixtures.cjs');
const source=path.join(__dirname,'../src');
test('daily package exposes only capture and management, with no diagnostic routes',()=>{
 const m=JSON.parse(fs.readFileSync(path.join(source,'manifest.json'),'utf8'));
 assert.deepEqual(Object.keys(m.router.pages).sort(),['Manage','Menu','Probe']);
 const menu=fs.readFileSync(path.join(source,'Menu/index.ux'),'utf8');assert.doesNotMatch(menu,/上次阶段|只读查找|定位退出|测试|诊断/);assert.match(menu,/记录管理/);
});
test('management uses a fixed component tree without Date or trace writes',()=>{
 const s=fs.readFileSync(path.join(source,'Manage/index.ux'),'utf8');assert.doesNotMatch(s,/\sif=|\sfor=|new Date|exit-trace|view-cache|showDiagnostic/);
 assert.match(s,/onclick="toggle0"/);assert.match(s,/onclick="primary"/);assert.match(s,/releaseInventories/);
});
test('scan shows all summaries, stays awake, and starts with nothing selected',async()=>{
 const f=fixture(),before=new Map(f.files),p=page('Manage',f);await p.onShow();assert.equal(p.totalCount,2);assert.equal(p.stage,'list');assert.equal(p.selectedCount,0);assert.equal(p.primaryEnabled,false);assert.equal(f.calls.awake.at(-1),true);for(const [u,t] of before)assert.equal(f.files.get(u),t);assert.equal(f.calls.delete.length,0);p.onDestroy();
});
test('prepare and cancel never delete and preserve selection without rescanning',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();p.toggleAll();const lists=f.calls.list.length;await p.primary();assert.equal(p.stage,'confirm');assert.equal(p.selectedCount,2);assert.match(p.message,/不可撤销|无法撤销/);assert.equal(f.calls.delete.length,0);p.secondary();assert.equal(p.stage,'list');assert.equal(f.calls.list.length,lists+2);assert.equal(f.calls.delete.length,0);p.onDestroy();
});
test('one selected record is removed only after final consent, remaining bytes stay intact',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();p.toggle0();const selected=p._items[0].id,others=new Map([...f.files].filter(([u])=>!u.includes('/'+selected+'/')));await p.primary();const lists=f.calls.list.length;await p.primary();assert.equal(p.stage,'list');assert.equal(p.totalCount,1);assert.equal(p.selectedCount,0);assert.equal(f.calls.delete.length,3);assert.ok(f.calls.list.length>lists);for(const [u,t] of others)assert.equal(f.files.get(u),t);assert.ok(!p._items.some(e=>e.id===selected));p.onDestroy();
});
test('all selected records can be deleted with one final confirmation',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();p.toggleAll();await p.primary();assert.equal(f.calls.delete.length,0);await p.primary();assert.equal(p.totalCount,0);assert.equal(p.primaryEnabled,false);assert.equal(f.calls.delete.length,6);assert.equal(f.files.get('internal://files/unrelated.json'),'keep');p.onDestroy();
});
test('partial and unfinished sessions share the same selectable list and explicit loss warning',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'b0000.json');f.files.delete(f.dir(1)+f.prefix(1)+'tail.json');const p=page('Manage',f);await p.onShow();p.toggleAll();assert.equal(p.selectedCount,2);await p.primary();assert.match(p.message,/缺块1/);assert.match(p.message,/未完成1/);assert.match(p.message,/丢失/);await p.primary();assert.equal(p.totalCount,0);assert.equal(f.calls.delete.length,4);p.onDestroy();
});
test('hiding cancels confirmation and never restores deletion consent',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();p.toggleAll();await p.primary();p.onHide();await p.onShow();assert.equal(p.stage,'list');assert.equal(p._ready,null);assert.equal(f.calls.delete.length,0);assert.equal(f.calls.awake.at(-1),true);p.onDestroy();
});
test('selection and repeated buttons cannot race an in-progress prepare',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();p.toggle0();const read=f.file.readText;let pending;f.file.readText=o=>{if(!pending)pending=o;else read(o);};const op=p.primary();await settle();assert.equal(p.busy,true);const count=p.selectedCount;p.toggleAll();p.toggle1();p.primary();assert.equal(p.selectedCount,count);read(pending);await op;assert.equal(p.stage,'confirm');assert.equal(f.calls.delete.length,0);p.onDestroy();
});
test('record mutation after confirmation preparation blocks all deletion',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();p.toggleAll();await p.primary();const u=f.dir(0)+f.prefix(0)+'b0000.json';f.files.set(u,'[[0,100,8,2,3],[1,160,2,3,4]]');await p.primary();assert.equal(p.stage,'error');assert.equal(f.calls.delete.length,0);p.onDestroy();
});
test('first native delete error stops batch and repeat click does not retry',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();p.toggleAll();await p.primary();f.file.delete=o=>{f.calls.delete.push(o.uri);o.fail('no space or native failure',5);};await p.primary();assert.equal(p.stage,'error');assert.equal(f.calls.delete.length,1);assert.equal(p.selectedCount,0);assert.match(p.message,/未确认|未定/);p.onDestroy();
});
test('hiding during native deletion stops following requests, late ack cannot mark success',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();p.toggleAll();await p.primary();const del=f.file.delete;let pending;f.file.delete=o=>{if(!pending)pending=o;};const op=p.primary();for(let i=0;i<200&&!pending;i++)await settle();assert.ok(pending);p.onHide();del(pending);await op;assert.equal(p.stage,'error');assert.equal(f.calls.delete.length,1);assert.equal(p.totalCount,2);assert.equal(p._ready,null);p.onDestroy();
});
test('duplicate final clicks issue one serialized purge only',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();p.toggleAll();await p.primary();const a=p.primary(),b=p.primary();await Promise.all([a,b]);assert.equal(f.calls.delete.length,6);assert.equal(p.totalCount,0);p.onDestroy();
});
test('keep-awake rejection blocks scan and all deletion',async()=>{
 const f=fixture();f.brightness={setKeepScreenOn(o){o.keepScreenOn?o.fail('denied',5):o.success();}};const p=page('Manage',f);await p.onShow();assert.equal(p.stage,'error');assert.equal(f.calls.list.length,0);assert.equal(f.calls.delete.length,0);p.onDestroy();
});
test('hide then late read result never enters a ready or confirmation state',async()=>{
 const f=fixture(),read=f.file.readText;let pending;f.file.readText=o=>{if(!pending)pending=o;else read(o);};const p=page('Manage',f),op=p.onShow();await settle();p.onHide();read(pending);await op;assert.equal(p.stage,'error');assert.equal(p._ready,null);assert.equal(f.calls.delete.length,0);p.onDestroy();
});
