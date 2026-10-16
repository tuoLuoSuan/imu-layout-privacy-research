// Independent 0.4.2 profile: preserve every earlier source tree and distributed package.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),version='0.4.2',artifactName='org.imuresearch.s5probe.release.'+version+'.rpk';
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
function one(s,a,b){if(s.split(a).length!==2)throw Error('Continuity marker mismatch: '+a.slice(0,90));return s.replace(a,b);}
function prepareStage(stage){
 require('./build_precise_recorder_source.cjs').prepareStage(stage);
 const mp=path.join(stage,'src/manifest.json'),m=JSON.parse(fs.readFileSync(mp));m.versionName=version;m.versionCode=11;fs.writeFileSync(mp,JSON.stringify(m,null,2)+'\n');
 const cp=path.join(stage,'src/common/research.js');let c=fs.readFileSync(cp,'utf8');
 c=one(c,"app_version:'0.4.1'","app_version:'0.4.2'");
 c=one(c,"const ROOT = 'internal://files/';","const continuityObserver = require('./continuity-observer.js');\nconst ROOT = 'internal://files/';");
 c=one(c,"record_purpose:options.inputProbe===true?'input_probe':'recording',acquisition_api:","record_purpose:options.inputProbe===true?'input_probe':'recording',sensor_path:options.inputProbe===true||options.sensorPath==='generic'?'generic':'legacy',continuity_policy:continuityObserver.policy(),acquisition_api:");
 c=one(c,'const id=head.session_id;','const id=head.session_id;const continuity=continuityObserver.create(head.started_epoch_ms,event);');
 c=one(c,'  function event(type,detail){','  function event(type,detail,observedAt){');
 c=one(c,'events.push({callback_epoch_ms:now(),type:','events.push({callback_epoch_ms:type===\'capture_heartbeat\'&&finite(observedAt)?observedAt:now(),type:');
 c=one(c,"    status='stopping';stopReason=reason||'manual';stopped=now();event('stop_requested',stopReason);",`    const cut=now(),observed=continuity.snapshot(cut,count);
    if(observed.silence_observed)warn('sensor_silence_observed');
    if(observed.late_tick_count||observed.terminal_tick_gap_ms>head.metadata.continuity_policy.tick_delay_warning_ms)warn('heartbeat_tick_delay');
    if(reason==='duration'&&observed.terminal_gap_ms>head.metadata.continuity_policy.silence_limit_ms)reason='sensor_silence';
    status='stopping';stopReason=reason||'manual';stopped=cut;event('stop_requested',stopReason);`);
 c=one(c,'      if(inputReport!==null)tail.input_probe=inputReport;','      tail.continuity_observation=continuity.snapshot(stopped,count);\n      if(inputReport!==null)tail.input_probe=inputReport;');
 c=one(c,"      rows.push([count++,t,value.x,value.y,value.z,page==='hidden'?'hidden':'visible']);","      rows.push([count++,t,value.x,value.y,value.z,page==='hidden'?'hidden':'visible']);\n      continuity.accepted(t,count);");
 c=one(c,'    tick:function(){\n      const t=now();','    tick:function(){\n      const t=now();if(status===\'recording\')continuity.tick(t,count);');
 c=one(c,"        if(t-head.started_epoch_ms>=head.metadata.requested_duration_ms){stop('duration');return;}\n        if(t-lastReceived>3000){stop('sensor_silence');return;}","        if(t-lastReceived>3000){stop('sensor_silence');return;}\n        if(t-head.started_epoch_ms>=head.metadata.requested_duration_ms){stop('duration');return;}");
 fs.writeFileSync(cp,c);fs.copyFileSync(path.join(root,'variants/continuity-recorder/src/common/continuity-observer.js'),path.join(stage,'src/common/continuity-observer.js'));
 const up=path.join(stage,'src/Probe/index.ux');let ux=fs.readFileSync(up,'utf8');ux=one(ux,'v0.4.1','v0.4.2');
 ux=one(ux,"(s.warnings.length?'已保存，需核验 · '+s.stop_reason:'已保存 '+s.persisted+'条 · 可导出')","(s.stop_reason==='sensor_silence'?'采集已中断 · 已保存，请导出核验':s.warnings.length?'已保存，需核验 · '+s.stop_reason:'已保存 '+s.persisted+'条 · 可导出')");
 fs.writeFileSync(up,ux);
}
async function main(){
 const output=path.resolve(process.argv[2]||path.join(root,'dist/continuity-recorder-0.4.2'));
 if(!output.startsWith(path.join(root,'dist')+path.sep)||fs.existsSync(output))throw Error('Output must be a fresh directory inside module dist');
 const modules=fs.existsSync(path.join(root,'node_modules/aiot-toolkit'))?path.join(root,'node_modules'):path.resolve(root,'../band9pro-probe/node_modules');
 const sign=process.env.S5_SIGN_DIR||(fs.existsSync(path.join(root,'sign/private.pem'))?path.join(root,'sign'):path.resolve(root,'../band9pro-probe/sign'));
 if(!fs.existsSync(path.join(modules,'aiot-toolkit'))||!fs.existsSync(path.join(sign,'private.pem')))throw Error('Existing toolkit/signature unavailable');
 const tmp=fs.realpathSync(os.tmpdir());if(/[^\x00-\x7f]/.test(tmp))throw Error('ASCII temporary path required');const stage=fs.mkdtempSync(path.join(tmp,'imus5-continuity-'));
 try{
  prepareStage(stage);fs.cpSync(sign,path.join(stage,'sign'),{recursive:true});fs.symlinkSync(modules,path.join(stage,'node_modules'),'junction');
  const names=['manifest.json','app.ux','Probe/index.ux',...fs.readdirSync(path.join(stage,'src/common')).map(n=>'common/'+n)];
  const inputs=Object.fromEntries(names.map(n=>[n,sha(fs.readFileSync(path.join(stage,'src',n)))]));
  const Builder=require(path.join(modules,'aiot-toolkit/lib/builder/VelaUxBuilder')).default;await new Builder().build(stage,{mode:'production',enableJsc:false,enableProtobuf:false});
  const artifact=path.join(stage,'dist',artifactName);if(!fs.existsSync(artifact))throw Error('RPK missing');fs.mkdirSync(output);fs.copyFileSync(artifact,path.join(output,artifactName),fs.constants.COPYFILE_EXCL);
  fs.writeFileSync(path.join(output,'build-report.json'),JSON.stringify({version,version_code:11,artifact:artifactName,bytes:fs.statSync(artifact).size,sha256:sha(fs.readFileSync(artifact)),enable_jsc:false,enable_protobuf:false,staged_source_sha256:inputs,device_installation:'not_performed',continuity_device_validation:'not_performed'},null,2)+'\n',{flag:'wx'});
  console.log(path.join(output,artifactName));
 }finally{
  const resolved=fs.realpathSync(stage);if(path.dirname(resolved)!==tmp||!/^imus5-continuity-[A-Za-z0-9]+$/.test(path.basename(resolved)))throw Error('Cleanup boundary');
  const link=path.join(resolved,'node_modules');if(fs.existsSync(link)&&fs.lstatSync(link).isSymbolicLink())fs.unlinkSync(link);fs.rmSync(resolved,{recursive:true,force:true});
 }
}
module.exports={prepareStage};if(require.main===module)main().catch(e=>{console.error(e.stack);process.exitCode=1;});
