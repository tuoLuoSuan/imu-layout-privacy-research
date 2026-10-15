const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.join(__dirname,'../diagnostics/startup-minimal/src');

test('minimal startup diagnostic has no sensor/storage permission or conditional QR tree',()=>{
 const filename=path.join(root,'manifest.json');
 assert.ok(fs.existsSync(filename),'启动检查包尚未实现');
 const m=JSON.parse(fs.readFileSync(filename,'utf8'));
 assert.equal(m.package,'org.imuresearch.s5start');
 assert.deepEqual(m.features,[]);
 const ux=fs.readFileSync(path.join(root,'Probe/index.ux'),'utf8');
 assert.doesNotMatch(ux,/@system\.|\bimport\b|qrcode|if="|setInterval|setTimeout|subscribe|writeText/);
});

test('minimal diagnostic exposes lifecycle and touch without starting acquisition',()=>{
 const filename=path.join(root,'Probe/index.ux');
 assert.ok(fs.existsSync(filename),'启动检查页面尚未实现');
 const ux=fs.readFileSync(filename,'utf8');
 const script=ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace('export default','result =');
 const context={};vm.createContext(context);vm.runInContext(script,context);
 const p=Object.assign({},context.result.private,context.result);
 assert.equal(p.phase,'D0');p.onInit();assert.equal(p.phase,'D1');
 p.onShow();assert.equal(p.phase,'D2');p.tap();assert.equal(p.phase,'D3');
 p.tap();assert.equal(p.clicks,2);
});
