// Explicit replacement identity only. Does not install, uninstall or access devices.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const suite=path.resolve(__dirname,'..'),repo=path.resolve(suite,'../..');
const OLD_CERT='47d3e2a887e50f35a84580a2c3c38bb2977d39a0f21d79ba3584357967d6b617';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
function identity(dir){
 const key=path.join(dir,'private.pem'),cert=path.join(dir,'certificate.pem');
 if(!fs.existsSync(key)||!fs.existsSync(cert))throw Error('Original replacement signing identity files required; no implicit key generation');
 const certBody=fs.readFileSync(cert),digest=sha(certBody),certificate=new crypto.X509Certificate(certBody);
 if(digest===OLD_CERT)throw Error('New identity builder refuses the old certificate');
 const publicKey=crypto.createPublicKey(crypto.createPrivateKey(fs.readFileSync(key))).export({format:'der',type:'spki'});
 if(!publicKey.equals(certificate.publicKey.export({format:'der',type:'spki'})))throw Error('Signing private key and certificate do not match');
 return {certificate_sha256:digest,certificate_der_sha256:sha(certificate.raw),previous_certificate_sha256:OLD_CERT,
         same_signature_update:false,key_matches_certificate:true,identity_generation:'new-2026-10-25'};
}
function sourceInputs(source){const inputs={};function visit(folder){for(const e of fs.readdirSync(folder,{withFileTypes:true})){
 const p=path.join(folder,e.name);if(e.isSymbolicLink())throw Error('Source symlinks not accepted');
 if(e.isDirectory())visit(p);else {const name=path.relative(source,p).replace(/\\/g,'/');if(/\.(pem|key|jks|keystore)$/i.test(name))throw Error('Signing material found inside application source');inputs[name]=sha(fs.readFileSync(p));}
 }}visit(source);return inputs;}
async function main(){
 const out=path.resolve(process.argv[2]||''),source=path.resolve(process.argv[3]||path.join(suite,'maintenance/daily-0.2.20/src'));
 if(!out.startsWith(path.join(suite,'dist')+path.sep)||fs.existsSync(out))throw Error('Fresh output inside suite/dist required');
 const sign=path.resolve(process.env.IMU_WATCH_SIGN_DIR||path.join(repo,'secrets/watch-signing-20261025'));
 const modules=path.resolve(process.env.IMU_WATCH_NODE_MODULES||path.join(repo,'.cache/vela-toolchain-20261025/node_modules'));
 const signer=identity(sign),inputs=sourceInputs(source),manifest=JSON.parse(fs.readFileSync(path.join(source,'manifest.json')));
 if(manifest.package!=='org.imuresearch.s5joint')throw Error('Existing phone/plugin route expects original package name');
 const builder=path.join(modules,'aiot-toolkit/lib/builder/VelaUxBuilder');
 if(!fs.existsSync(builder+'.js'))throw Error('Prepared pinned local toolchain required');
 const stage=fs.mkdtempSync(path.join(fs.realpathSync(os.tmpdir()),'imu-watch-new-'));
 if(/[^\x00-\x7f]/.test(stage))throw Error('ASCII stage required by vendor toolchain');
 fs.cpSync(source,path.join(stage,'src'),{recursive:true});fs.mkdirSync(path.join(stage,'sign'));
 for(const name of ['private.pem','certificate.pem'])fs.copyFileSync(path.join(sign,name),path.join(stage,'sign',name),fs.constants.COPYFILE_EXCL);
 fs.symlinkSync(modules,path.join(stage,'node_modules'),'junction');
 // Preserve and register temporary signing replicas. Never recursively clean a
 // pre-existing tree or delete a key as part of ordinary workspace housekeeping.
 const replicas=[path.join(stage,'sign'),path.join(path.dirname(stage),'.temp_'+path.basename(stage),'sign')];
 const localReceipt=path.join(sign,'build-replicas-'+path.basename(stage)+'.json');
 fs.writeFileSync(localReceipt,JSON.stringify({source:sign,protected_signing_replicas:replicas},null,2),{flag:'wx'});
 const Builder=require(builder).default;await new Builder().build(stage,{mode:'production',enableJsc:false,enableProtobuf:false});
 const name=manifest.package+'.release.'+manifest.versionName+'.rpk',file=path.join(stage,'dist',name);
 if(!fs.existsSync(file))throw Error('Build did not produce RPK');
 if(JSON.stringify(sourceInputs(source))!==JSON.stringify(inputs))throw Error('Source changed during build');
 if(identity(sign).certificate_sha256!==signer.certificate_sha256)throw Error('Signing identity changed during build');
 fs.mkdirSync(out,{recursive:true});fs.copyFileSync(file,path.join(out,name),fs.constants.COPYFILE_EXCL);
 const report={artifact:name,bytes:fs.statSync(file).size,sha256:sha(fs.readFileSync(file)),package:manifest.package,
  version:manifest.versionName,versionCode:manifest.versionCode,signing_certificate_sha256:signer.certificate_sha256,
  signing_identity:signer,inputs,sourceFormat:true,installed:false,hardwareVerified:false,
  same_signature_update:false,old_app_data_automatically_migrated:false,
  backup_verification_required_before_old_app_uninstall:true,old_app_uninstalled:false,
  toolchain:'aiot-toolkit 2.0.5 / pinned package-lock / offline npm ci',
  protected_signing_replica_directories:replicas};
 fs.writeFileSync(path.join(out,'watch-build.json'),JSON.stringify(report,null,2),{flag:'wx'});
 console.log(JSON.stringify({artifact:path.join(out,name),bytes:report.bytes,sha256:report.sha256,
                            new_certificate_sha256:signer.certificate_sha256,same_signature_update:false}));
}
module.exports={identity,sourceInputs};if(require.main===module)main().catch(e=>{console.error(e.stack);process.exitCode=1;});
