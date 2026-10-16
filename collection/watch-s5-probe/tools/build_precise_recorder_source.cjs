// Independent profile. All older source/bytecode-free builds and exports stay intact.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),version='0.4.1',artifactName='org.imuresearch.s5probe.release.'+version+'.rpk';
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
function one(source,from,to){if(source.split(from).length!==2)throw Error('Precise profile marker mismatch: '+from.slice(0,100));return source.replace(from,to);}
function prepareStage(stage){
 require('./build_input_probe_source.cjs').prepareStage(stage);
 const mp=path.join(stage,'src/manifest.json'),m=JSON.parse(fs.readFileSync(mp));m.versionName=version;m.versionCode=10;fs.writeFileSync(mp,JSON.stringify(m,null,2)+'\n');
 const cp=path.join(stage,'src/common/research.js');let c=fs.readFileSync(cp,'utf8');
 c=one(c,"app_version:'0.4.0'","app_version:'0.4.1'");
 c=one(c,"const duration=options.durationSeconds===undefined?2:options.durationSeconds,interval=options.interval||'game';", "const duration=options.durationSeconds===undefined?2:options.durationSeconds,interval=options.interval||(options.sensorPath==='generic'&&!options.inputProbe?'high':'game');");
 c=one(c,"if((options.inputProbe===true&&(duration!==2||interval!=='game'))||DURATIONS.indexOf(duration)<0||INTERVALS.indexOf(interval)<0)","if((options.sensorPath!==undefined&&['generic','legacy'].indexOf(options.sensorPath)<0)||(options.inputProbe===true&&(duration!==2||interval!=='game'))||DURATIONS.indexOf(duration)<0||(options.sensorPath==='generic'&&!options.inputProbe?['high','mid','low']:INTERVALS).indexOf(interval)<0)");
 c=one(c,"acquisition_api:options.inputProbe===true?'@system.sensor.subscribe':'@system.sensor.subscribeAccelerometer'", "acquisition_api:options.inputProbe===true||options.sensorPath==='generic'?'@system.sensor.subscribe':'@system.sensor.subscribeAccelerometer'");
 c=one(c,'let inputReport=null;','let inputReport=null,acquisitionReport=null,acquisitionHolds=0;');
 c=one(c,"    if(status==='stopping'){\n      if(!count)","    if(status==='stopping'){\n      if(acquisitionHolds>0)return;\n      if(!count)");
 c=one(c,'      if(inputReport!==null)tail.input_probe=inputReport;','      if(inputReport!==null)tail.input_probe=inputReport;\n      if(acquisitionReport!==null)tail.acquisition_observation=acquisitionReport;');
 c=one(c,"head.metadata.record_purpose==='input_probe'&&finite(receivedAt)","head.metadata.acquisition_api==='@system.sensor.subscribe'&&finite(receivedAt)");
 c=one(c,'    state:state,event:event,stop:stop,',`    state:state,event:event,stop:stop,
    holdAcquisition:function(){if(status==='sealed')throw Error('sealed acquisition');acquisitionHolds++;},
    releaseAcquisition:function(){if(acquisitionHolds<=0)throw Error('unbalanced acquisition hold');acquisitionHolds--;if(acquisitionHolds===0&&status==='stopping')pump();},
    setAcquisitionObservation:function(value){
      if(head.metadata.record_purpose!=='recording'||status==='sealed'||ascii(value).length>32768)throw Error('acquisition report boundary');
      if(value.cleanup&&['unsubscribe_exception','handle_unavailable'].indexOf(value.cleanup.status)>=0)warn('sensor_cleanup_unconfirmed');
      acquisitionReport=clone(value);
    },`);
 fs.writeFileSync(cp,c);fs.copyFileSync(path.join(root,'variants/precise-recorder/src/common/sensor-capture.js'),path.join(stage,'src/common/sensor-capture.js'));
 const up=path.join(stage,'src/Probe/index.ux');let ux=fs.readFileSync(up,'utf8').replace(/\r\n/g,'\n');ux=one(ux,'v0.4.0','v0.4.1');ux=require('../variants/precise-recorder/page-overlay.cjs').decorate(ux);fs.writeFileSync(up,ux);
}
async function main(){
 const output=path.resolve(process.argv[2]||path.join(root,'dist/precise-recorder-0.4.1'));
 if(!output.startsWith(path.join(root,'dist')+path.sep)||fs.existsSync(output))throw Error('Output must be a fresh directory inside module dist');
 const modules=fs.existsSync(path.join(root,'node_modules/aiot-toolkit'))?path.join(root,'node_modules'):path.resolve(root,'../band9pro-probe/node_modules');
 const sign=process.env.S5_SIGN_DIR||(fs.existsSync(path.join(root,'sign/private.pem'))?path.join(root,'sign'):path.resolve(root,'../band9pro-probe/sign'));
 if(!fs.existsSync(path.join(modules,'aiot-toolkit'))||!fs.existsSync(path.join(sign,'private.pem')))throw Error('Existing toolkit/signature unavailable');
 const tmp=fs.realpathSync(os.tmpdir());if(/[^\x00-\x7f]/.test(tmp))throw Error('ASCII temporary path required');const stage=fs.mkdtempSync(path.join(tmp,'imus5-precise-'));
 try{
  prepareStage(stage);fs.cpSync(sign,path.join(stage,'sign'),{recursive:true});fs.symlinkSync(modules,path.join(stage,'node_modules'),'junction');
  const names=['manifest.json','app.ux','Probe/index.ux',...fs.readdirSync(path.join(stage,'src/common')).map(n=>'common/'+n)];
  const inputs=Object.fromEntries(names.map(n=>[n,sha(fs.readFileSync(path.join(stage,'src',n)))]));
  const Builder=require(path.join(modules,'aiot-toolkit/lib/builder/VelaUxBuilder')).default;await new Builder().build(stage,{mode:'production',enableJsc:false,enableProtobuf:false});
  const artifact=path.join(stage,'dist',artifactName);if(!fs.existsSync(artifact))throw Error('RPK missing');fs.mkdirSync(output);fs.copyFileSync(artifact,path.join(output,artifactName),fs.constants.COPYFILE_EXCL);
  fs.writeFileSync(path.join(output,'build-report.json'),JSON.stringify({version,version_code:10,artifact:artifactName,bytes:fs.statSync(artifact).size,sha256:sha(fs.readFileSync(artifact)),enable_jsc:false,enable_protobuf:false,staged_source_sha256:inputs,device_installation:'not_performed',generic_probe_0_4_0:'33_rows_fractional_observed',new_recorder_device_validation:'not_performed'},null,2)+'\n',{flag:'wx'});console.log(path.join(output,artifactName));
 }finally{const resolved=fs.realpathSync(stage);if(path.dirname(resolved)!==tmp||!/^imus5-precise-[A-Za-z0-9]+$/.test(path.basename(resolved)))throw Error('Cleanup boundary');const link=path.join(resolved,'node_modules');if(fs.existsSync(link)&&fs.lstatSync(link).isSymbolicLink())fs.unlinkSync(link);fs.rmSync(resolved,{recursive:true,force:true});}
}
module.exports={prepareStage};if(require.main===module)main().catch(e=>{console.error(e.stack);process.exitCode=1;});
