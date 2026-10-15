// Offline E2E: actual JS sender -> actual native Rust receiver -> independent Python checker.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn,spawnSync}=require('node:child_process');
const repo=path.resolve(__dirname,'../../..'),core=require(path.join(repo,'collection/watch-s5-probe/variants/research-recorder/src/common/research.js'));
const transfer=require(path.join(repo,'collection/watch-s5-probe/variants/research-transfer/src/common/transfer.js'));
const binary=process.argv[2];if(!binary||!fs.existsSync(binary))throw Error('Pass the native receiver_sim binary');
const settle=()=>new Promise(r=>setImmediate(r));
async function main(){
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'s5-radio-synthetic-'));let child=null;
 try{
  const files=new Map(),api={writeText:o=>queueMicrotask(()=>{files.set(o.uri,o.text);o.success();}),list:o=>queueMicrotask(()=>o.success({fileList:[...files.keys()].map(uri=>({uri}))})),readText:o=>queueMicrotask(()=>o.success({text:files.get(o.uri)}))};
  let time=1000000;const store=core.createStore(api,{now:()=>time}),session=await store.start({durationSeconds:300});
  for(let i=0;i<15000;i++){time=1000000+i*20;session.push({x:i/10000,y:-2,z:3},i%2?'hidden':'visible');if(i%50===0)await settle();}
  session.stop('manual');await settle();await settle();const inv=await store.inventory(session.state().id);
  const bodies=[core.ascii({kind:'manifest',schema_version:2,session_id:inv.id,files:inv.files})];for(const name of inv.files)bodies.push(await store.readPart(inv.id,name));
  const receiving=path.join(temp,'receiver');fs.mkdirSync(receiving);let packets=0,token=null,buffer='',failed=null;
  child=spawn(binary,[receiving],{stdio:['pipe','pipe','pipe']});let stderr='';child.stderr.on('data',d=>stderr+=d);
  let finish;const completed=new Promise(r=>finish=r);
  const sender=transfer.createSender({send:(text,fail)=>{packets++;token=JSON.parse(text).t;child.stdin.write(text+'\n',e=>{if(e)fail(e.message);});},onStatus:s=>{if(s.status==='complete')finish();if(s.status==='failed'){failed=s.error;finish();}}});
  child.stdout.on('data',data=>{buffer+=data;let at;while((at=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,at);buffer=buffer.slice(at+1);sender.receive(line);}});
  const started=Date.now();await sender.start({session:inv.id,format:'v2',parts:bodies.length,readPart:i=>Promise.resolve(bodies[i])});
  const timer=setInterval(()=>sender.tick(),100);try{await completed;}finally{clearInterval(timer);child.stdin.end();}
  assert.equal(failed,null,failed||stderr);assert.equal(sender.state().status,'complete');
  const wire=path.join(temp,'export.txt');let result=spawnSync(binary,[receiving,'--export',token,wire],{encoding:'utf8'});assert.equal(result.status,0,result.stderr);
  const output=path.join(temp,'decoded');result=spawnSync(process.env.PYTHON||'python',[path.join(repo,'collection/watch-s5-probe/tools/decode_research_export.py'),wire,'--output',output],{encoding:'utf8',maxBuffer:2*1024*1024});assert.equal(result.status,0,result.stderr);
  const report=JSON.parse(result.stdout);assert.equal(report.samples,15000);assert.equal(report.session_status,'sealed');assert.equal(report.callback_hz,50);
  for(const name of inv.files)assert.equal(fs.readFileSync(path.join(output,'raw',name),'utf8'),await store.readPart(inv.id,name));
  console.log(JSON.stringify({scope:'offline synthetic, NOT Bluetooth or device validation',samples:report.samples,parts:bodies.length,packets,raw_files_byte_exact:inv.files.length,elapsed_ms:Date.now()-started,callback_hz_synthetic:report.callback_hz}));
 }finally{
  if(child)child.kill();await new Promise(r=>setTimeout(r,80));const resolved=fs.realpathSync(temp);assert.equal(path.dirname(resolved),fs.realpathSync(os.tmpdir()));assert.match(path.basename(resolved),/^s5-radio-synthetic-[A-Za-z0-9]+$/);fs.rmSync(resolved,{recursive:true,force:true});
 }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
