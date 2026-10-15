const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const research=require('../variants/research-recorder/src/common/research.js');
function setup(){
  const files=new Map();let time=1000;const file={
    list(o){queueMicrotask(()=>o.success({fileList:[...files.keys()].map(uri=>({uri}))}));},
    writeText(o){queueMicrotask(()=>{files.set(o.uri,o.text);o.success();});},
    readText(o){queueMicrotask(()=>files.has(o.uri)?o.success({text:files.get(o.uri)}):o.fail('missing',301));},
    delete(o){queueMicrotask(()=>{files.delete(o.uri);o.success();});}
  };
  const sensor={subscribeAccelerometer(o){this.options=o;},unsubscribeAccelerometer(){}};
  const ux=fs.readFileSync(path.join(__dirname,'../variants/research-recorder/src/Probe/index.ux'),'utf8');
  const script=ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result =');
  const runtime=Object.assign({},research,{createStore:f=>research.createStore(f,{now:()=>time})});
  const context={sensor,file,research:runtime,legacyCore:require('../src/common/recorder.js'),Date,Math,JSON,Promise,setInterval:()=>1,clearInterval(){}};
  vm.createContext(context);vm.runInContext(script,context);const p=Object.assign({},context.result.private,context.result);p.onInit();
  return {p,sensor,files,tick(t){time=t;}};
}
const settle=()=>new Promise(r=>setImmediate(r));
test('request settings reach sensor and files, and controls stay locked during recording',async()=>{
  const {p,sensor,files,tick}=setup();p.openSettings();p.nextValue(); // 10 seconds
  p.nextSetting();p.nextValue(); // ui
  p.closeSettings();p.startRecording();await settle();
  assert.equal(sensor.options.interval,'ui');assert.equal(p.recording,true);
  p.showRecords();p.openSettings();assert.equal(p.tab,'collect');assert.equal(p.settingsMode,false);
  tick(1020);sensor.options.callback({x:1.234567890123,y:2,z:3});p.onHide();tick(1040);sensor.options.callback({x:4,y:5,z:6});p.stopRecording();await settle();await settle();
  assert.equal(p.saving,false);assert.equal(p.persisted,2);p.showRecords();await settle();
  assert.match(p.recordDetail,/2条/);const block=JSON.parse([...files.entries()].find(([n])=>n.includes('_b0000'))[1]);
  assert.equal(block.rows[1][5],'hidden');assert.equal(block.rows[0][2],1.234567890123);assert.ok(block.events.some(e=>e.type==='page_hide'));
});
test('cancelled trash never changes storage, confirmation moves it and restore recovers it',async()=>{
  const {p,sensor,tick}=setup();p.startRecording();await settle();tick(1020);sensor.options.callback({x:1,y:2,z:3});p.stopRecording();await settle();await settle();
  p.showRecords();await settle();p.recordAction();assert.equal(p.confirmMode,true);p.cancelConfirm();assert.equal((await p._store.list(false)).length,1);
  p.recordAction();p.confirmAction();await settle();await settle();assert.equal((await p._store.list(false)).length,0);
  p.toggleTrash();await settle();p.recordAction();await settle();await settle();assert.equal((await p._store.list(false)).length,1);
});
test('segmented export only loads current bounded part and preserves old record identity',async()=>{
  const {p,sensor,tick,files}=setup();p.startRecording();await settle();tick(1020);sensor.options.callback({x:1,y:2,z:3});p.stopRecording();await settle();await settle();
  p.showRecords();await settle();p.openExport();await settle();assert.equal(p.exportMode,true);assert.match(p.qrValue,/^IMUS5\|2\|/);assert.equal(p.partTotal,4);
  p.nextPart();await settle();assert.equal(p.partIndex,1);assert.ok(p._frames.length<219);p.closeExport();
  const old=require('../src/common/recorder.js').createRecorder();old.start();old.append({x:7,y:8,z:9});const record=old.stop();record.metadata.app_version='0.1.1';
  files.set('internal://files/imus5_latest.txt','internal://files/imus5_old.json');files.set('internal://files/imus5_old.json',JSON.stringify(record));
  p.extraAction();await settle();p.openExport();assert.match(p.qrValue,/^IMU9P\|1\|/);assert.equal(p._legacy.metadata.app_version,'0.1.1');
});
