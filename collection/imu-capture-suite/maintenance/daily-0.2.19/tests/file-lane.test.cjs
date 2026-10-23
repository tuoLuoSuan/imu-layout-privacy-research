const test=require('node:test'),assert=require('node:assert/strict');
test('native callback delivery is deferred and opaque native metadata is discarded',async()=>{
 const native={list(o){assert.equal(typeof o.complete,'function');o.success({fileList:[{uri:'internal://files/a/',secret:'x'.repeat(10000),subFiles:[{name:'b.json',metadata:{large:true}}]}],extra:'ignored'});o.complete();}};
 const lane=require('../src/common/file-lane.js').create(native);let returned=false;const r=await new Promise(resolve=>{lane.file.list({uri:'internal://files/',success:v=>{assert.equal(returned,true);resolve(v);},fail:()=>assert.fail()});returned=true;});assert.deepEqual(r.fileList,[{uri:'internal://files/a/'},{uri:'internal://files/a/b.json'}]);assert.equal(lane.state().max_native_inflight,1);
});
test('only one native request is active and late duplicate callbacks cannot deliver twice',async()=>{
 let held,calls=0,deliveries=0;const native={readText(o){calls++;if(calls===1)held=o;else{o.success({text:'second'});o.complete();}}},lane=require('../src/common/file-lane.js').create(native);
 const a=new Promise(resolve=>lane.file.readText({uri:'internal://files/one',success:v=>{deliveries++;resolve(v.text);}})),b=new Promise(resolve=>lane.file.readText({uri:'internal://files/two',success:v=>{deliveries++;resolve(v.text);}}));await new Promise(r=>setTimeout(r,5));assert.equal(calls,1);held.success({text:'first'});held.success({text:'late'});held.complete();assert.deepEqual(await Promise.all([a,b]),['first','second']);assert.equal(deliveries,2);assert.equal(lane.state().max_native_inflight,1);
});
test('an unconfirmed native request halts the lane instead of overlapping a later request',{timeout:500},async()=>{
 let calls=0;const native={readText(){calls++;}},lane=require('../src/common/file-lane.js').create(native,{timeoutMs:10});const read=uri=>new Promise((resolve,reject)=>lane.file.readText({uri,success:resolve,fail:m=>reject(Error(m))}));const outcomes=await Promise.allSettled([read('internal://files/a'),read('internal://files/b')]);assert.ok(outcomes.every(r=>r.status==='rejected'));assert.equal(calls,1);assert.equal(lane.state().halted,true);await assert.rejects(()=>read('internal://files/c'));assert.equal(calls,1);
});
