// Selected legacy files share the root. Never delete a directory or an unselected prefix.
const hash=require('./ascii-sha256.js').hash,directory=require('./file-directory.js'),layout=require('./record-layout.js');
function canonical(value){
 if(value===null||typeof value==='string'||typeof value==='boolean')return JSON.stringify(value);
 if(typeof value==='number'&&isFinite(value))return JSON.stringify(value);
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
 if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
 throw Error('记录包含不支持的内容，未删除');
}
function create(o){
 const manifest=JSON.parse(JSON.stringify(o.manifest)),file=o.file;
 if(!manifest||manifest.schema!==1||!Array.isArray(manifest.targets)||manifest.targets.length<1||manifest.targets.length>256)throw Error('清理白名单无效');
 const basis=manifest.backup_basis||'pc_verified';
 if(['pc_verified','user_confirmed_export','unbacked_incomplete','selected_local_snapshot'].indexOf(basis)<0)throw Error('备份确认依据无效');
 const safe=s=>typeof s==='string'&&/^[A-Za-z0-9_-]{1,64}$/.test(s),hex=s=>typeof s==='string'&&/^[0-9a-f]{64}$/.test(s),seen={};
 const targets=manifest.targets.map(t=>{
  if(basis==='selected_local_snapshot'){
   if(!safe(t.native_sid)||!safe(t.sid)||['complete','partial','incomplete'].indexOf(t.source_state)<0||!Number.isSafeInteger(t.started_ms)||!t.file_sha256||typeof t.file_sha256!=='object')throw Error('所选记录身份无效');
   const loc=layout.location(t),dir=loc.dir,prefix='s5joint_'+t.sid+'_',expected={},keys=Object.keys(t.file_sha256),scope=dir+prefix;
   if(seen[scope])throw Error('重复选择记录');seen[scope]=true;
   if(keys.length<1||keys.length>3002||!hex(t.file_sha256[prefix+'head.json']))throw Error('没有可核对的会话头部');
   if(t.source_state==='incomplete'&&keys.indexOf(prefix+'tail.json')>=0)throw Error('未完成记录出现了封口');
   if(t.source_state!=='incomplete'&&!hex(t.file_sha256[prefix+'tail.json']))throw Error('已封口记录缺少封口');
   keys.forEach(name=>{const suffix=name.slice(prefix.length);if(name.indexOf(prefix)!==0||!(suffix==='head.json'||suffix==='tail.json'||/^b[0-9]{4}\.json$/.test(suffix))||!hex(t.file_sha256[name]))throw Error('所选目录含未知文件');expected[name]={kind:suffix==='head.json'?'owned_head':suffix==='tail.json'?'owned_tail':'block',sha:t.file_sha256[name]};});
   return {target:t,dir:dir,storage_layout:loc.storage_layout,expected:expected};
  }
  if(basis==='unbacked_incomplete'){
   if(!safe(t.native_sid)||!safe(t.sid)||t.incomplete!==true||t.backup_verified_on_pc!==false||t.backup_zip_sha256!==null||!t.file_sha256||typeof t.file_sha256!=='object')throw Error('失败记录身份无效');
   const dir='internal://files/s5joint_'+t.native_sid+'_'+t.sid+'/',prefix='s5joint_'+t.sid+'_',expected={};
   if(seen[dir])throw Error('重复清理身份');seen[dir]=true;
   const keys=Object.keys(t.file_sha256);if(keys.length<1||keys.length>3001||!hex(t.file_sha256[prefix+'head.json']))throw Error('缺少可核对的失败记录头部');
   keys.forEach(name=>{const suffix=name.slice(prefix.length);if(name.indexOf(prefix)!==0||!(suffix==='head.json'||/^b[0-9]{4}\.json$/.test(suffix))||!hex(t.file_sha256[name]))throw Error('失败记录含未知文件');expected[name]={kind:suffix==='head.json'?'failed_head':'block',sha:t.file_sha256[name]};});
   return {target:t,dir:dir,expected:expected};
  }
  const backed=basis==='pc_verified'?(t.backup_verified_on_pc===true&&hex(t.backup_zip_sha256)):(t.backup_verified_on_pc===false&&t.backup_confirmed_by_user===true&&t.backup_zip_sha256===null);
  if(!safe(t.native_sid)||!safe(t.sid)||!backed||!Array.isArray(t.block_sha256)||!t.block_sha256.length||t.block_sha256.length>3000||!t.block_sha256.every(hex))throw Error('备份未确认或身份无效');
  if(!t.end||t.end.p!=='J_END1'||t.end.native_sid!==t.native_sid||t.end.sid!==t.sid||t.end.blocks!==t.block_sha256.length||t.end.count!==t.rows)throw Error('备份封口不符');
  const dir='internal://files/s5joint_'+t.native_sid+'_'+t.sid+'/',prefix='s5joint_'+t.sid+'_';
  if(seen[dir])throw Error('重复清理身份');seen[dir]=true;
  const expected={};expected[prefix+'head.json']={kind:'head'};
  t.block_sha256.forEach((h,i)=>{expected[prefix+'b'+('0000'+i).slice(-4)+'.json']={kind:'block',sha:h};});
  expected[prefix+'tail.json']={kind:'tail',sha:hash(canonical(t.end))};
  return {target:t,dir:dir,expected:expected};
 });
 const expectedFiles=targets.reduce((n,t)=>n+Object.keys(t.expected).length,0);
 const later=o.setTimeout||setTimeout,clear=o.clearTimeout||clearTimeout;let busy=false,cancelled=false,phase='idle',error='',plan=null,token=null,files=0,checked=0,deleted=0,uncertain=false,serial=0,deleteRequests=0,verifiedAbsent=0,listingOmissions=0,lastInspection=null;
 function state(){return {phase:phase,error:error,files:files,expected_files:expectedFiles,missing_files:Math.max(0,expectedFiles-files),partial:files<expectedFiles,checked:checked,deleted:deleted,delete_requests:deleteRequests,delete_acknowledged:deleted,verified_absent_files:verifiedAbsent,listing_omission_observations:listingOmissions,last_inspection:lastInspection?JSON.parse(JSON.stringify(lastInspection)):null,uncertain:uncertain,token:token,busy:busy,sessions:targets.length,backup_basis:basis,complete_sessions:targets.filter(t=>t.target.source_state==='complete').length,partial_sessions:targets.filter(t=>t.target.source_state==='partial').length,incomplete_sessions:targets.filter(t=>t.target.source_state==='incomplete').length};}
 function notify(){if(o.onStatus)o.onStatus(state());}
 function check(){if(cancelled)throw Error('已取消；已完成的删除不会回滚');}
 function call(method,uri,options){return new Promise((resolve,reject)=>{
  let done=false;const timer=later(()=>{if(done)return;done=true;if(method==='delete')uncertain=true;reject(Error('本机文件操作超时；请保留当前结果'));},30000);
  function finish(err,result){if(done)return;done=true;clear(timer);err?reject(err):resolve(result);}
  try{if(!file||typeof file[method]!=='function')throw Error('文件接口不可用');if(method==='delete')deleteRequests++;file[method](Object.assign({},options,{uri:uri,success:v=>finish(null,v),fail:(m,c)=>{if(method==='delete')uncertain=true;const e=Error('文件操作失败 '+method+' '+m+' '+c);e.code=Number(c);e.uri=uri;e.method=method;finish(e);}}));}catch(e){finish(e);}
 });}
 function names(result,t){
  if(!result||!Array.isArray(result.fileList))throw Error('目录返回无效，未删除');
  const out=[],used={};result.fileList.forEach(entry=>{
   let name=entry&&typeof entry.uri==='string'?entry.uri:entry&&entry.name;
   if(typeof name!=='string')throw Error('目录条目无效');
   if(name.indexOf('internal://files//')===0)name='internal://files/'+name.slice('internal://files//'.length);
   if(name.indexOf(t.dir)===0){name=name.slice(t.dir.length);if(name.charAt(0)==='/')name=name.slice(1);}
   if(t.storage_layout==='legacy_flat'&&name.indexOf('s5joint_'+t.target.sid+'_')!==0)return;
   if(!/^[A-Za-z0-9_.-]+$/.test(name)||!Object.prototype.hasOwnProperty.call(t.expected,name))throw Error('目录含未核验文件，已停止');
   if(!used[name]){used[name]=true;out.push(name);}
  });return out.sort();
 }
 function validate(text,t,name){
  if(typeof text!=='string'||text.length>32768)throw Error('记录内容无效或超限');
  const expected=t.expected[name];
  if(expected.kind==='owned_head'){
   const v=JSON.parse(text);
   if(hash(text)!==expected.sha||!layout.owned(v,{native_sid:t.target.native_sid,sid:t.target.sid,dir:t.dir,storage_layout:t.storage_layout})||v.started_epoch_ms!==t.target.started_ms)throw Error('会话头部改变，未删除');
  }
  else if(expected.kind==='owned_tail'){if(hash(text)!==expected.sha)throw Error('会话封口改变，未删除');}
  else if(expected.kind==='failed_head'){
   const v=JSON.parse(text);
   if(hash(text)!==expected.sha||v.kind!=='head'||v.schema_version!==1||v.native_sid!==t.target.native_sid||v.sid!==t.target.sid||v.storage_root_uri!==t.dir||v.storage_strategy!=='isolated_session_directory')throw Error('失败记录头部改变，未删除');
  }
  else if(expected.kind==='block'){if(hash(text)!==expected.sha)throw Error(basis==='pc_verified'?'本地块与历史备份清单SHA不同，已停止':'本地块在核对期间改变，已停止');}
  else if(expected.kind==='tail'){if(hash(canonical(JSON.parse(text)))!==expected.sha)throw Error('本地封口与核对内容不同，已停止');}
  else{
   const v=JSON.parse(text),keys=['kind','schema_version','sid','native_sid','started_epoch_ms','requested_duration_ms','app_version','storage_strategy','storage_root_uri','sensor_path','requested_interval','acceleration_unit','axis_convention','hardware_timestamp','wrist'];
   if(Object.keys(v).sort().join('|')!==keys.sort().join('|')||v.kind!=='head'||v.schema_version!==1||v.native_sid!==t.target.native_sid||v.sid!==t.target.sid||v.started_epoch_ms!==t.target.end.start_ms||v.storage_root_uri!==t.dir||v.storage_strategy!=='isolated_session_directory'||v.sensor_path!=='generic'||v.requested_interval!=='high'||v.acceleration_unit!=='unknown'||v.axis_convention!=='unverified'||v.hardware_timestamp!==false||v.wrist!=='not_recorded'||typeof v.app_version!=='string'||[20000,60000,120000,300000,600000].indexOf(v.requested_duration_ms)<0)throw Error('本地头部身份不符，未删除');
  }
  return hash(text);
 }
 function inspect(){
  const items=[];let ti=0;
  function nextTarget(){check();if(ti>=targets.length)return Promise.resolve(items);const t=targets[ti++];
   return directory.read(call,file,t.dir,{preferRootFiles:true,preferList:t.storage_layout==='legacy_flat'}).then(v=>{check();const listed=names(v,t),expected=Object.keys(t.expected).sort(),omitted=expected.filter(n=>listed.indexOf(n)<0),list=basis==='selected_local_snapshot'?expected:listed;let ni=0;
    lastInspection={phase:phase,session_index:ti,sessions:targets.length,sid:t.target.sid,expected_files:expected.length,listed_files:listed.length,omitted_from_listing:omitted.length,omitted_examples:omitted.slice(0,3).map(n=>n.slice(('s5joint_'+t.target.sid+'_').length)),missing_file:null,read_error_code:null};
    if(basis==='selected_local_snapshot')listingOmissions+=omitted.length;
    function nextFile(){check();if(ni>=list.length)return nextTarget();const name=list[ni++];
     return call('readText',t.dir+name).catch(e=>{check();lastInspection.missing_file=name.slice(('s5joint_'+t.target.sid+'_').length);lastInspection.read_error_code=Number.isFinite(e.code)?e.code:null;if(e.code===301){const missing=Error('第'+ti+'条缺少'+lastInspection.missing_file+'；已停止，请返回记录重新核对');missing.code=301;throw missing;}throw e;}).then(v=>{check();const digest=validate(v&&v.text,t,name);items.push({uri:t.dir+name,sha:digest,kind:t.expected[name].kind});checked++;if(checked%20===0)notify();return nextFile();});
    }return nextFile();
   });
  }return nextTarget();
 }
 // A successful native delete callback is an acknowledgement. Confirm absence separately.
 function verifySelectionAbsent(){
  let ti=0;verifiedAbsent=0;
  function nextTarget(){
   check();if(ti>=targets.length)return Promise.resolve();const t=targets[ti++],expected=Object.keys(t.expected).sort();
   return directory.read(call,file,t.dir,{preferRootFiles:true,preferList:t.storage_layout==='legacy_flat'}).then(v=>{
    check();const listed=names(v,t);lastInspection={phase:phase,session_index:ti,sessions:targets.length,sid:t.target.sid,expected_files:expected.length,listed_files:listed.length,omitted_from_listing:expected.length-listed.length,omitted_examples:[],missing_file:null,read_error_code:null};let ni=0;
    function nextFile(){
     check();if(ni>=expected.length)return nextTarget();const name=expected[ni++];
     return call('readText',t.dir+name).then(()=>{check();uncertain=true;throw Error('删除后仍可读取第'+ti+'条的'+name.slice(('s5joint_'+t.target.sid+'_').length)+'；结果未确认，已停止');},e=>{
      check();if(e.code!==301){uncertain=true;lastInspection.read_error_code=Number.isFinite(e.code)?e.code:null;throw e;}
      verifiedAbsent++;checked++;if(verifiedAbsent%20===0)notify();return nextFile();
     });
    }return nextFile();
   });
  }return nextTarget().catch(e=>{uncertain=true;throw e;});
 }
 function signature(items){return hash(items.map(v=>v.uri+' '+v.sha).sort().join('\n'));}
 function finishError(e){phase=cancelled?'cancelled':'error';error=String(e&&e.message||e);busy=false;token=null;notify();throw e;}
 function prepare(){
  if(busy)return Promise.reject(Error('操作尚未结束'));busy=true;cancelled=false;phase='checking';error='';checked=0;files=0;token=null;plan=null;deleted=0;deleteRequests=0;verifiedAbsent=0;listingOmissions=0;lastInspection=null;uncertain=false;notify();
  return inspect().then(items=>{check();plan=items;files=items.length;token=items.length?'checked_'+(++serial)+'_'+signature(items):null;phase=items.length?'ready':'complete';busy=false;notify();return state();}).catch(finishError);
 }
 function purge(confirmation){
  const c=confirmation;
  if(busy||phase!=='ready'||!token||!plan||!c||c.token!==token||c.confirmPermanent!==true)return Promise.reject(Error('请先核对并确认永久清理范围'));
  if(basis==='selected_local_snapshot'){
   const complete=targets.some(t=>t.target.source_state==='complete'),partial=targets.some(t=>t.target.source_state==='partial'),unfinished=targets.some(t=>t.target.source_state==='incomplete');
   if(complete&&c.confirmBackup!==true)return Promise.reject(Error('请确认需要保留的完整记录已导出'));
   if((partial||unfinished)&&c.confirmUnbackedLoss!==true)return Promise.reject(Error('请确认接受不完整记录的剩余内容永久丢失'));
   if(partial&&c.confirmPartial!==true)return Promise.reject(Error('请确认清理缺块记录的剩余文件'));
   if(unfinished&&c.confirmFailedRecord!==true)return Promise.reject(Error('请确认丢弃未完成记录'));
  }else if(basis==='unbacked_incomplete'){
   if(c.confirmUnbackedLoss!==true||c.confirmFailedRecord!==true) return Promise.reject(Error('必须明确确认：这条失败记录没有备份，删除不可恢复'));
  }else{
   if(c.confirmBackup!==true||(basis==='pc_verified'&&c.confirmCurrentBackup!==true))return Promise.reject(Error('请当次确认电脑仍保留这条导出包；手表不能检查电脑'));
  }
  if(files<expectedFiles&&c.confirmPartial!==true)return Promise.reject(Error('本地文件部分缺失，需要单独确认只清理剩余文件'));
  busy=true;cancelled=false;phase='rechecking';checked=0;notify();const approved=signature(plan);token=null;
  return inspect().then(current=>{
   check();if(signature(current)!==approved)throw Error('记录已改变，请重新核对；未删除');
   const order=k=>k==='block'?0:k==='head'||k==='failed_head'||k==='owned_head'?1:2;
   const ordered=current.slice().sort((a,b)=>order(a.kind)-order(b.kind));let at=0;phase='deleting';notify();
   function next(){check();if(at>=ordered.length)return Promise.resolve();const item=ordered[at++];
    return call('readText',item.uri).then(v=>{check();if(!v||hash(v.text)!==item.sha)throw Error('删除前内容变化，已停止');return call('delete',item.uri);}).then(()=>{deleted++;if(deleted%10===0)notify();return next();});
   }return next();
  }).then(()=>{check();phase='verifying';checked=0;notify();return basis==='selected_local_snapshot'?verifySelectionAbsent():inspect();}).then(remaining=>{
   if(basis!=='selected_local_snapshot'&&remaining.length)throw Error('仍有文件，未宣称清理完成');phase='complete';busy=false;plan=null;notify();return state();
  }).catch(finishError);
 }
 function cancel(){cancelled=true;token=null;plan=null;if(!busy&&phase!=='complete'){phase='cancelled';error='操作已中断，需要重新核对';}notify();}
 function suspend(){
  if(busy||phase!=='ready'||!plan){cancel();return state();}
  token=null;phase='paused';notify();return state();
 }
 function resume(){
  if(phase==='paused'&&plan){cancelled=false;token='checked_'+(++serial)+'_'+signature(plan);phase='ready';notify();}
  return state();
 }
 function prepareFromSnapshot(){
  if(basis!=='selected_local_snapshot'||busy||phase!=='idle')return Promise.reject(Error('只能使用刚生成的所选文件快照'));
  cancelled=false;plan=[];targets.forEach(t=>Object.keys(t.expected).sort().forEach(name=>plan.push({uri:t.dir+name,sha:t.expected[name].sha,kind:t.expected[name].kind})));
  files=plan.length;checked=files;token='checked_'+(++serial)+'_'+signature(plan);phase='ready';notify();
  // Purge still rereads and validates every owned head/hash before any deletion.
  return Promise.resolve(state());
 }
 return {prepare:prepare,prepareFromSnapshot:prepareFromSnapshot,purge:purge,state:state,cancel:cancel,suspend:suspend,resume:resume};
}
module.exports={create:create,canonical:canonical};
