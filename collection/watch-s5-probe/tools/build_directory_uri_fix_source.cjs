// Independent 0.3.4 directory-boundary fix; previous profiles and files remain intact.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),version='0.3.4',artifactName='org.imuresearch.s5probe.release.'+version+'.rpk';
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
function one(source,from,to){if(source.split(from).length!==2)throw Error('Preserved marker mismatch: '+from.slice(0,60));return source.replace(from,to);}
function prepareStage(stage){
 require('./build_storage_diagnostic_source.cjs').prepareStage(stage);
 const mp=path.join(stage,'src/manifest.json'),m=JSON.parse(fs.readFileSync(mp));m.versionName=version;m.versionCode=8;fs.writeFileSync(mp,JSON.stringify(m,null,2)+'\n');
 const page=path.join(stage,'src/Probe/index.ux');fs.writeFileSync(page,one(fs.readFileSync(page,'utf8'),'v0.3.3','v0.3.4'));
 const cp=path.join(stage,'src/common/research.js');let core=fs.readFileSync(cp,'utf8');
 core=one(core,"app_version:'0.3.3'","app_version:'0.3.4'");
 core=one(core,"const ROOT = 'internal://files/';","const directoryEntries = require('./directory-entries.js');\nconst ROOT = 'internal://files/';");
 core=one(core,"function directory(){return call('list',{uri:ROOT}).then(d=>d.fileList || []);}","function directory(){return call('list',{uri:ROOT}).then(d=>directoryEntries.normalize(d&&d.fileList));}");
 fs.writeFileSync(cp,core);fs.copyFileSync(path.join(root,'variants/directory-uri-fix/src/common/directory-entries.js'),path.join(stage,'src/common/directory-entries.js'));
}
async function main(){
 const output=path.resolve(process.argv[2]||path.join(root,'dist/directory-uri-fix-0.3.4'));
 if(!output.startsWith(path.join(root,'dist')+path.sep)||fs.existsSync(output))throw Error('Output must be a fresh directory inside module dist');
 const modules=fs.existsSync(path.join(root,'node_modules/aiot-toolkit'))?path.join(root,'node_modules'):path.resolve(root,'../band9pro-probe/node_modules');
 const sign=process.env.S5_SIGN_DIR||(fs.existsSync(path.join(root,'sign/private.pem'))?path.join(root,'sign'):path.resolve(root,'../band9pro-probe/sign'));
 if(!fs.existsSync(path.join(modules,'aiot-toolkit'))||!fs.existsSync(path.join(sign,'private.pem')))throw Error('Existing toolkit/signature unavailable');
 const tmp=fs.realpathSync(os.tmpdir());if(/[^\x00-\x7f]/.test(tmp))throw Error('ASCII temporary path required');const stage=fs.mkdtempSync(path.join(tmp,'imus5-uri-'));
 try{
  prepareStage(stage);fs.cpSync(sign,path.join(stage,'sign'),{recursive:true});fs.symlinkSync(modules,path.join(stage,'node_modules'),'junction');
  const names=['manifest.json','app.ux','Probe/index.ux','common/icon.png','common/research.js','common/recorder.js','common/transfer.js','common/storage-diagnostic.js','common/directory-entries.js'];
  const inputs=Object.fromEntries(names.map(n=>[n,sha(fs.readFileSync(path.join(stage,'src',n)))]));
  const Builder=require(path.join(modules,'aiot-toolkit/lib/builder/VelaUxBuilder')).default;await new Builder().build(stage,{mode:'production',enableJsc:false,enableProtobuf:false});
  const artifact=path.join(stage,'dist',artifactName);if(!fs.existsSync(artifact))throw Error('RPK missing');fs.mkdirSync(output);fs.copyFileSync(artifact,path.join(output,artifactName),fs.constants.COPYFILE_EXCL);
  fs.writeFileSync(path.join(output,'build-report.json'),JSON.stringify({version,version_code:8,artifact:artifactName,bytes:fs.statSync(artifact).size,sha256:sha(fs.readFileSync(artifact)),enable_jsc:false,enable_protobuf:false,staged_source_sha256:inputs,device_installation:'not_performed',real_record_recovery:'awaiting_user_check',wireless_transfer:'not_hardware_verified'},null,2)+'\n',{flag:'wx'});
  console.log(path.join(output,artifactName));
 }finally{const resolved=fs.realpathSync(stage);if(path.dirname(resolved)!==tmp||!/^imus5-uri-[A-Za-z0-9]+$/.test(path.basename(resolved)))throw Error('Cleanup boundary');const link=path.join(resolved,'node_modules');if(fs.existsSync(link)&&fs.lstatSync(link).isSymbolicLink())fs.unlinkSync(link);fs.rmSync(resolved,{recursive:true,force:true});}
}
module.exports={prepareStage};if(require.main===module)main().catch(e=>{console.error(e.stack);process.exitCode=1;});
