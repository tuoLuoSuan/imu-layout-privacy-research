const test=require('node:test'),assert=require('node:assert/strict');
const {create}=require('../watch/src/common/joint.js');
const pause=()=>new Promise(r=>setImmediate(r));
function fixture(target){
 let time=1792300000000,sub=null,blocked=null,id=0;const timers=new Map(),sent=[],writes=[];
 const file={mkdir(o){o.success({});},list(o){if(target==='list'){blocked=o;return;}o.success({fileList:[]});},writeText(o){writes.push(o.uri);const stage=o.uri.endsWith('_head.json')?'head':o.uri.endsWith('_tail.json')?'tail':'block';if(stage===target){blocked=o;return;}o.success({});}};
 const sensor={DATA_TYPES:{ACCELEROMETER:2},subscribe(o){sub=o;return 7;},unsubscribe(){}};
 const engine=create({file,sensor,now:()=>time,random:()=>.2,send:p=>sent.push(p),setTimeout:(f,ms)=>{timers.set(++id,{f,ms});return id;},clearTimeout:i=>timers.delete(i)});
 function receive(p){engine.receive(p,time);}
 function clock(){const p=sent.filter(p=>p.p==='J_CLK_REQ1').at(-1);if(p){receive({p:'J_CLK_REP1',sid:p.sid,native_sid:p.native_sid,seq:p.seq,w1_ms:p.w1_ms,p2_us:time*1000,p3_us:time*1000});receive({p:'J_CLK_ACK1',sid:p.sid,native_sid:p.native_sid,seq:p.seq,saved:true});}}
 return {engine,sent,writes,receive,clock,get blocked(){return blocked;},get sub(){return sub;},advance(n){time+=n;},sample(){time+=60;sub.callback({ACCELEROMETER:{x:1,y:2,z:3}});},timeout(){const t=[...timers.values()].at(-1);assert.equal(t.ms,8000);time+=8000;t.f();},start(){engine.start();const h=sent[0];receive({p:'J_HELLO_ACK1',sid:h.sid,native_sid:'native-session',duration_ms:20000});}};
}
for(const stage of ['list','head','block','tail'])test('real engine '+stage+' timeout remains failed and confirms only a saved failure ACK',async()=>{
 const f=fixture(stage);f.start();await pause();
 if(stage==='block'||stage==='tail'){f.clock();for(let i=0;i<16;i++)f.sample();if(stage==='block'){f.advance(1001);f.engine.tick();}else f.engine.stop('user');await pause();}
 assert.ok(f.blocked);f.timeout();await pause();assert.equal(f.engine.state().phase,'failed');assert.equal(f.engine.state().stage,stage);assert.equal(f.sent.filter(p=>p.p==='J_FAIL1').length,1);assert.equal(f.sent.some(p=>p.p==='J_END1'),false);
 assert.equal(f.engine.state().failure_notified,false,'sending once does not prove plugin persistence');
 f.blocked.success(stage==='list'?{fileList:[]}:{});await pause();assert.equal(f.engine.state().phase,'failed');
 const p=f.sent.find(p=>p.p==='J_FAIL1');f.receive({p:'J_FAIL_ACK1',sid:'foreign',native_sid:p.native_sid,saved:true});assert.equal(f.engine.state().failure_notified,false);f.receive({p:'J_FAIL_ACK1',sid:p.sid,native_sid:p.native_sid,saved:true});assert.equal(f.engine.state().failure_notified,true);assert.equal(f.engine.state().phase,'failed');
});
test('failure text respects the plugin UTF-8 byte limit',async()=>{const f=fixture('head');f.start();await pause();f.blocked.fail('错'.repeat(200),1);await pause();const p=f.sent.find(p=>p.p==='J_FAIL1');assert.ok(Buffer.byteLength(p.error,'utf8')<=240);assert.ok(JSON.stringify(p).length<=1280);});
test('sensor failure does not resume queued block writes after an in-flight success',async()=>{const f=fixture('block');f.start();await pause();f.clock();for(let i=0;i<16;i++)f.sample();f.advance(1001);f.engine.tick();await pause();const before=f.writes.length;f.sub.fail('synthetic sensor failure',1);f.blocked.success({});await pause();assert.equal(f.engine.state().phase,'failed');assert.equal(f.writes.length,before,'only the already in-flight write may finish');});
test('actual page and real engine isolate late file and connection callbacks after an explicit new session',async()=>{
 const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
 let oldList,block=true,id=0;const timers=new Map(),connections=[];const schedule=(fn,ms)=>{timers.set(++id,{fn,ms});return id;};
 const file={mkdir(o){o.success({});},list(o){if(block){oldList=o;return;}o.success({fileList:[]});},writeText(o){o.success({});}};
 const sensor={DATA_TYPES:{ACCELEROMETER:2},subscribe(){return 7;},unsubscribe(){}};
 const moduleBox={exports:{}};const source=fs.readFileSync(path.join(__dirname,'../watch/src/Probe/index.ux'),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/mg,'').replace('export default','module.exports=');
 const realTimeout=global.setTimeout,realClear=global.clearTimeout;global.setTimeout=schedule;global.clearTimeout=x=>timers.delete(x);
 try{
  vm.runInNewContext(source,{module:moduleBox,require:()=>({create}),file,sensor,Date,brightness:{setKeepScreenOn(){}},setTimeout:schedule,clearTimeout:x=>timers.delete(x),setInterval:()=>1,clearInterval(){},interconnect:{instance(){const c={packets:[],getReadyState(o){c.ready=o;},send(o){c.packets.push(o.data);}};connections.push(c);return c;}}});
  const page=moduleBox.exports;Object.assign(page,page.data);page.onInit();page.start();connections[0].ready.success({status:1});let h=connections[0].packets[0];connections[0].onmessage({p:'J_HELLO_ACK1',sid:h.sid,native_sid:'first-native',duration_ms:60000});await pause();[...timers.values()].at(-1).fn();await pause();assert.equal(page._engine.state().phase,'failed');
  block=false;page.start();connections[1].ready.success({status:1});h=connections[1].packets[0];connections[1].onmessage({p:'J_HELLO_ACK1',sid:h.sid,native_sid:'second-native',duration_ms:60000});await pause();assert.equal(page._engine.state().phase,'recording');
  oldList.success({fileList:[]});connections[0].onmessage({p:'J_ERR1',sid:h.sid,error:'late old connection'});await pause();assert.equal(page._started,true);assert.equal(page._engine.state().phase,'recording');assert.equal(page.message,'正在采集');
  page.onDestroy();
 }finally{global.setTimeout=realTimeout;global.clearTimeout=realClear;}
});

for(const deliver of [true,false])test('actual destroyed page and real uploading engine '+(deliver?'finish saved ACK chain':'report bounded missing ACK failure'),async()=>{
 const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');let time=1792300000000,sub,id=0;
 const intervals=new Map(),timeouts=new Map(),packets=[],writes=[];
 const schedule=(fn,ms)=>{const key=++id;timeouts.set(key,{fn,ms});return key;};
 const file={mkdir(o){o.success({});},list(o){o.success({fileList:[]});},writeText(o){writes.push(o.uri);o.success({});}};
 const sensor={DATA_TYPES:{ACCELEROMETER:2},subscribe(o){sub=o;return 7;},unsubscribe(){}};
 const connection={getReadyState(o){connection.ready=o;},send(o){packets.push(o.data);}};
 const moduleBox={exports:{}};const source=fs.readFileSync(path.join(__dirname,'../watch/src/Probe/index.ux'),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/mg,'').replace('export default','module.exports=');
 vm.runInNewContext(source,{module:moduleBox,require:()=>({create:o=>create(Object.assign({},o,{now:()=>time,setTimeout:schedule,clearTimeout:key=>timeouts.delete(key)}))}),file,sensor,Date:{now:()=>time},brightness:{setKeepScreenOn(){}},setTimeout:schedule,clearTimeout:key=>timeouts.delete(key),setInterval:fn=>{const key=++id;intervals.set(key,fn);return key;},clearInterval:key=>intervals.delete(key),interconnect:{instance:()=>connection}});
 const page=moduleBox.exports;Object.assign(page,page.data);page.onInit();page.durationMs=20000;page.start();connection.ready.success({status:1});
 const hello=packets.at(-1);connection.onmessage({p:'J_HELLO_ACK1',sid:hello.sid,native_sid:'native-page-destroy',duration_ms:20000});await pause();assert.equal(page._engine.state().phase,'recording');
 const clock=packets.at(-1);connection.onmessage({p:'J_CLK_REP1',sid:clock.sid,native_sid:clock.native_sid,seq:clock.seq,w1_ms:clock.w1_ms,p2_us:time*1000,p3_us:time*1000});connection.onmessage({p:'J_CLK_ACK1',sid:clock.sid,native_sid:clock.native_sid,seq:clock.seq,saved:true});
 for(let i=0;i<16;i++){time+=60;sub.callback({ACCELEROMETER:{x:1,y:2,z:3}});}page.stop();await pause();assert.equal(page._engine.state().phase,'uploading');
 const generation=page._generation;page.onDestroy();assert.equal(page._generation,generation);assert.equal(intervals.size,1);
 if(deliver){
  let steps=0;while(page._engine.state().phase==='uploading'&&steps++<10){const p=packets.at(-1);if(p.p==='J_DATA1')connection.onmessage({p:'J_DATA_ACK1',sid:p.sid,native_sid:p.native_sid,index:p.index,crc32:p.crc32,saved:true});else{assert.equal(p.p,'J_END1');connection.onmessage({p:'J_END_ACK1',sid:p.sid,native_sid:p.native_sid,count:p.count,saved:true});}}
  assert.equal(page._engine.state().phase,'complete');assert.equal(packets.some(p=>p.p==='J_FAIL1'),false);
 }else{
  time+=8001;[...intervals.values()][0]();assert.equal(page._engine.state().phase,'failed');const failures=packets.filter(p=>p.p==='J_FAIL1');assert.equal(failures.length,1);assert.equal(failures[0].stage,'transport');assert.equal(packets.some(p=>p.p==='J_END1'),false);connection.onmessage({p:'J_FAIL_ACK1',sid:failures[0].sid,native_sid:failures[0].native_sid,saved:true});assert.equal(page._engine.state().failure_notified,true);
 }
 assert.equal(page._engine.state().count,16);assert.equal(writes.filter(uri=>uri.endsWith('_tail.json')).length,1);assert.equal(intervals.size,0);
});
