const crypto=require('node:crypto'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const sha=s=>crypto.createHash('sha256').update(s,'ascii').digest('hex');
function fixture(){
 const files=new Map(),targets=[];
 for(let n=1;n<=2;n++){
  const native='00000000-0000-4000-8000-00000000000'+n,sid='j_'+n;
  const dir='internal://files/s5joint_'+native+'_'+sid+'/',prefix='s5joint_'+sid+'_';
  const head={kind:'head',schema_version:1,sid,native_sid:native,started_epoch_ms:100,requested_duration_ms:120000,app_version:'0.2.5',storage_strategy:'isolated_session_directory',storage_root_uri:dir,sensor_path:'generic',requested_interval:'high',acceleration_unit:'unknown',axis_convention:'unverified',hardware_timestamp:false,wrist:'not_recorded'};
  const block=JSON.stringify([[0,100,1,2,3],[1,160,2,3,4]]),end={p:'J_END1',sid,native_sid:native,count:2,blocks:1,start_ms:100,stop_ms:1000,clock_observations:1,stop_reason:'duration'};
  files.set(dir+prefix+'head.json',JSON.stringify(head));files.set(dir+prefix+'b0000.json',block);files.set(dir+prefix+'tail.json',JSON.stringify(end));
  targets.push({card:n,native_sid:native,sid,backup_zip_sha256:String(n).repeat(64),backup_verified_on_pc:true,rows:2,block_sha256:[sha(block)],end});
 }
 files.set('internal://files/unrelated.json','keep');
 files.set('internal://files/s5catalog_v2.json',JSON.stringify({schema:2,hints:targets.map(t=>[t.native_sid,t.sid,'i'])}));
 const calls={list:[],read:[],delete:[],awake:[]};
 const file={list(o){calls.list.push(o.uri);if(o.uri==='internal://files/'){
  const dirs=[...new Set([...files.keys()].filter(u=>u.startsWith(o.uri+'s5joint_')).map(u=>u.slice(o.uri.length).split('/')[0]))];o.success({fileList:dirs.map(name=>({uri:o.uri+name+'/'}))});
 }else{o.success({fileList:[...files.keys()].filter(u=>u.startsWith(o.uri)).map(uri=>({uri}))});}},
 readText(o){calls.read.push(o.uri);files.has(o.uri)?o.success({text:files.get(o.uri)}):o.fail('missing',301);},
 delete(o){calls.delete.push(o.uri);files.delete(o.uri);o.success({});}};
 return {files,targets,calls,file,dir:n=>'internal://files/s5joint_'+targets[n].native_sid+'_'+targets[n].sid+'/',prefix:n=>'s5joint_'+targets[n].sid+'_'};
}
function page(kind,f,manifest){
 const raw=fs.readFileSync(path.join(__dirname,'../src',kind,'index.ux'),'utf8');
 const script=raw.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .+$/gm,'').replace('export default','module.exports=');
 const sandbox={module:{exports:{}},require:n=>n.includes('backup-allowlist')?manifest:require(path.join(__dirname,'../src',kind,n)),file:f.file,brightness:f.brightness||{setKeepScreenOn(o){f.calls.awake.push(o.keepScreenOn);if(o.success)o.success();}},router:{replace(){},push(){}},Date,Promise,setTimeout,clearTimeout};
 vm.runInNewContext(script,sandbox);const spec=sandbox.module.exports,p=Object.assign({},spec,JSON.parse(JSON.stringify(spec.data)));p.onInit();return p;
}
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(r=>setTimeout(r,1));};
module.exports={fixture,page,sha,settle};
