// New profile only. Previous builders, source trees, signatures and recordings remain intact.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),version='0.4.0',artifactName='org.imuresearch.s5probe.release.'+version+'.rpk';
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
function one(source,from,to){if(source.split(from).length!==2)throw Error('Preserved marker mismatch: '+from.slice(0,70));return source.replace(from,to);}
function prepareStage(stage){
 require('./build_directory_uri_fix_source.cjs').prepareStage(stage);
 const mp=path.join(stage,'src/manifest.json'),m=JSON.parse(fs.readFileSync(mp));m.versionName=version;m.versionCode=9;fs.writeFileSync(mp,JSON.stringify(m,null,2)+'\n');
 const cp=path.join(stage,'src/common/research.js');let core=fs.readFileSync(cp,'utf8');
 core=one(core,"app_version:'0.3.4'","app_version:'0.4.0'");
 core=one(core,"if(DURATIONS.indexOf(duration)<0||INTERVALS.indexOf(interval)<0)","if((options.inputProbe===true&&(duration!==2||interval!=='game'))||DURATIONS.indexOf(duration)<0||INTERVALS.indexOf(interval)<0)");
 core=one(core,"requested_interval:interval,requested_duration_ms:duration*1000", "record_purpose:options.inputProbe===true?'input_probe':'recording',acquisition_api:options.inputProbe===true?'@system.sensor.subscribe':'@system.sensor.subscribeAccelerometer',requested_interval:options.inputProbe===true?'high':interval,requested_duration_ms:duration*1000");
 core=one(core,'  const id=head.session_id;','  const id=head.session_id;let inputReport=null;');
 core=one(core,'      tailPending=true;lastFlush=now();','      if(inputReport!==null)tail.input_probe=inputReport;\n      tailPending=true;lastFlush=now();');
 core=one(core,'    state:state,event:event,stop:stop,',`    state:state,event:event,stop:stop,
    setInputProbe:function(value){
      if(head.metadata.record_purpose!=='input_probe')throw Error('not an input probe');
      if(status==='sealed'||ascii(value).length>49152)throw Error('input probe report exceeds boundary');
      inputReport=clone(value);
    },`);
 core=one(core,'push:function(value,page){','push:function(value,page,receivedAt){');
 core=one(core,'      const t=now();if(!finite(t))','      const t=head.metadata.record_purpose===\'input_probe\'&&finite(receivedAt)?receivedAt:now();if(!finite(t))');
 fs.writeFileSync(cp,core);
 fs.copyFileSync(path.join(root,'variants/input-probe/src/common/input-probe.js'),path.join(stage,'src/common/input-probe.js'));
 const up=path.join(stage,'src/Probe/index.ux');let ux=fs.readFileSync(up,'utf8');ux=one(ux,'v0.3.4','v0.4.0');
 // Page integration is installed only by this independent profile.
 ux=require('../variants/input-probe/page-overlay.cjs').decorate(ux);
 fs.writeFileSync(up,ux);
}
async function main(){
 const output=path.resolve(process.argv[2]||path.join(root,'dist/input-probe-0.4.0'));
 if(!output.startsWith(path.join(root,'dist')+path.sep)||fs.existsSync(output))throw Error('Output must be a fresh directory inside module dist');
 const modules=fs.existsSync(path.join(root,'node_modules/aiot-toolkit'))?path.join(root,'node_modules'):path.resolve(root,'../band9pro-probe/node_modules');
 const sign=process.env.S5_SIGN_DIR||(fs.existsSync(path.join(root,'sign/private.pem'))?path.join(root,'sign'):path.resolve(root,'../band9pro-probe/sign'));
 if(!fs.existsSync(path.join(modules,'aiot-toolkit'))||!fs.existsSync(path.join(sign,'private.pem')))throw Error('Existing toolkit/signature unavailable');
 const tmp=fs.realpathSync(os.tmpdir());if(/[^\x00-\x7f]/.test(tmp))throw Error('ASCII temporary path required');const stage=fs.mkdtempSync(path.join(tmp,'imus5-input-'));
 try{
  prepareStage(stage);fs.cpSync(sign,path.join(stage,'sign'),{recursive:true});fs.symlinkSync(modules,path.join(stage,'node_modules'),'junction');
  const names=['manifest.json','app.ux','Probe/index.ux',...fs.readdirSync(path.join(stage,'src/common')).map(n=>'common/'+n)];
  const inputs=Object.fromEntries(names.map(n=>[n,sha(fs.readFileSync(path.join(stage,'src',n)))]));
  const Builder=require(path.join(modules,'aiot-toolkit/lib/builder/VelaUxBuilder')).default;await new Builder().build(stage,{mode:'production',enableJsc:false,enableProtobuf:false});
  const artifact=path.join(stage,'dist',artifactName);if(!fs.existsSync(artifact))throw Error('RPK missing');fs.mkdirSync(output);fs.copyFileSync(artifact,path.join(output,artifactName),fs.constants.COPYFILE_EXCL);
  fs.writeFileSync(path.join(output,'build-report.json'),JSON.stringify({version,version_code:9,artifact:artifactName,bytes:fs.statSync(artifact).size,sha256:sha(fs.readFileSync(artifact)),enable_jsc:false,enable_protobuf:false,staged_source_sha256:inputs,device_installation:'not_performed',generic_sensor_runtime:'not_verified',raw_input_precision:'not_verified'},null,2)+'\n',{flag:'wx'});
  console.log(path.join(output,artifactName));
 }finally{const resolved=fs.realpathSync(stage);if(path.dirname(resolved)!==tmp||!/^imus5-input-[A-Za-z0-9]+$/.test(path.basename(resolved)))throw Error('Cleanup boundary');const link=path.join(resolved,'node_modules');if(fs.existsSync(link)&&fs.lstatSync(link).isSymbolicLink())fs.unlinkSync(link);fs.rmSync(resolved,{recursive:true,force:true});}
}
module.exports={prepareStage};if(require.main===module)main().catch(e=>{console.error(e.stack);process.exitCode=1;});
