const test=require('node:test'),assert=require('node:assert/strict');
const transfer=require('../variants/research-transfer/src/common/transfer.js');

function rig(){let time=0;const sent=[],states=[];
 const sender=transfer.createSender({send:(text,fail)=>sent.push({text:JSON.parse(text),fail}),now:()=>time,onStatus:s=>states.push(s)});
 return {sender,sent,states,tick(ms){time+=ms;sender.tick();},ack(overrides){const m=sent.at(-1).text;sender.receive(JSON.stringify(Object.assign({p:'S5ACK1',t:m.t,s:m.s,i:m.i,o:Math.min(m.o+m.d.length,m.l),c:m.c,state:m.o+m.d.length===m.l?'part_complete':'stored'},overrides||{})));}};
}
test('one packet in flight and only matching receiver acknowledgement advances offset',async()=>{
 const r=rig();await r.sender.start({session:'1000_abcdef',format:'v2',parts:2,readPart:i=>Promise.resolve('x'.repeat(i?2000:1500))});
 assert.equal(r.sent.length,1);r.ack({t:'0000000000000000'});assert.equal(r.sent.length,1);
 r.ack();await new Promise(setImmediate);assert.equal(r.sent.length,2);assert.equal(r.sent[1].text.o,1024);
 r.ack();await new Promise(setImmediate);assert.equal(r.sent[2].text.i,1);r.ack();r.ack();await new Promise(setImmediate);
 assert.equal(r.sender.state().status,'complete');
});
test('lost acknowledgement is resent identically and retry budget is bounded',async()=>{
 const r=rig();await r.sender.start({session:'1000_abcdef',format:'v2',parts:1,readPart:()=>Promise.resolve('abc')});
 for(let i=0;i<4;i++)r.tick(2100);
 assert.equal(r.sent.length,4);assert.deepEqual(r.sent[0].text,r.sent[3].text);assert.equal(r.sender.state().status,'failed');
});
test('receiver may report already persisted suffix for deterministic restart, but never beyond file length',async()=>{
 const r=rig(),source={session:'1000_abcdef',format:'v2',parts:1,readPart:()=>Promise.resolve('x'.repeat(3000))};
 await r.sender.start(source);const token=r.sent[0].text.t;r.ack({o:3001,state:'part_complete'});assert.equal(r.sender.state().status,'sending');
 r.ack({o:3000,state:'part_complete'});assert.equal(r.sender.state().status,'complete');
 await r.sender.start(source);assert.equal(r.sent.at(-1).text.t,token);
});
test('cancel and disconnect preserve files and ignore late acknowledgements',async()=>{
 const r=rig();await r.sender.start({session:'1000_abcdef',format:'v2',parts:1,readPart:()=>Promise.resolve('abc')});r.sender.cancel();r.ack();assert.equal(r.sender.state().status,'cancelled');
});
