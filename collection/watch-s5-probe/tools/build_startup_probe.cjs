// Separate diagnostic package; does not overwrite the acquisition RPK or source.
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const profile=path.join(root,'diagnostics/startup-minimal');
const sibling=path.resolve(root,'../band9pro-probe');
const modules=fs.existsSync(path.join(root,'node_modules/aiot-toolkit'))?path.join(root,'node_modules'):path.join(sibling,'node_modules');
const sign=process.env.S5_SIGN_DIR||(fs.existsSync(path.join(root,'sign/private.pem'))?path.join(root,'sign'):path.join(sibling,'sign'));
const tempRoot=fs.realpathSync(os.tmpdir());
if (/[^\x00-\x7f]/.test(tempRoot)) throw Error('Diagnostic build needs an ASCII temporary path');
const stage=fs.mkdtempSync(path.join(tempRoot,'imus5-start-'));
const expected='org.imuresearch.s5start.release.0.0.1.rpk';
async function main(){
 try{
  fs.cpSync(path.join(profile,'src'),path.join(stage,'src'),{recursive:true});
  // Shared icon and signing identity are copied only into the bounded build stage.
  fs.mkdirSync(path.join(stage,'src/common'),{recursive:true});
  fs.copyFileSync(path.join(root,'src/common/icon.png'),path.join(stage,'src/common/icon.png'));
  fs.cpSync(sign,path.join(stage,'sign'),{recursive:true});
  for(const name of ['package.json','quickapp.config.js'])fs.copyFileSync(path.join(root,name),path.join(stage,name));
  fs.symlinkSync(modules,path.join(stage,'node_modules'),'junction');
  const Builder=require(path.join(modules,'aiot-toolkit/lib/builder/VelaUxBuilder')).default;
  await new Builder().build(stage,{mode:'production',enableJsc:true,enableProtobuf:true});
  const artifact=path.join(stage,'dist',expected);
  if(!fs.existsSync(artifact)||fs.statSync(artifact).size<500)throw Error('No diagnostic RPK produced');
  const output=path.join(profile,'dist');fs.mkdirSync(output,{recursive:true});
  fs.copyFileSync(artifact,path.join(output,expected));
  const report={artifact:expected,bytes:fs.statSync(artifact).size,sha256:crypto.createHash('sha256').update(fs.readFileSync(artifact)).digest('hex'),
   built_at:new Date().toISOString(),scope:'startup isolation only; not an acquisition fix or device acceptance',
   jsc:true,protobuf:true,aiot_toolkit:'2.0.5',jsc_version:'1.0.9',features:[]};
  fs.writeFileSync(path.join(output,'build-report.json'),JSON.stringify(report,null,2));
  console.log('Diagnostic RPK:',path.join(output,expected));
 }finally{
  const resolved=fs.realpathSync(stage);
  if(path.dirname(resolved)!==tempRoot||!/^imus5-start-[A-Za-z0-9]+$/.test(path.basename(resolved)))throw Error('Temporary directory boundary check failed');
  const link=path.join(resolved,'node_modules');
  if(fs.existsSync(link)&&fs.lstatSync(link).isSymbolicLink())fs.unlinkSync(link);
  fs.rmSync(resolved,{recursive:true,force:true});
 }
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
