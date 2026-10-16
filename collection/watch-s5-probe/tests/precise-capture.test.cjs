const test=require('node:test'),assert=require('node:assert/strict');
const capture=require('../variants/precise-recorder/src/common/sensor-capture.js');
function rig(change){
 let t=1000,options;const calls=[],values=[],errors=[],changes=[];
 const sensor={DATA_TYPES:{ACCELEROMETER:2},subscribe(o){options=o;calls.push(['generic',o.type,o.interval]);return 129;},unsubscribe(h){calls.push(['unsubscribe',h]);},
  subscribeAccelerometer(o){options=o;calls.push(['legacy',o.interval]);},unsubscribeAccelerometer(){calls.push(['unsubscribeAccelerometer']);}};
 if(change)change(sensor,calls);
 const driver=capture.create(sensor,{now:()=>t,onValue:(v,at)=>{values.push({value:v,at});return true;},onFail:e=>errors.push(e),onChange:s=>changes.push(s)});
 return {driver,sensor,calls,values,errors,changes,emit(v){options.callback(v);},time(v){t=v;}};
}
test('generic uses observed shape, real constant/handle, unrounded decimals, one arrival time and idempotent cleanup',()=>{
 const r=rig();r.driver.start({sensorPath:'generic',interval:'high'});r.time(1061);r.emit({ACCELEROMETER:{x:-0.197280004620552,y:3.43999004364014,z:9.24263000488281}});
 assert.equal(r.values[0].value.x,-0.197280004620552);assert.equal(r.values[0].at,1061);r.driver.stop();r.driver.stop();
 assert.deepEqual(r.calls,[['generic',2,'high'],['unsubscribe',129]]);const s=r.driver.state();assert.equal(s.valid_xyz_callbacks,1);assert.equal(s.fractional_xyz_scalars,3);assert.equal(s.cleanup.status,'unsubscribe_returned');
 assert.deepEqual(JSON.parse(s.first_callback_json),JSON.parse(s.last_callback_json));assert.equal(s.hardware_timestamp_verified,false);
});
test('generic missing constant and mixed interval fail without guessing or fallback',()=>{
 const r=rig(s=>{s.DATA_TYPES={};});r.driver.start({sensorPath:'generic',interval:'high'});assert.equal(r.calls.length,0);assert.match(r.errors[0].message,/ACCELEROMETER/);
 const q=rig();q.driver.start({sensorPath:'generic',interval:'game'});assert.equal(q.calls.length,0);assert.equal(q.errors.length,1);
});
test('native failure keeps original message/code and cleans late synchronous returned handle',()=>{
 const r=rig((s,calls)=>{s.subscribe=o=>{calls.push(['subscribe']);o.fail('permission denied exactly',203);return 701;};});
 r.driver.start({sensorPath:'generic',interval:'high'});assert.equal(r.errors[0].message,'permission denied exactly');assert.equal(r.errors[0].code,203);
 assert.deepEqual(r.calls,[['subscribe'],['unsubscribe',701]]);assert.equal(r.driver.state().cleanup.status,'unsubscribe_returned');
});
test('generic unknown/new fields retain raw evidence and stop, never discard potential timestamps silently',()=>{
 const r=rig();r.driver.start({sensorPath:'generic',interval:'mid'});r.emit({ACCELEROMETER:{x:1.1,y:2,z:3,timestamp:555}});
 assert.equal(r.values.length,0);assert.equal(r.errors.length,1);assert.equal(JSON.parse(r.driver.state().rejected_callback_json).ACCELEROMETER.timestamp,555);
 assert.deepEqual(r.calls.at(-1),['unsubscribe',129]);r.emit({ACCELEROMETER:{x:1.1,y:2,z:3}});assert.equal(r.values.length,0);
});
test('invalid return handle is not replaced with sensor type and native throw never falls back',()=>{
 const r=rig(s=>{s.subscribe=()=>undefined;});r.driver.start({sensorPath:'generic',interval:'high'});assert.equal(r.driver.state().cleanup.status,'handle_unavailable');assert.equal(r.calls.length,0);
 const q=rig(s=>{s.subscribe=()=>{throw Error('native thrown');};});q.driver.start({sensorPath:'generic',interval:'high'});assert.equal(q.errors[0].message,'native thrown');assert.equal(q.calls.length,0);
});
test('legacy explicitly uses dedicated subscribe/unsubscribe, independent from generic native method',()=>{
 const r=rig();r.driver.start({sensorPath:'legacy',interval:'game'});r.emit({x:2,y:3,z:9});r.driver.stop();
 assert.deepEqual(r.calls,[['legacy','game'],['unsubscribeAccelerometer']]);assert.equal(r.values.length,1);assert.equal(r.driver.state().api,'@system.sensor.subscribeAccelerometer');
});
test('non-finite data cannot be saved as null and cleanup error is preserved',()=>{
 const r=rig(s=>{s.unsubscribe=()=>{throw Error('cleanup failed exactly');};});r.driver.start({sensorPath:'generic',interval:'high'});r.emit({ACCELEROMETER:{x:NaN,y:2,z:3}});
 assert.equal(r.values.length,0);assert.equal(r.driver.state().cleanup.status,'unsubscribe_exception');assert.equal(r.driver.state().cleanup.error.message,'cleanup failed exactly');
});
