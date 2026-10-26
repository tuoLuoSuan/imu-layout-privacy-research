const test=require('node:test'),assert=require('node:assert/strict');
const {create}=require('../src/common/joint.js');
const pause=()=>new Promise(r=>setImmediate(r));
async function fixture(support=true){
 let time=1792923000000,cb;const files=new Map(),sent=[];
 const e=create({now:()=>time,random:()=>.5,requestedDurationMs:60000,
 file:{mkdir:o=>o.success(),list:o=>o.success({fileList:[]}),writeText:o=>{files.set(o.uri,o.text);o.success();}},
 sensor:{DATA_TYPES:{ACCELEROMETER:2},subscribe:o=>{cb=o.callback;return 7;},unsubscribe:()=>{}},send:p=>sent.push(p)});
 e.start();const h=sent[0];e.receive({p:'J_HELLO_ACK1',sid:h.sid,native_sid:'native-session',duration_ms:60000,clock_drop_supported:support},time);
 for(let i=0;i<8;i++)await pause();
 const reply=(q,extra={})=>({p:'J_CLK_REP1',sid:q.sid,native_sid:q.native_sid,seq:q.seq,w1_ms:q.w1_ms,p2_us:q.w1_ms*1000+100,p3_us:q.w1_ms*1000+200,...extra});
 return {e,sent,files,reply,advance:n=>time+=n,receive:p=>e.receive(p,time),sample:()=>cb({ACCELEROMETER:{x:1,y:2,z:9.8}})};
}
test('matched reply beyond five seconds is discarded while sensing continues',async()=>{
 const f=await fixture(),q=f.sent.at(-1);f.advance(6000);f.receive(f.reply(q));
 assert.equal(f.e.state().phase,'recording');assert.equal(f.sent.at(-1).p,'J_CLK_DROP1');
 f.receive({p:'J_CLK_DROP_ACK1',sid:q.sid,native_sid:q.native_sid,seq:q.seq,saved:true});
 f.sample();assert.equal(f.e.state().count,1);assert.equal(f.e.state().clock_observations,0);assert.equal(f.e.state().discarded_clock_observations,1);
 f.e.stop('user');for(let i=0;i<8;i++)await pause();
 const end=JSON.parse([...f.files.entries()].find(([u])=>u.endsWith('_tail.json'))[1]);assert.equal(end.count,1);assert.equal(end.clock_observations,0);assert.equal(end.acquisition.clock_exchange_diagnostics.discarded,1);
});
test('stale reply cannot kill the next clock request',async()=>{
 const f=await fixture(),q=f.sent.at(-1);f.receive(f.reply(q));f.receive({p:'J_CLK_ACK1',sid:q.sid,native_sid:q.native_sid,seq:q.seq,saved:true});
 f.advance(2100);f.e.tick();const next=f.sent.at(-1);assert.equal(next.seq,1);f.receive(f.reply(q));
 assert.equal(f.e.state().phase,'recording');assert.equal(f.sent.at(-1),next);f.receive(f.reply(next));assert.equal(f.sent.at(-1).p,'J_CLK_OBS1');
});
test('reply timeout uses acknowledged discard rather than an invented observation',async()=>{
 const f=await fixture(),q=f.sent.at(-1);f.advance(8100);f.e.tick();assert.equal(f.e.state().phase,'recording');assert.equal(f.sent.at(-1).p,'J_CLK_DROP1');
 f.receive({p:'J_CLK_DROP_ACK1',sid:q.sid,native_sid:q.native_sid,seq:q.seq,saved:true});assert.equal(f.e.state().clock_observations,0);
});
