const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const old=require('../variants/research-recorder/src/common/research.js'),ROOT='internal://files/';
function disk(){
 const files=new Map(),reads=[],deletes=[];let mixed=false;
 const api={
  list(o){queueMicrotask(()=>{
   const names=[...files.keys()];const entries=names.map(uri=>({uri:uri.replace(ROOT,ROOT+'/')}));
   if(mixed)names.forEach(uri=>{entries.push({uri},{uri:uri.slice(ROOT.length)});});
   entries.push({uri:'internal://cache//s5r_9_aaaaaa_head.json'},{uri:ROOT+'../s5r_9_aaaaaa_head.json'},{uri:ROOT+'%2e%2e%2fs5r_9_aaaaaa_head.json'},{uri:ROOT+'nested/s5r_9_aaaaaa_head.json'});
   o.success({fileList:entries});
  });},
  writeText(o){queueMicrotask(()=>{files.set(o.uri,o.text);o.success();});},
  readText(o){reads.push(o.uri);queueMicrotask(()=>files.has(o.uri)?o.success({text:files.get(o.uri)}):o.fail('missing',301));},
  delete(o){deletes.push(o.uri);queueMicrotask(()=>files.delete(o.uri)?o.success():o.fail('missing',301));}
 };
 return {api,files,reads,deletes,mix(){mixed=true;}};
}
function corrected(){
 const builder=path.join(__dirname,'../tools/build_directory_uri_fix_source.cjs');assert.ok(fs.existsSync(builder),'缺少URI兼容修正覆盖层');
 const parent=fs.realpathSync(os.tmpdir()),temp=fs.mkdtempSync(path.join(parent,'imus5-uri-test-'));
 try{require(builder).prepareStage(temp);return require(path.join(temp,'src/common/research.js'));}
 finally{assert.equal(path.dirname(fs.realpathSync(temp)),parent);fs.rmSync(temp,{recursive:true,force:true});}
}
const settle=()=>new Promise(r=>setImmediate(r));
async function record99(d){let t=1000;const s=await old.createStore(d.api,{now:()=>t}).start({durationSeconds:2});
 for(let i=0;i<99;i++){t=1000+i*20;s.push({x:i+0.125,y:-2,z:3});}t=3000;s.tick();await settle();await settle();assert.equal(s.state().persisted,99);return s.state().id;}

test('observed double root separator reproduces old empty list; corrected core lists and exports all 99 original rows unchanged',async()=>{
 const d=disk(),id=await record99(d);assert.equal((await old.createStore(d.api).list(false)).length,0);
 const before=[...d.files],fixed=corrected().createStore(d.api),items=await fixed.list(false);
 assert.equal(items.length,1);assert.equal(items[0].id,id);assert.equal(items[0].count,99);assert.equal(items[0].state,'sealed');
 const inv=await fixed.inventory(id);const raw=[];for(const n of inv.files)raw.push(JSON.parse(await fixed.readPart(id,n)));
 assert.equal(raw.filter(p=>p.kind==='block').flatMap(b=>b.rows).length,99);assert.equal(raw[0].metadata.app_version,'0.3.0');
 assert.deepEqual([...d.files],before);assert.deepEqual(d.deletes,[]);assert.ok(d.reads.every(uri=>d.files.has(uri)));
});

test('mixed URI aliases are deduplicated and wrong roots or unsafe paths cannot become file operations',async()=>{
 const d=disk();await record99(d);d.mix();const store=corrected().createStore(d.api);const items=await store.list(false);
 assert.equal(items.length,1);assert.ok(d.reads.every(uri=>d.files.has(uri)));
 const helper=require('../variants/directory-uri-fix/src/common/directory-entries.js');
 const evil=['../x',ROOT+'../x',ROOT+'/../x',ROOT+'//s5r_1_aaaaaa_head.json',ROOT+'x/y',ROOT+'x\\y',ROOT+'x%2fy','file:///x','/x','internal://cache/x'];
 assert.deepEqual(helper.normalize(evil.map(uri=>({uri}))),[]);
 assert.throws(()=>helper.normalize(undefined),/列表/);
});

test('capacity limit still counts sessions reported with doubled separators before allowing any new write',async()=>{
 const d=disk();for(let i=1;i<=40;i++)d.files.set(ROOT+'s5r_'+i+'_aaaaaa_head.json','retained');
 const before=[...d.files],store=corrected().createStore(d.api);await assert.rejects(()=>store.start({durationSeconds:2}),/40条/);
 assert.deepEqual([...d.files],before);
});

test('trash, restore and confirmed purge use canonical paths and preserve unrelated original records',async()=>{
 const d=disk(),id=await record99(d);d.files.set(ROOT+'unrelated.json','keep exactly');const store=corrected().createStore(d.api);
 await store.trash(id);assert.equal((await store.list(false)).length,0);assert.equal((await store.list(true))[0].id,id);
 await store.restore(id);assert.equal((await store.list(false)).length,1);await store.trash(id);await store.purge(id,id);
 assert.equal((await store.list(true)).length,0);assert.equal(d.files.get(ROOT+'unrelated.json'),'keep exactly');
 assert.ok(d.deletes.every(uri=>uri.startsWith(ROOT+'s5r_'+id+'_')));
});
