const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {fixture,page}=require('./fixtures.cjs');
function withoutOptionalNumberHelper(f){
 const root=path.join(__dirname,'../src/Manage'),raw=fs.readFileSync(path.join(root,'index.ux'),'utf8'),script=raw.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm,'').replace('export default','module.exports=');
 const s={module:{exports:{}},require:n=>require(path.join(root,n)),file:f.file,brightness:{setKeepScreenOn(o){o.success();}},router:{replace(){},push(){}},Promise,setTimeout,clearTimeout};vm.createContext(s);vm.runInContext('Number.isFinite=undefined;',s);vm.runInContext(script,s);const spec=s.module.exports,p=Object.assign({},spec,JSON.parse(JSON.stringify(spec.data)));p.onInit();return p;
}
test('a missing optional Number helper does not reject after successful discovery',async()=>{
 const f=fixture(),p=withoutOptionalNumberHelper(f);await p.onShow();assert.equal(p.stage,'list');assert.equal(p.totalCount,2);assert.match(p.row0,/待核对/);assert.equal(f.calls.delete.length,0);p.onDestroy();
});
test('formatter failure enters a non-formatting error state with no rejected load promise',async()=>{
 const f=fixture(),old=new Map(f.files),p=page('Manage',f);p.label=()=>{throw Error('injected row-format failure');};await p.onShow();assert.equal(p.stage,'error');assert.equal(p.busy,false);assert.equal(p._ready,null);assert.equal(p.row0,'');assert.equal(p.can0,false);assert.match(p.message,/injected/);assert.equal(f.calls.delete.length,0);for(const [u,t] of old)assert.equal(f.files.get(u),t);p.onDestroy();
});
test('formatting failure in a selection callback is caught before preparing a delete',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();p.label=()=>{throw Error('selection render failed');};assert.doesNotThrow(()=>p.toggle0());assert.equal(p.stage,'error');assert.equal(p.selectedCount,0);assert.equal(p._ready,null);assert.equal(f.calls.delete.length,0);p.onDestroy();
});
test('formatting failure before final purge invalidates consent and issues no delete',async()=>{
 const f=fixture(),p=page('Manage',f);await p.onShow();p.toggleAll();await p.primary();assert.equal(p.stage,'confirm');p.label=()=>{throw Error('delete render failed');};await p.primary();assert.equal(p.stage,'error');assert.equal(p._ready,null);assert.equal(f.calls.delete.length,0);p.onDestroy();
});
