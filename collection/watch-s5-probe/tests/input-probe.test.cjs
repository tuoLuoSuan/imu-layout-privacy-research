const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const probe=require('../variants/input-probe/src/common/input-probe.js');
const settle=()=>new Promise(setImmediate);
function core(){
 const base=fs.realpathSync(os.tmpdir()),dir=fs.mkdtempSync(path.join(base,'imus5-input-test-'));
 try{require('../tools/build_input_probe_source.cjs').prepareStage(dir);return require(path.join(dir,'src/common/research.js'));}
 finally{assert.equal(path.dirname(fs.realpathSync(dir)),base);fs.rmSync(dir,{recursive:true,force:true});}
}
function rig(modify){
 let t=1000,options,calls=0;const files=new Map(),cleaned=[],states=[];
 const file={list(o){queueMicrotask(()=>o.success({fileList:[...files.keys()].map(uri=>({uri:uri.replace('files/','files//')}))}));},
 writeText(o){queueMicrotask(()=>{files.set(o.uri,o.text);o.success();});}};
 const sensor={DATA_TYPES:{ACCELEROMETER:2},subscribe(o){calls++;options=o;return 77;},unsubscribe(handle){cleaned.push(handle);}};
 if(modify)modify(sensor,file);
 const store=core().createStore(file,{now:()=>t});
 const run=probe.create({sensor,store,now:()=>t,monotonic:()=>t-900,pageState:()=> 'visible',onState:s=>states.push(s)});
 return {run,files,sensor,cleaned,states,time(v){t=v;},emit(v){options.callback(v);},get calls(){return calls;}};
}
function parts(r){return [...r.files.values()].map(JSON.parse);}
test('declaration inspection calls no methods, does not guess missing constants, and records getter errors',()=>{
 let called=0;const s={subscribe(){called++;},unsubscribe(){called++;},checkAvailable(){called++;}};
 assert.equal(probe.inspect(s).eligible,false);assert.equal(called,0);
 Object.defineProperty(s,'DATA_TYPES',{get(){throw Error('native getter failed exactly');}});
 const d=probe.inspect(s);assert.equal(d.eligible,false);assert.match(JSON.stringify(d),/native getter failed exactly/);assert.equal(called,0);
});
test('generic preserves decimal/raw nested timestamp and callback arrival; cleanup uses returned handle, never sensor type',async()=>{
 const r=rig();await r.run.start();r.time(1011);r.emit({ACCELEROMETER:{x:1.23456789,y:-9.81234,z:0.0001,timestamp:123456789}});
 r.time(1031);r.emit({ACCELEROMETER:{x:1.456789,y:-9.8,z:0.0002,timestamp:123456999}});
 r.time(3000);r.run.tick();await settle();await settle();
 const p=parts(r),head=p.find(x=>x.kind==='head'),tail=p.find(x=>x.kind==='tail'),rows=p.filter(x=>x.kind==='block').flatMap(x=>x.rows);
 assert.equal(r.calls,1);assert.deepEqual(r.cleaned,[77]);assert.equal(head.metadata.record_purpose,'input_probe');assert.equal(head.metadata.requested_interval,'high');
 assert.equal(head.metadata.acquisition_api,'@system.sensor.subscribe');assert.equal(head.metadata.hardware_timestamp,false);
 assert.equal(rows[0][1],1011);assert.equal(rows[0][2],1.23456789);assert.equal(rows.length,2);
 assert.equal(JSON.parse(tail.input_probe.callbacks[0].raw_json).ACCELEROMETER.timestamp,123456789);
 assert.equal(tail.input_probe.callbacks[0].performance_now_ms,111);assert.equal(tail.input_probe.result,'completed');
 assert.equal(tail.input_probe.hardware_time_semantics,'unverified');assert.equal(r.run.state().phase,'complete');
 await assert.rejects(()=>r.run.start(),/once/);assert.equal(r.calls,1);
});
test('missing generic method seals an exportable zero-sample declaration report without fallback',async()=>{
 const r=rig(s=>{delete s.subscribe;});await r.run.start();await settle();await settle();
 const p=parts(r),tail=p.find(x=>x.kind==='tail');assert.equal(tail.count,0);assert.equal(tail.input_probe.result,'unavailable');assert.equal(r.calls,0);assert.deepEqual(r.cleaned,[]);
});
test('synchronous native fail is preserved, late returned handle cleaned once, no retry',async()=>{
 const r=rig(s=>{s.subscribe=o=>{o.fail('sensor not implemented',203);return 88;};});await r.run.start();await settle();await settle();
 const tail=parts(r).find(x=>x.kind==='tail');assert.equal(tail.input_probe.result,'native_fail');assert.equal(tail.input_probe.error.message,'sensor not implemented');
 assert.equal(tail.input_probe.error.code,203);assert.deepEqual(r.cleaned,[88]);r.run.tick();assert.deepEqual(r.cleaned,[88]);
});
test('throw and silence end once and retain distinct reasons',async()=>{
 const r=rig(s=>{s.subscribe=()=>{throw Error('unsupported native method');};});await r.run.start();await settle();await settle();
 assert.equal(parts(r).find(x=>x.kind==='tail').input_probe.error.message,'unsupported native method');
 const q=rig();await q.run.start();q.time(3000);q.run.tick();await settle();await settle();assert.equal(parts(q).find(x=>x.kind==='tail').input_probe.result,'no_callbacks');
});
test('unknown callback shape is preserved without inventing XYZ rows and stops this candidate',async()=>{
 const r=rig();await r.run.start();r.emit({data:[{x:0.25,y:1,z:2}],stamp:123});await settle();await settle();
 const tail=parts(r).find(x=>x.kind==='tail');assert.equal(tail.count,0);assert.equal(tail.input_probe.result,'unknown_shape');assert.equal(JSON.parse(tail.input_probe.callbacks[0].raw_json).stamp,123);assert.deepEqual(r.cleaned,[77]);
});
test('hide stops probe immediately, ignores late callbacks, does not pretend it tested screen off',async()=>{
 const r=rig();await r.run.start();r.emit({x:0.25,y:1,z:2});r.run.stop('page_hide');r.emit({x:8,y:9,z:10});await settle();await settle();
 const tail=parts(r).find(x=>x.kind==='tail');assert.equal(tail.count,1);assert.equal(tail.input_probe.result,'page_hide');assert.deepEqual(r.cleaned,[77]);
});
test('callback cap and payload cap are explicit stops rather than silent truncation',async()=>{
 const r=rig();await r.run.start();for(let i=0;i<130;i++){r.time(1001+i);r.emit({x:i+0.125,y:1,z:2});}await settle();await settle();
 let tail=parts(r).find(x=>x.kind==='tail');assert.equal(tail.input_probe.callbacks.length,128);assert.equal(tail.input_probe.result,'callback_limit');assert.equal(tail.count,128);
 const q=rig();await q.run.start();q.emit({x:1,y:2,z:3,extra:'a'.repeat(3000)});await settle();await settle();tail=parts(q).find(x=>x.kind==='tail');
 assert.equal(tail.input_probe.result,'raw_budget_exceeded');assert.equal(tail.input_probe.callbacks.length,0);assert.equal(tail.count,0);
});
test('invalid numeric values are not silently changed to JSON null; invalid return handle is not guessed',async()=>{
 const r=rig();await r.run.start();r.emit({x:NaN,y:1,z:2});await settle();await settle();assert.equal(parts(r).find(x=>x.kind==='tail').input_probe.result,'raw_not_json');
 const q=rig(s=>{s.subscribe=()=>undefined;});await q.run.start();await settle();await settle();
 const report=parts(q).find(x=>x.kind==='tail').input_probe;assert.equal(report.result,'invalid_handle');assert.equal(report.cleanup.status,'handle_unavailable');assert.deepEqual(q.cleaned,[]);
});
test('ordinary core rejects externally supplied arrival and probe metadata unless explicitly probe',async()=>{
 let t=1000;const files=[],file={list:o=>o.success({fileList:[]}),writeText:o=>{files.push(JSON.parse(o.text));o.success();}};
 const s=await core().createStore(file,{now:()=>t}).start({durationSeconds:2});t=1010;s.push({x:1,y:2,z:3},'visible',1001);s.stop('manual');
 assert.equal(files.find(p=>p.kind==='block').rows[0][1],1010);assert.throws(()=>s.setInputProbe({}),/probe/);
});
test('asynchronous block write failure immediately unsubscribes and retains a visible storage failure',async()=>{
 const r=rig((s,file)=>{const write=file.writeText;file.writeText=o=>o.uri.includes('_b')?queueMicrotask(()=>o.fail('disk full',301)):write(o);});
 await r.run.start();for(let i=0;i<128;i++)r.emit({x:i+0.5,y:1,z:2});await settle();await settle();
 assert.deepEqual(r.cleaned,[77]);assert.equal(r.run.state().phase,'storage_failed');
});
