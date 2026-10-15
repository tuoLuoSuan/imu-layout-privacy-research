// Offline candidate only: same minimal page, JS/JSON format, no device action.
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
if(/[^\x00-\x7f]/.test(tempRoot))throw Error('Source candidate needs an ASCII temporary path');
const stage=fs.mkdtempSync(path.join(tempRoot,'imus5-source-'));
const expected='org.imuresearch.s5start.release.0.0.2.rpk';
async function main(){
 try{
  fs.cpSync(path.join(profile,'src'),path.join(stage,'src'),{recursive:true});
  const manifestFile=path.join(stage,'src/manifest.json');
  const manifest=JSON.parse(fs.readFileSync(manifestFile,'utf8'));
  manifest.versionName='0.0.2';manifest.versionCode=2;
  fs.writeFileSync(manifestFile,JSON.stringify(manifest,null,2));
  fs.mkdirSync(path.join(stage,'src/common'),{recursive:true});
  fs.copyFileSync(path.join(root,'src/common/icon.png'),path.join(stage,'src/common/icon.png'));
  fs.cpSync(sign,path.join(stage,'sign'),{recursive:true});
  fs.copyFileSync(path.join(root,'package.json'),path.join(stage,'package.json'));
  fs.writeFileSync(path.join(stage,'quickapp.config.js'),'module.exports={cli:{enableJsc:false,enableProtobuf:false}};\n');
  fs.symlinkSync(modules,path.join(stage,'node_modules'),'junction');
  const Builder=require(path.join(modules,'aiot-toolkit/lib/builder/VelaUxBuilder')).default;
  await new Builder().build(stage,{mode:'production',enableJsc:false,enableProtobuf:false});
  const artifact=path.join(stage,'dist',expected);
  if(!fs.existsSync(artifact)||fs.statSync(artifact).size<500)throw Error('No source-format candidate produced');
  const output=path.join(profile,'dist/source-format');fs.mkdirSync(output,{recursive:true});
  fs.copyFileSync(artifact,path.join(output,expected));
  const report={artifact:expected,bytes:fs.statSync(artifact).size,sha256:crypto.createHash('sha256').update(fs.readFileSync(artifact)).digest('hex'),
   built_at:new Date().toISOString(),scope:'offline unverified JS/JSON candidate; do not install without a separate reviewed test',
   enable_jsc:false,enable_protobuf:false,aiot_toolkit:'2.0.5',features:[],
   comparison:'same app.ux, Probe/index.ux, minAPI, logical designWidth and icon; temporary manifest version bump only',
   source_sha256:Object.fromEntries(['app.ux','Probe/index.ux'].map(n=>[n,crypto.createHash('sha256').update(fs.readFileSync(path.join(profile,'src',n))).digest('hex')]))};
  fs.writeFileSync(path.join(output,'build-report.json'),JSON.stringify(report,null,2));
  console.log('Offline JS/JSON candidate:',path.join(output,expected));
 }finally{
  const resolved=fs.realpathSync(stage);
  if(path.dirname(resolved)!==tempRoot||!/^imus5-source-[A-Za-z0-9]+$/.test(path.basename(resolved)))throw Error('Temporary directory boundary check failed');
  const link=path.join(resolved,'node_modules');
  if(fs.existsSync(link)&&fs.lstatSync(link).isSymbolicLink())fs.unlinkSync(link);
  fs.rmSync(resolved,{recursive:true,force:true});
 }
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
