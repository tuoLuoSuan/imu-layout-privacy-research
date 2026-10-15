// Independent 0.3.2 round-icon candidate. Never patches the preserved 0.3.1 profile.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),version='0.3.2',artifactName='org.imuresearch.s5probe.release.'+version+'.rpk';
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
function prepareStage(stage){
 require('./build_transfer_source.cjs').prepareStage(stage);
 const mp=path.join(stage,'src/manifest.json'),m=JSON.parse(fs.readFileSync(mp));m.versionName=version;m.versionCode=6;fs.writeFileSync(mp,JSON.stringify(m,null,2)+'\n');
 for(const [name,from,to] of [['Probe/index.ux','v0.3.1','v0.3.2'],['common/research.js',"app_version:'0.3.1'","app_version:'0.3.2'"]]){
  const file=path.join(stage,'src',name),source=fs.readFileSync(file,'utf8');if(source.split(from).length!==2)throw Error('Unexpected preserved version literal');fs.writeFileSync(file,source.replace(from,to));
 }
 fs.copyFileSync(path.join(root,'variants/transfer-round/icon.png'),path.join(stage,'src/common/icon.png'));
}
async function main(){
 const output=path.resolve(process.argv[2]||path.join(root,'dist/transfer-0.3.2'));
 if(!output.startsWith(path.join(root,'dist')+path.sep)||fs.existsSync(output))throw Error('Output must be a fresh directory inside module dist');
 const modules=fs.existsSync(path.join(root,'node_modules/aiot-toolkit'))?path.join(root,'node_modules'):path.resolve(root,'../band9pro-probe/node_modules');
 const sign=process.env.S5_SIGN_DIR||(fs.existsSync(path.join(root,'sign/private.pem'))?path.join(root,'sign'):path.resolve(root,'../band9pro-probe/sign'));
 if(!fs.existsSync(path.join(modules,'aiot-toolkit'))||!fs.existsSync(path.join(sign,'private.pem')))throw Error('Existing toolkit/signature unavailable');
 const tmp=fs.realpathSync(os.tmpdir());if(/[^\x00-\x7f]/.test(tmp))throw Error('ASCII temporary path required');const stage=fs.mkdtempSync(path.join(tmp,'imus5-round-'));
 try{
  prepareStage(stage);fs.cpSync(sign,path.join(stage,'sign'),{recursive:true});fs.symlinkSync(modules,path.join(stage,'node_modules'),'junction');
  const names=['manifest.json','app.ux','Probe/index.ux','common/icon.png','common/research.js','common/recorder.js','common/transfer.js'];
  const inputs=Object.fromEntries(names.map(n=>[n,sha(fs.readFileSync(path.join(stage,'src',n)))]));
  const Builder=require(path.join(modules,'aiot-toolkit/lib/builder/VelaUxBuilder')).default;await new Builder().build(stage,{mode:'production',enableJsc:false,enableProtobuf:false});
  const artifact=path.join(stage,'dist',artifactName);if(!fs.existsSync(artifact))throw Error('RPK missing');fs.mkdirSync(output);fs.copyFileSync(artifact,path.join(output,artifactName),fs.constants.COPYFILE_EXCL);
  fs.writeFileSync(path.join(output,'build-report.json'),JSON.stringify({version,version_code:6,artifact:artifactName,bytes:fs.statSync(artifact).size,sha256:sha(fs.readFileSync(artifact)),enable_jsc:false,enable_protobuf:false,staged_source_sha256:inputs,device_installation:'not_performed',wireless_transfer:'not_hardware_verified'},null,2)+'\n',{flag:'wx'});
  console.log(path.join(output,artifactName));
 }finally{const resolved=fs.realpathSync(stage);if(path.dirname(resolved)!==tmp||!/^imus5-round-[A-Za-z0-9]+$/.test(path.basename(resolved)))throw Error('Cleanup boundary');const link=path.join(resolved,'node_modules');if(fs.existsSync(link)&&fs.lstatSync(link).isSymbolicLink())fs.unlinkSync(link);fs.rmSync(resolved,{recursive:true,force:true});}
}
module.exports={prepareStage};if(require.main===module)main().catch(e=>{console.error(e.stack);process.exitCode=1;});
