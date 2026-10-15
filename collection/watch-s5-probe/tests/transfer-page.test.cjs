const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const research=require('../variants/research-recorder/src/common/research.js'),transfer=require('../variants/research-transfer/src/common/transfer.js');
function page(){
 const filename=path.join(__dirname,'../variants/research-transfer/src/Probe/index.ux');assert.ok(fs.existsSync(filename),'无线传输页面尚未实现');
 const ux=fs.readFileSync(filename,'utf8'),code=ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result=');
 const messages=[],connect={getReadyState(o){o.success({status:1});},send(o){messages.push(typeof o.data==='string'?JSON.parse(o.data):o.data);}};
 const context={research,transfer,interconnect:{instance:()=>connect},sensor:{unsubscribeAccelerometer(){}},file:{},legacyCore:require('../src/common/recorder.js'),Date,Math,JSON,Promise,setInterval:()=>1,clearInterval(){}};
 vm.createContext(context);vm.runInContext(code,context);const p=Object.assign({},context.result.private,context.result);p.onInit();
 return {p,connect,messages};
}
test('wireless export locks capture controls until receiver confirms; opening export never sends automatically',async()=>{
 const {p,messages,connect}=page();p._items=[{id:'1000_abcdef'}];p.openExport();assert.equal(p.exportChoice,true);assert.equal(messages.length,0);
 p._store={inventory:()=>Promise.resolve({id:'1000_abcdef',files:['s5r_1000_abcdef_head.json']}),readPart:()=>Promise.resolve('{}')};
 p.startWireless();await new Promise(setImmediate);assert.equal(p.transferring,true);assert.equal(p.transferMode,true);assert.equal(messages.length,1);
 p.startRecording();p.showCollect();p.openSettings();assert.equal(p.settingsMode,false);assert.equal(messages.length,1);
 for(let i=0;i<2;i++){const m=messages.at(-1);connect.onmessage({data:JSON.stringify({p:'S5ACK1',t:m.t,s:m.s,i:m.i,o:m.l,c:m.c,state:'part_complete'})});await new Promise(setImmediate);}
 assert.equal(p.transferring,false);assert.match(p.transferStatus,/保存/);
});
test('leaving transmission page cancels in-flight work without deleting or changing the selected legacy record',async()=>{
 const {p,messages}=page();p._legacy={session_id:'1000_ab',schema_version:1,rows:[[0,1,2,3,'visible']]};const before=JSON.stringify(p._legacy);
 p.startWireless();await new Promise(setImmediate);assert.equal(messages[0].m,'legacy1');p.onHide();assert.equal(p.transferring,false);assert.equal(JSON.stringify(p._legacy),before);
});
