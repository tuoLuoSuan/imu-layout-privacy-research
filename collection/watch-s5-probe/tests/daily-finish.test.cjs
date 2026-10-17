const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const previous=path.join(__dirname,'research-ready.test.cjs'),prefix=fs.readFileSync(previous,'utf8').split("test('independent candidate")[0];
function load(builder){
 let code=prefix.replace("path.join(root,'tools/build_research_ready_source.cjs')",JSON.stringify(path.resolve(__dirname,'../tools',builder))).replace('i<30;i++','i<160;i++');
 code=code.replaceAll('Math,JSON','Math:Object.assign(Object.create(Math),{random:()=>0.5}),JSON');
 const m=new Module(previous,module);m.filename=previous;m.paths=module.paths;m._compile(code+'\nmodule.exports={rig,record,addSession,settle,sources,manifest};',previous);return m.exports;
}
const baseline=load('build_catalog_recovery_source.cjs'),candidate=fs.existsSync(path.resolve(__dirname,'../tools/build_daily_finish_source.cjs'))?load('build_daily_finish_source.cjs'):baseline;
module.exports=candidate;
test('daily0415 keeps ordinary capabilities and single records organize action',()=>{
 assert.equal(candidate.manifest.versionName,'0.4.15');assert.equal(candidate.manifest.versionCode,24);
 assert.deepEqual(candidate.manifest.features,baseline.manifest.features);
 const template=candidate.sources.page.match(/<template>([\s\S]*?)<\/template>/)[1];
 assert.match(template,/已保存 \{\{persisted\}\} \/ \{\{samples\}\}/);assert.match(template,/整理记录/);
 assert.doesNotMatch(template,/onclick="recordAction"|onclick="inspectStorage"|onclick="openInputProbe"|界面检查|输入检查|文件诊断/);
 assert.match(template,/onclick="openBatch"/);assert.match(template,/onclick="extraAction"/);assert.match(template,/备用二维码/);
});
test('daily labels keep real warnings and do not show startup test instructions',async()=>{
 const {r}=await candidate.record('high',60,6000);assert.equal(r.page.recording,true);assert.doesNotMatch(r.page.status,/检查high|测试|诊断/);
 r.page.stopRecording();await candidate.settle();assert.equal(r.tail().startup_rate_observation.status,'passed');
 const slow=await candidate.record('high',200,6000);assert.equal(slow.r.tail().stop_reason,'startup_rate_low');assert.ok(slow.r.tail().quality.warnings.includes('startup_rate_low'));
});
test('same synthetic observations preserve every head/block/tail byte apart from app version',async()=>{
 const left=await baseline.record('high',60,12000),right=await candidate.record('high',60,12000);
 left.r.page.stopRecording();right.r.page.stopRecording();await baseline.settle();await candidate.settle();
 const normalize=r=>r.parts().map(v=>{if(v.kind==='head')v.metadata.app_version='normalized-only-in-test';return JSON.stringify(v);}).sort();
 assert.deepEqual(normalize(left.r),normalize(right.r));assert.deepEqual(right.r.screens,[true,false]);
});
test('daily source freezes catalog, capture, screen and original storage except version literal',()=>{
 for(const name of Object.keys(baseline.sources).filter(x=>x!=='page'&&x!=='research.js'))assert.equal(candidate.sources[name],baseline.sources[name],name);
 assert.equal(candidate.sources['research.js'].replace("app_version:'0.4.15'","app_version:'0.4.14'"),baseline.sources['research.js']);
});
