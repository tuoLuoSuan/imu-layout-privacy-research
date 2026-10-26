const test=require('node:test'),assert=require('node:assert/strict');
const {fixture}=require('./fixtures.cjs');
const directory=require('../src/common/file-directory.js');
const consent=s=>({token:s.token,preparedId:s.prepared_id,confirmBackup:true,confirmUnbackedLoss:true,confirmFailedRecord:true,confirmPermanent:true});
test('native child URI keeps the trailing-directory double separator from __read_dir_c',()=>{
 const dir='internal://files/s5joint_native_j_1/';
 assert.deepEqual(directory.compact(dir,[{uri:dir+'/s5joint_j_1_head.json'}]),[{uri:dir+'s5joint_j_1_head.json'}]);
 for(const bad of ['internal://cache/a//b','/data/a//b','internal://files/a//../b','internal://files/a/%2e%2e/b'])assert.equal(directory.relative(bad),null);
});
test('list 185 native double-separator leaves prepare without falling into empty get(false)',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');
 for(let i=1;i<184;i++)f.files.set(f.dir(0)+f.prefix(0)+'b'+String(i).padStart(4,'0')+'.json','[]');
 let gets=0;f.file.list=o=>o.success({fileList:[...f.files.keys()].filter(u=>u.startsWith(o.uri)).map(u=>({uri:o.uri+'/'+u.slice(o.uri.length)}))});
 f.file.get=o=>{gets++;o.success({type:'dir',uri:o.uri,subFiles:[]});};
 const lane=require('../src/common/file-lane.js').create(f.file),a=require('../src/common/records-fast-delete.js').create({file:lane.file,recoveryDirectories:f.targets.map((_,i)=>f.dir(i))});
 const id=(await a.scan()).find(x=>x.id.endsWith('_j_1')).id,s=await a.prepareSelection([id]);
 assert.equal(s.expected_files,185);assert.equal(gets,0);assert.equal(f.calls.delete.length,0);
 await a.purge(consent(s));assert.equal(f.calls.delete.length,185);assert.ok(f.files.has(f.dir(1)+f.prefix(1)+'head.json'));lane.close();
});
test('read-only fallback requests recursive get because upstream false omits subFiles',async()=>{
 const f=fixture();f.files.delete(f.dir(0)+f.prefix(0)+'tail.json');let gets=[];
 f.file.list=o=>o.success({fileList:[]});f.file.get=o=>{gets.push(o.recursive);o.success({type:'dir',uri:o.uri,subFiles:o.recursive?[...f.files.keys()].filter(u=>u.startsWith(o.uri)).map(uri=>({uri})):[]});};
 const a=require('../src/common/records-fast-delete.js').create({file:f.file,recoveryDirectories:f.targets.map((_,i)=>f.dir(i))}),id=(await a.scan()).find(x=>x.id.endsWith('_j_1')).id;
 const s=await a.prepareSelection([id]);assert.equal(s.expected_files,2);assert.deepEqual(gets,[true]);assert.equal(f.calls.delete.length,0);
});
