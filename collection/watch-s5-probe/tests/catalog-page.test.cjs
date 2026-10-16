const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const root=path.join(__dirname,'..');
async function settle(){await new Promise(setImmediate);await new Promise(setImmediate);}
function rig(){
 const tmp=fs.realpathSync(os.tmpdir()),stage=fs.mkdtempSync(path.join(tmp,'imus5-catalog-test-'));let profile;
 try{require('../tools/build_catalog_recorder_source.cjs').prepareStage(stage);profile={core:require(path.join(stage,'src/common/research.js')),catalog:require(path.join(stage,'src/common/record-catalog.js')),ux:fs.readFileSync(path.join(stage,'src/Probe/index.ux'),'utf8'),manifest:JSON.parse(fs.readFileSync(path.join(stage,'src/manifest.json')))};}
 finally{assert.equal(path.dirname(fs.realpathSync(stage)),tmp);fs.rmSync(stage,{recursive:true,force:true});}
 const files=new Map(),calls={list:0,read:[],sensor:0,screen:0};
 for(let i=0;i<30;i++){const id=String(1000+i)+'_abcdef',p='internal://files/s5r_'+id;files.set(p+'_head.json',JSON.stringify({kind:'head',schema_version:2,session_id:id,started_epoch_ms:1000}));files.set(p+'_b0000.json','{}');files.set(p+'_tail.json',JSON.stringify({kind:'tail',schema_version:2,session_id:id,blocks:1,persisted:i+1,stopped_epoch_ms:2000,stop_reason:'duration',quality:{warnings:[]}}));}
 const file={list:o=>{calls.list++;o.success({fileList:[...files.keys()].map(uri=>({uri:uri.replace('files/','files//')}))});},readText:o=>{calls.read.push(o.uri);o.success({text:files.get(o.uri)});}};
 const context={sensor:{subscribe:()=>{calls.sensor++;throw Error('must not subscribe from list');}},file,research:profile.core,recordCatalog:profile.catalog,screenGuard:{},sensorCapture:{},inputProbe:{},storageDiagnostic:{},legacyCore:{},transfer:{},interconnect:{},Date,Math,JSON,Promise,setTimeout,clearTimeout,setInterval:()=>1,clearInterval(){},require:()=>{calls.screen++;throw Error('must not alter screen from list');}};
 vm.createContext(context);vm.runInContext(profile.ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','result='),context);
 const page=Object.assign({},context.result.private,context.result);page.onInit();return {page,profile,calls,files};
}
test('actual built page reads only selected head/tail, supports observed double-slash URIs and cached navigation',async()=>{
 const r=rig();r.page.showRecords();await settle();assert.equal(r.page.recordPosition,'1 / 30');assert.equal(r.page.recordTitle,'会话 abcdef');assert.match(r.page.recordDetail,/30条/);
 assert.equal(r.calls.list,1);assert.equal(r.calls.read.length,2);assert.equal(r.page.loading,false);
 r.page.nextRecord();await settle();assert.match(r.page.recordDetail,/29条/);assert.equal(r.calls.read.length,4);
 r.page.previousRecord();await settle();assert.match(r.page.recordDetail,/30条/);assert.equal(r.calls.read.length,4);assert.equal(r.calls.list,1);
 r.page.showCollect();r.page.showRecords();await settle();assert.equal(r.calls.list,2);assert.equal(r.calls.read.length,4);assert.equal(r.calls.sensor+r.calls.screen,0);
});
test('selected corruption is shown without dropping unrelated records or writing files',async()=>{
 const r=rig();r.files.set('internal://files/s5r_1029_abcdef_tail.json','bad JSON');r.page.showRecords();await settle();assert.match(r.page.recordQuality,/损坏/);assert.equal(r.page.recordPosition,'1 / 30');
 r.page.nextRecord();await settle();assert.match(r.page.recordDetail,/29条/);assert.equal(r.page.alert,false);
});
test('new profile retains ordinary features and byte-identical acquisition, transport and screen modules',()=>{
 const r=rig();assert.equal(r.profile.manifest.versionName,'0.4.4');assert.equal(r.profile.manifest.versionCode,13);
 assert.deepEqual(r.profile.manifest.features.map(f=>f.name).sort(),['system.brightness','system.file','system.interconnect','system.sensor']);
 assert.match(r.profile.ux,/recordCatalog.wrap/);assert.match(r.profile.ux,/this\._store\.inventory/);assert.match(r.profile.ux,/this\._store\.purge/);
 const tmp=fs.realpathSync(os.tmpdir()),a=fs.mkdtempSync(path.join(tmp,'imus5-catalog-compare-')),b=fs.mkdtempSync(path.join(tmp,'imus5-catalog-compare-'));
 try{require('../tools/build_foreground_recorder_source.cjs').prepareStage(a);require('../tools/build_catalog_recorder_source.cjs').prepareStage(b);
  for(const n of ['sensor-capture.js','screen-guard.js','continuity-observer.js','transfer.js','directory-entries.js'])assert.deepEqual(fs.readFileSync(path.join(a,'src/common',n)),fs.readFileSync(path.join(b,'src/common',n)));
  assert.equal(fs.readFileSync(path.join(a,'src/common/research.js'),'utf8').replace("app_version:'0.4.3'","app_version:'0.4.4'"),fs.readFileSync(path.join(b,'src/common/research.js'),'utf8'));
 }finally{for(const p of [a,b]){assert.equal(path.dirname(fs.realpathSync(p)),tmp);fs.rmSync(p,{recursive:true,force:true});}}
});
