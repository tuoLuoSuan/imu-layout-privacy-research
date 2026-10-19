const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),repo=path.resolve(root,'../..'),sha=b=>crypto.createHash('sha256').update(b).digest('hex');
async function main(){
 const out=path.resolve(process.argv[2]);if(!out.startsWith(path.join(root,'dist')+path.sep)||fs.existsSync(out))throw Error('Fresh suite dist output required');
 const base=path.join(repo,'collection/watch-s5-probe'),modules=fs.existsSync(path.join(base,'node_modules/aiot-toolkit'))?path.join(base,'node_modules'):path.join(repo,'collection/band9pro-probe/node_modules');
 const sign=fs.existsSync(path.join(base,'sign/private.pem'))?path.join(base,'sign'):path.join(repo,'collection/band9pro-probe/sign');
 const stage=fs.mkdtempSync(path.join(fs.realpathSync(os.tmpdir()),'imu-suite-watch-'));fs.cpSync(path.join(root,'watch/src'),path.join(stage,'src'),{recursive:true});
 fs.mkdirSync(path.join(stage,'sign'));for(const n of['private.pem','certificate.pem'])fs.copyFileSync(path.join(sign,n),path.join(stage,'sign',n));fs.symlinkSync(modules,path.join(stage,'node_modules'),'junction');
 const ownKey=path.join(stage,'sign/private.pem'),manifest=JSON.parse(fs.readFileSync(path.join(stage,'src/manifest.json'),'utf8'));
 try{const Builder=require(path.join(modules,'aiot-toolkit/lib/builder/VelaUxBuilder')).default;await new Builder().build(stage,{mode:'production',enableJsc:false,enableProtobuf:false});
  const name=manifest.package+'.release.'+manifest.versionName+'.rpk',file=path.join(stage,'dist',name);if(!fs.existsSync(file))throw Error('RPK missing');fs.mkdirSync(out,{recursive:true});fs.copyFileSync(file,path.join(out,name),fs.constants.COPYFILE_EXCL);
  const inputs={};function visit(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())visit(p);else inputs[path.relative(path.join(stage,'src'),p).replace(/\\/g,'/')]=sha(fs.readFileSync(p));}}visit(path.join(stage,'src'));
  fs.writeFileSync(path.join(out,'watch-build.json'),JSON.stringify({artifact:name,bytes:fs.statSync(file).size,sha256:sha(fs.readFileSync(file)),package:manifest.package,version:manifest.versionName,inputs,sourceFormat:true,installed:false,hardwareVerified:false},null,2),{flag:'wx'});
 }finally{if(path.dirname(ownKey)!==path.join(stage,'sign'))throw Error('key boundary');if(fs.existsSync(ownKey))fs.unlinkSync(ownKey);}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
