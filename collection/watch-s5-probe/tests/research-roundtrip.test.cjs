const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawnSync}=require('node:child_process');
const core=require('../variants/research-recorder/src/common/research.js');
const settle=()=>new Promise(r=>setImmediate(r));
test('actual JS five-minute segmented QR export decodes independently in Python with byte-exact raw files',async()=>{
  const files=new Map();const api={list:o=>queueMicrotask(()=>o.success({fileList:[...files.keys()].map(uri=>({uri}))})),
    writeText:o=>queueMicrotask(()=>{files.set(o.uri,o.text);o.success();}),readText:o=>queueMicrotask(()=>o.success({text:files.get(o.uri)}))};
  let t=1000000;const store=core.createStore(api,{now:()=>t}),s=await store.start({durationSeconds:300});
  for(let i=0;i<15000;i++){t=1000000+i*20;s.push({x:i/100000,y:-2,z:3},i%2?'hidden':'visible');if(i%50===0)await settle();}
  s.stop('manual');await settle();await settle();const inv=await store.inventory(s.state().id);
  const packets=core.frames(inv.id,0,core.ascii({kind:'manifest',schema_version:2,session_id:inv.id,files:inv.files}));
  for(let i=0;i<inv.files.length;i++)packets.push(...core.frames(inv.id,i+1,await store.readPart(inv.id,inv.files[i])));
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'s5-roundtrip-'));
  try{
    const input=path.join(temp,'packets.txt'),output=path.join(temp,'decoded');fs.writeFileSync(input,packets.reverse().join('\n'));
    const run=spawnSync(process.env.PYTHON||'python',[path.join(__dirname,'../tools/decode_research_export.py'),input,'--output',output],{encoding:'utf8'});
    assert.equal(run.status,0,run.stderr);const report=JSON.parse(run.stdout);assert.equal(report.samples,15000);assert.equal(report.callback_hz,50);assert.equal(report.session_status,'sealed');
    for(const name of inv.files)assert.equal(fs.readFileSync(path.join(output,'raw',name),'utf8'),await store.readPart(inv.id,name));
    const csv=fs.readFileSync(path.join(output,'accelerometer.csv'),'utf8');assert.equal(csv.trim().split('\n').length,15001);
    // QR volume is explicitly measured; this is a fallback, not a fast radio transfer.
    assert.ok(packets.length>1000);
  }finally{const resolved=fs.realpathSync(temp);assert.equal(path.dirname(resolved),fs.realpathSync(os.tmpdir()));assert.match(path.basename(resolved),/^s5-roundtrip-[A-Za-z0-9]+$/);fs.rmSync(resolved,{recursive:true});}
});
