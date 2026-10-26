// Ordinary deletion validates identity and exact paths, not payload integrity.
// Native delete acknowledgements are never reported as independently read-back absence.
const records=require('./records.js'),catalog=require('./catalog-index.js'),cache=require('./view-cache.js');
const layout=require('./record-layout.js'),hash=require('./ascii-sha256.js').hash;
const directory=require('./file-directory.js');
function create(o){
 const file=o.file,later=o.setTimeout||setTimeout,clear=o.clearTimeout||clearTimeout;
 const core=records.create({file:file,recoveryDirectories:o.recoveryDirectories,setTimeout:later,clearTimeout:clear});
 let generation=0,busy=false,inflight=0,halted=false,phase='idle',error='',uncertain=false;
 let plans=[],token=null,preparedId=null,files=0,requests=0,ack=0,absent=0,removed=[],forgotten=[],at=0;
 let directoryDiagnostic={list_entries:null,get_entries:null,source:null,reason:null};
 const identify=r=>r[2]==='f'?'flat:'+r[1]:'s5joint_'+r[0]+'_'+r[1];
 function state(){return {phase:phase,busy:busy||inflight>0,error:error,uncertain:uncertain,
  files:files,expected_files:files,checked:at,deleted:ack,delete_requests:requests,delete_acknowledged:ack,
  already_absent_files:absent,verified_absent_files:0,verification_mode:'system_acknowledgement_only',
  content_verified:false,token:token,prepared_id:preparedId,sessions:plans.length,
  complete_sessions:0,sealed_sessions:plans.filter(p=>p.sealed).length,partial_sessions:0,
  incomplete_sessions:plans.filter(p=>!p.sealed).length,removed_ids:removed.slice(),
  retained_full_file_records:0,retained_signature_records:plans.length,directory_diagnostic:Object.assign({},directoryDiagnostic)};}
 function notify(){if(o.onStatus)o.onStatus(state());}
 function check(g){if(g!==generation)throw Error('页面或选择已改变，操作已停止');}
 function begin(){
  if(busy||inflight||core.state().busy)throw Error('文件操作尚未结束');
  if(halted)throw Error('上个文件请求未确认，请返回首页后重新进入');
  generation++;token=null;preparedId=null;phase='idle';error='';uncertain=false;return generation;
 }
 function failure(e,g){if(g===generation){busy=false;phase='error';error=String(e.message||e);token=null;preparedId=null;notify();}throw e;}
 function call(method,uri,options){return new Promise((resolve,reject)=>{
  if(halted){reject(Error('文件请求未确认，请退出此页'));return;}
  let done=false;inflight++;
  const timer=later(()=>{halted=true;if(method==='delete')uncertain=true;finish(Error('本机文件操作超时；请保留当前结果'));},30000);
  function finish(e,v){if(done)return;done=true;clear(timer);inflight--;e?reject(e):resolve(v);}
  try{file[method](Object.assign({},options||{},{uri:uri,complete:function(){},success:v=>finish(null,v),fail:(m,c)=>{
   const e=Error('文件操作失败 '+method+' '+m+' '+c);e.code=Number(c);
   if(e.code===-2)halted=true;if(method==='delete'&&e.code!==301)uncertain=true;finish(e);
  }}));}catch(e){if(method==='delete')uncertain=true;finish(e);}
 });}
 function refs(){return core.catalogHints().filter(r=>forgotten.indexOf(identify(r))<0);}
 function ownedEntry(id){const matches=refs().filter(r=>identify(r)===id);if(matches.length!==1)throw Error('只能删除当前列表中所选的本应用记录');
  const r=matches[0];return Object.assign({id:id},layout.location({native_sid:r[0],sid:r[1],storage_layout:r[2]==='f'?'legacy_flat':'isolated_session_directory'}));}
 function read(uri){return call('readText',uri).then(v=>{if(!v||typeof v.text!=='string'||v.text.length>32768)throw Error('记录元信息无效，保留此条');return {text:v.text,value:JSON.parse(v.text)};});}
 function metadata(e,g){
  const prefix=e.dir+'s5joint_'+e.sid+'_';let head;
  return read(prefix+'head.json').then(h=>{
   check(g);if(!layout.owned(h.value,e))throw Error('记录头部身份不符，未删除');head=h;
   return read(prefix+'tail.json').catch(err=>{check(g);if(err.code!==301)throw err;return null;});
  }).then(t=>{
   check(g);if(t){const v=t.value;if(v.p!=='J_END1'||v.native_sid!==e.native_sid||v.sid!==e.sid||!Number.isInteger(v.count)||v.count<1||v.count>20000||!Number.isInteger(v.blocks)||v.blocks<1||v.blocks>3000||!Number.isSafeInteger(v.start_ms)||!Number.isSafeInteger(v.stop_ms)||v.stop_ms<v.start_ms||v.start_ms!==head.value.started_epoch_ms)throw Error('封口身份或范围改变，未删除');}
   return {headHash:hash(head.text),tailHash:t?hash(t.text):null,sealed:!!t,blocks:t?t.value.blocks:null};
  });
 }
 function scopeError(){const err=Error('目录返回路径范围不一致，未删除');err.directoryScopeMismatch=true;return err;}
 function listingUnconfirmed(reason){const err=Error('目录名单未确认（'+reason+'），保留此条');err.directoryListingUnconfirmed=true;directoryDiagnostic.reason=reason;return err;}
 function selectedNames(e,v){
  if(!v||!Array.isArray(v.fileList)||v.fileList.length>(e.storage_layout==='legacy_flat'?20000:6004))throw Error('未完成记录目录无效，保留此条');
  const prefix='s5joint_'+e.sid+'_',base=directory.relative(e.dir),out=[],seen={};
  v.fileList.forEach(item=>{
   const raw=item&&typeof item.uri==='string'?item.uri:item&&item.name;
   if(typeof raw!=='string')throw Error('目录路径无效');
   const relative=directory.relative(raw);if(relative===null)throw scopeError();let name=relative;
   if(e.storage_layout==='legacy_flat'){if(name.indexOf(prefix)!==0)return;}
   else if(name.indexOf(base)===0)name=name.slice(base.length);
   else if(name.indexOf('/')>=0||raw.indexOf('://')>=0)throw scopeError();
   if(!name)throw scopeError();
   if(name.indexOf(prefix)!==0||!(/^(head|tail|b[0-9]{4})\.json$/.test(name.slice(prefix.length))))throw Error('目录含未知或其他记录路径，未删除');
   if(!seen[name]){seen[name]=true;out.push(name);}
  });
  if(out.length>3002)throw Error('目录文件数超限，保留此条');
  if(out.indexOf(prefix+'tail.json')>=0)throw Error('目录出现封口文件，请刷新后重新选择');
  if(!out.length)throw listingUnconfirmed('返回空名单');
  if(out.indexOf(prefix+'head.json')<0)throw listingUnconfirmed('未列出头文件');
  return out.sort();
 }
 function listNames(e,g){directoryDiagnostic={list_entries:null,get_entries:null,source:'list',reason:null};return call('list',e.dir).then(v=>{check(g);directoryDiagnostic.list_entries=v&&Array.isArray(v.fileList)?v.fileList.length:null;return selectedNames(e,v);}).catch(err=>{
  check(g);if((!err.directoryScopeMismatch&&!err.directoryListingUnconfirmed)||e.storage_layout==='legacy_flat'||typeof file.get!=='function')throw err;
  // Some native list implementations return root-relative or parent entries.
  // Re-read the exact selected directory; never turn another URI into a basename.
  return call('get',e.dir,{recursive:true}).then(v=>{
   check(g);if(!v||v.type!=='dir'||!Array.isArray(v.subFiles))throw scopeError();
   directoryDiagnostic.get_entries=v.subFiles.length;directoryDiagnostic.source='get';
   if(typeof v.uri==='string'&&directory.relative(v.uri)!==directory.relative(e.dir))throw scopeError();
   return selectedNames(e,{fileList:v.subFiles});
  });
 }).catch(err=>{if(err.directoryListingUnconfirmed)err.message+=' L'+directoryDiagnostic.list_entries+'/G'+directoryDiagnostic.get_entries;throw err;});}
 function same(p,m){if(p.headHash!==m.headHash||p.tailHash!==m.tailHash||p.sealed!==m.sealed||p.blocks!==m.blocks)throw Error('所选记录身份或封口已改变，未删除');}
 function scan(){let g;try{g=begin();}catch(e){return Promise.reject(e);}busy=true;phase='reading';plans=[];files=0;
  return catalog.load(file).then(v=>{if(!v.ok)throw Error('记录索引读取未确认，请返回首页后重新进入');return cache.load(file).then(saved=>{if(saved.revision===null)throw Error('记录缓存读取未确认，请返回首页后重新进入');return catalog.merge([catalog.fromDirectories(o.recoveryDirectories),v.hints,saved.hints||[]]);});}).then(hints=>{check(g);return core.restore(hints);}).then(rows=>{check(g);busy=false;phase='idle';return rows.filter(r=>forgotten.indexOf(r.id)<0);}).catch(e=>failure(e,g));
 }
 function prepareSelection(ids){let g,entries;try{g=begin();if(!Array.isArray(ids)||!ids.length||ids.length>256||new Set(ids).size!==ids.length)throw Error('所选记录为空、重复或超限');entries=ids.slice().sort().map(ownedEntry);}catch(e){return Promise.reject(e);}
  busy=true;phase='checking_identity';plans=[];files=0;removed=[];requests=0;ack=0;absent=0;at=0;
  function next(){check(g);if(at>=entries.length){preparedId=entries.map(e=>e.id).join('|');token='identity_'+g+'_'+hash(plans.map(p=>p.entry.id+' '+p.headHash+' '+p.tailHash).join('\n'));phase='ready';busy=false;notify();return state();}
   const e=entries[at++];return metadata(e,g).then(m=>{
    const p=Object.assign({entry:e,namesHash:null},m);
    return (m.sealed?Promise.resolve(m.blocks+2):listNames(e,g).then(names=>{p.namesHash=hash(names.join('\n'));return names.length;})).then(n=>{check(g);p.files=n;plans.push(p);files+=n;notify();return next();});
   });}
  return Promise.resolve().then(next).catch(e=>failure(e,g));
 }
 function paths(p,g){const prefix='s5joint_'+p.entry.sid+'_';if(p.sealed){const names=[];for(let i=0;i<p.blocks;i++)names.push(prefix+'b'+('0000'+i).slice(-4)+'.json');return Promise.resolve(names.concat([prefix+'tail.json',prefix+'head.json']));}
  return listNames(p.entry,g).then(names=>{if(hash(names.join('\n'))!==p.namesHash)throw Error('未完成记录的文件名单已改变，未删除');return names.filter(n=>n!==prefix+'head.json').concat([prefix+'head.json']);});
 }
 function purge(c){
  if(busy||phase!=='ready'||!c||!token||c.token!==token||c.preparedId!==preparedId||c.confirmPermanent!==true)return Promise.reject(Error('请先选择并确认永久删除'));
  if(plans.some(p=>p.sealed)&&c.confirmBackup!==true)return Promise.reject(Error('请确认所需导出已保留'));
  if(plans.some(p=>!p.sealed)&&(c.confirmUnbackedLoss!==true||c.confirmFailedRecord!==true))return Promise.reject(Error('请确认未完成内容永久丢失'));
  const g=generation;token=null;busy=true;phase='checking_identity';at=0;
  function validateAll(){check(g);if(at>=plans.length)return Promise.resolve();const p=plans[at++];return metadata(p.entry,g).then(m=>{check(g);same(p,m);notify();return validateAll();});}
  function deleteNext(){check(g);if(at>=plans.length){phase='complete';busy=false;notify();return state();}const p=plans[at++];
   return metadata(p.entry,g).then(m=>{check(g);same(p,m);return paths(p,g);}).then(names=>{let ni=0;function next(){check(g);if(ni>=names.length){removed.push(p.entry.id);notify();return deleteNext();}const name=names[ni++];requests++;
    return call('delete',p.entry.dir+name).then(()=>{check(g);ack++;},e=>{check(g);if(e.code!==301)throw e;absent++;}).then(()=>{if((ack+absent)%20===0)notify();return next();});
   }return next();});
  }
  return validateAll().then(()=>{check(g);at=0;phase='deleting';notify();return deleteNext();}).catch(e=>failure(e,g));
 }
 function cancel(){if(inflight&&phase==='deleting')uncertain=true;generation++;token=null;preparedId=null;busy=false;core.cancel();if(phase!=='complete')phase='cancelled';}
 return {scan:scan,summary:id=>core.preview(id),releaseInventories:()=>core.releaseInventories(),catalogHints:refs,
  discovery:()=>Object.assign({},core.discovery(),{scope:'known_identity_paths',unregistered_orphans_not_fully_enumerated:true}),
  prepareSelection:prepareSelection,purge:purge,state:state,cancel:cancel,
  forgetDeleted:ids=>{if(phase!=='complete'||ids.slice().sort().join('|')!==removed.slice().sort().join('|'))throw Error('系统删除回执未完成');forgotten=forgotten.concat(ids);}};
}
module.exports={create:create};
