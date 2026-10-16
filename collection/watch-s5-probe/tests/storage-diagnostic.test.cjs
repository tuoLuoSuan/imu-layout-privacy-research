const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const target=path.join(__dirname,'../variants/storage-diagnostic/src/common/storage-diagnostic.js');
function moduleUnderTest(){assert.ok(fs.existsSync(target),'缺少只读文件诊断模块');return require(target);}

test('diagnostic reads only the fixed app directory and exposes unrecognised URI shape without modifying records',async()=>{
 const diag=moduleUnderTest(),calls=[];
 const file=new Proxy({
  list(o){calls.push(['list',o.uri]);queueMicrotask(()=>o.success({fileList:[{uri:'/native/app/files/s5r_1000_abcdef_head.json'},{uri:'/native/app/files/s5r_1000_abcdef_tail.json'}]}));},
  get(o){calls.push(['get',o.uri,o.recursive]);queueMicrotask(()=>o.success({type:'dir',subFiles:[{uri:'internal://files/s5r_1000_abcdef_head.json'}]}));}
 },{get(t,k){assert.ok(k in t,'不许访问文件写入／删除／正文接口: '+String(k));return t[k];}});
 const result=await diag.inspect(file);
 assert.deepEqual(calls,[['list','internal://files/'],['get','internal://files/',false]]);
 assert.equal(result.probes[0].status,'success');assert.equal(result.probes[0].shape.arrays[0].count,2);
 assert.equal(result.probes[0].shape.arrays[0].entries[0].uri,'/native/app/files/s5r_1000_abcdef_head.json');
 assert.ok(result.pages.some(p=>p.detail.includes('/native/app/files/')));
 for(const page of result.pages)for(const line of page.detail.split('\n')){
  assert.ok([...line].reduce((n,c)=>n+(c.charCodeAt(0)>127?2:1),0)<=30,'原始URI必须分行，不能被圆屏裁掉');
 }
});

test('missing fileList and bare-array results remain distinguishable from a real empty directory',async()=>{
 const diag=moduleUnderTest();
 const a=await diag.inspect({list:o=>o.success({unexpected:[]}),get:o=>o.success([])});
 const b=await diag.inspect({list:o=>o.success({fileList:[]}),get:o=>o.success({type:'dir',subFiles:[]})});
 assert.deepEqual(a.probes[0].shape.keys,['unexpected']);assert.equal(a.probes[1].shape.type,'array');
 assert.deepEqual(b.probes[0].shape.keys,['fileList']);assert.notDeepEqual(a.probes[0].shape,b.probes[0].shape);
 assert.ok(a.pages[0].detail.includes('unexpected'));assert.ok(b.pages[0].detail.includes('fileList'));
});

test('I/O failures, unsupported get and missing callbacks produce visible bounded results',async()=>{
 const diag=moduleUnderTest();let late;
 const result=await diag.inspect({list:o=>{late=o;},get:o=>o.fail('io error',300)},{timeoutMs:5});
 assert.equal(result.probes[0].status,'timeout');assert.equal(result.probes[1].status,'failed');
 assert.match(result.probes[1].error,/300/);
 const before=JSON.stringify(result);late.success({fileList:[{uri:'late'}]});assert.equal(JSON.stringify(result),before);
 const unsupported=await diag.inspect({list:o=>o.success({fileList:[]})});
 assert.equal(unsupported.probes[1].status,'failed');assert.ok(unsupported.pages.some(p=>p.detail.includes('get')));
});

test('large and malformed results are bounded and do not turn into fabricated session entries',async()=>{
 const diag=moduleUnderTest(),rows=Array.from({length:10000},()=>({uri:'x'.repeat(10000),name:'y'.repeat(10000)}));
 const result=await diag.inspect({list:o=>o.success({fileList:rows}),get:o=>o.success(null)});
 const arr=result.probes[0].shape.arrays[0];assert.equal(arr.count,10000);assert.equal(arr.entries.length,3);
 assert.ok(arr.entries[0].uri.length<=161);assert.equal(result.probes[1].shape.type,'null');
 assert.ok(JSON.stringify(result).length<12000);assert.ok(!('sessions' in result));
});
