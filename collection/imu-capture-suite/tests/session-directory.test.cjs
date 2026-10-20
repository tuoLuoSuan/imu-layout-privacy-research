const test=require('node:test'),assert=require('node:assert/strict');
const {create}=require('../watch/src/common/joint.js');
const pause=()=>new Promise(r=>setImmediate(r));
function setup(mode){
 let t=1792486980000,subscribed=0,blocked=null,id=0;const calls=[],timers=new Map(),sent=[];
 const file={
  mkdir(o){calls.push({name:'mkdir',uri:o.uri});if(mode==='mkdir-timeout'){blocked=o;return;}if(mode==='mkdir-error'){o.fail('synthetic permission denied',300);return;}o.success({});},
  list(o){calls.push({name:'list',uri:o.uri});if(o.uri==='internal://files/')return;if(mode==='list-timeout'){blocked=o;return;}o.success({fileList:mode==='collision'?[{uri:o.uri+'old-head.json',length:12}]:[]});},
  writeText(o){calls.push({name:'write',uri:o.uri});o.success({});}
 };
 const sensor={DATA_TYPES:{ACCELEROMETER:2},subscribe(){subscribed++;return 7;},unsubscribe(){}};
 const engine=create({file,sensor,now:()=>t,random:()=>.5,send:p=>sent.push(p),setTimeout:(fn,ms)=>{timers.set(++id,{fn,ms});return id;},clearTimeout:n=>timers.delete(n)});
 engine.start();const hello=sent[0];engine.receive({p:'J_HELLO_ACK1',sid:hello.sid,native_sid:'native-a',duration_ms:20000},t);
 return {engine,calls,sent,get subscribed(){return subscribed;},get blocked(){return blocked;},fire(){t+=8000;const timer=[...timers.values()].at(-1);assert.equal(timer.ms,8000);timer.fn();}};
}
test('an unresponsive historical root is never listed during a new session',async()=>{const f=setup();await pause();assert.equal(f.engine.state().phase,'recording');assert.equal(f.subscribed,1);assert.equal(f.calls.some(x=>x.name==='list'&&x.uri==='internal://files/'),false);const dir=f.calls.find(x=>x.name==='mkdir').uri;assert.ok(dir.includes('native-a'));assert.ok(dir.endsWith('/'));assert.equal(f.calls.find(x=>x.name==='list').uri,dir);assert.ok(f.calls.filter(x=>x.name==='write').every(x=>x.uri.startsWith(dir)));});
test('an existing nonempty session directory stops before any write',async()=>{const f=setup('collision');await pause();assert.equal(f.engine.state().phase,'failed');assert.equal(f.subscribed,0);assert.equal(f.calls.some(x=>x.name==='write'),false);});
test('mkdir errors stop without listing or starting the sensor',async()=>{const f=setup('mkdir-error');await pause();assert.equal(f.engine.state().phase,'failed');assert.equal(f.subscribed,0);assert.equal(f.calls.some(x=>x.name==='list'||x.name==='write'),false);});
test('a late mkdir success after timeout cannot list, write or subscribe',async()=>{const f=setup('mkdir-timeout');await pause();assert.ok(f.blocked);f.fire();await pause();assert.equal(f.engine.state().phase,'failed');f.blocked.success({});await pause();assert.equal(f.calls.some(x=>x.name==='list'||x.name==='write'),false);assert.equal(f.subscribed,0);});
test('session list timeout never falls back to the historical root',async()=>{const f=setup('list-timeout');await pause();assert.ok(f.blocked);f.fire();await pause();assert.equal(f.engine.state().phase,'failed');assert.equal(f.engine.state().stage,'list');assert.equal(f.calls.filter(x=>x.name==='list').length,1);assert.notEqual(f.calls.find(x=>x.name==='list').uri,'internal://files/');assert.equal(f.subscribed,0);});
