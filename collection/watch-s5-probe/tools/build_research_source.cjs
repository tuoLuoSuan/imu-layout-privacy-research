// Offline-only build. Preserved prototypes and earlier UI build are never overwritten.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),version='0.3.0',artifactName='org.imuresearch.s5probe.release.'+version+'.rpk';
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
function prepareStage(stage){
  require('./build_ui_source.cjs').prepareStage(stage);
  const manifestPath=path.join(stage,'src/manifest.json'),m=JSON.parse(fs.readFileSync(manifestPath));m.versionName=version;m.versionCode=4;
  fs.writeFileSync(manifestPath,JSON.stringify(m,null,2)+'\n');
  fs.cpSync(path.join(root,'variants/research-recorder/src'),path.join(stage,'src'),{recursive:true});
}
async function main(){
  const output=path.resolve(process.argv[2]||path.join(root,'dist/research-0.3.0')),reportPath=path.join(output,'build-report.json');
  if(!output.startsWith(path.join(root,'dist')+path.sep))throw Error('Output must stay within this module dist directory');
  if(fs.existsSync(path.join(output,artifactName))||fs.existsSync(reportPath))throw Error('Output exists; refusing overwrite');
  const modules=fs.existsSync(path.join(root,'node_modules/aiot-toolkit'))?path.join(root,'node_modules'):path.resolve(root,'../band9pro-probe/node_modules');
  const sign=process.env.S5_SIGN_DIR||(fs.existsSync(path.join(root,'sign/private.pem'))?path.join(root,'sign'):path.resolve(root,'../band9pro-probe/sign'));
  if(!fs.existsSync(path.join(modules,'aiot-toolkit'))||!fs.existsSync(path.join(sign,'private.pem'))||!fs.existsSync(path.join(sign,'certificate.pem')))throw Error('Local toolkit/signature unavailable');
  const tmp=fs.realpathSync(os.tmpdir());if(/[^\x00-\x7f]/.test(tmp))throw Error('Toolkit needs an ASCII temporary path');
  const stage=fs.mkdtempSync(path.join(tmp,'imus5-research-'));
  try{
    prepareStage(stage);fs.cpSync(sign,path.join(stage,'sign'),{recursive:true});fs.symlinkSync(modules,path.join(stage,'node_modules'),'junction');
    const sourceFiles=['manifest.json','app.ux','Probe/index.ux','common/icon.png','common/recorder.js','common/research.js'];
    const inputs=Object.fromEntries(sourceFiles.map(n=>[n,sha(fs.readFileSync(path.join(stage,'src',n)))]));
    const Builder=require(path.join(modules,'aiot-toolkit/lib/builder/VelaUxBuilder')).default;
    await new Builder().build(stage,{mode:'production',enableJsc:false,enableProtobuf:false});
    const artifact=path.join(stage,'dist',artifactName);if(!fs.existsSync(artifact))throw Error('RPK not produced');
    fs.mkdirSync(output,{recursive:true});fs.copyFileSync(artifact,path.join(output,artifactName),fs.constants.COPYFILE_EXCL);
    fs.writeFileSync(reportPath,JSON.stringify({version:version,version_code:4,artifact:artifactName,bytes:fs.statSync(artifact).size,
      sha256:sha(fs.readFileSync(artifact)),built_at:new Date().toISOString(),enable_jsc:false,enable_protobuf:false,
      aiot_toolkit:'2.0.5',features:mFeatures(),staged_source_sha256:inputs,device_installation:'not_performed',hardware_continuity:'not_verified',
      upgrade_gate:'retrieve existing 0.1.1 raw session first, then staged 2s/30s/60s device checks'},null,2)+'\n',{flag:'wx'});
    console.log(path.join(output,artifactName));
  }finally{
    const resolved=fs.realpathSync(stage);if(path.dirname(resolved)!==tmp||!/^imus5-research-[A-Za-z0-9]+$/.test(path.basename(resolved)))throw Error('Cleanup boundary failed');
    const link=path.join(resolved,'node_modules');if(fs.existsSync(link)&&fs.lstatSync(link).isSymbolicLink())fs.unlinkSync(link);fs.rmSync(resolved,{recursive:true,force:true});
  }
}
function mFeatures(){return ['system.sensor','system.file'];}
module.exports={prepareStage};if(require.main===module)main().catch(e=>{console.error(e.stack);process.exitCode=1;});
