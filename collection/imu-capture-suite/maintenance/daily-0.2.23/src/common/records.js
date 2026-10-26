// Daily single-record management. External backup is explicitly user-confirmed.
const cleanup=require('./cleanup.js'),directory=require('./file-directory.js'),layout=require('./record-layout.js'),index=require('./session-index.js'),hash=require('./ascii-sha256.js').hash,ROOT='internal://files/';
function create(o){
 const file=o.file,later=o.setTimeout||setTimeout,clear=o.clearTimeout||clearTimeout;let catalog=[],generation=0,child=null,preparedId=null;
 let discovery={},rootFilesObserved=false;
 function call(method,uri,options){return new Promise((resolve,reject)=>{
  let done=false;const timer=later(()=>{if(!done){done=true;reject(Error('目录或记录读取超时；保留原状'));}},method==='get'&&uri===ROOT?8000:30000);
  function end(e,v){if(done)return;done=true;clear(timer);e?reject(e):resolve(v);}
  try{file[method](Object.assign({},options,{uri:uri,success:v=>end(null,v),fail:(m,c)=>{const e=Error('记录读取失败 '+method+' '+m+' '+c);e.code=Number(c);end(e);}}));}catch(e){end(e);}
 });}
 function active(){if(child&&child.state().busy)throw Error('清理操作尚未结束');}
 function check(g){if(g!==generation)throw Error('页面或选择已改变，已停止');}
 function begin(){active();const g=++generation;preparedId=null;if(child)child.cancel();child=null;return g;}
 function entry(id){const found=catalog.filter(x=>x.id===id);if(found.length!==1)throw Error('只允许选择刚扫描出的本应用记录');return found[0];}
 function readObject(uri){return call('readText',uri).then(v=>{if(!v||typeof v.text!=='string'||v.text.length>32768)throw Error('记录文件无效');return JSON.parse(v.text);});}
 function selectNames(e,result){
   if(!result||!Array.isArray(result.fileList)||result.fileList.length>(e.storage_layout==='legacy_flat'?20000:6004))throw Error('会话目录无效或过大');
   const prefix='s5joint_'+e.sid+'_',names=[],seen={};
   result.fileList.forEach(v=>{
    let name=v&&typeof v.uri==='string'?v.uri:v&&v.name;
    if(typeof name!=='string')throw Error('会话目录条目无效');
    if(name.indexOf('internal://files//')===0)name='internal://files/'+name.slice('internal://files//'.length);
    if(name.indexOf(e.dir)===0){name=name.slice(e.dir.length);if(name.charAt(0)==='/')name=name.slice(1);}
    if(e.storage_layout==='legacy_flat'&&name.indexOf(prefix)!==0)return;
    const tail=name.slice(prefix.length);
    if(name.indexOf(prefix)!==0||!(tail==='head.json'||tail==='tail.json'||/^b[0-9]{4}\.json$/.test(tail)))throw Error('目录含未知文件；保留原状');
    if(!seen[name]){seen[name]=true;names.push(name);}
   });if(names.length>3002)throw Error('会话文件过多，保留原状');return names.sort();
 }
 function localNames(e,g,preview){
  if(preview&&e.scanListing){check(g);return Promise.resolve().then(()=>selectNames(e,e.scanListing));}
  return directory.read(call,file,e.dir,{preferRootFiles:true,preferList:e.storage_layout==='legacy_flat'}).then(result=>{check(g);return selectNames(e,result);});
 }
 function failedMeta(e,g,previewNames){
  return (previewNames?Promise.resolve(previewNames):localNames(e,g)).then(names=>{
   const prefix='s5joint_'+e.sid+'_';
   if(names.indexOf(prefix+'tail.json')>=0)throw Error('这条已有封口，不允许按无备份失败记录删除');
   if(names.indexOf(prefix+'head.json')<0)throw Error('没有可验证的会话头部，保留原状');
   return readObject(e.dir+prefix+'head.json').then(head=>{
    check(g);if(!layout.owned(head,e))throw Error('失败记录头部身份不符，保留原状');
    return {names:names,head:head};
   });
  });
 }
 function meta(e,g){
  const prefix=e.dir+'s5joint_'+e.sid+'_';let head;
  return readObject(prefix+'head.json').then(v=>{check(g);head=v;return readObject(prefix+'tail.json');}).then(end=>{
   check(g);
   if(!layout.owned(head,e)||end.p!=='J_END1'||end.native_sid!==e.native_sid||end.sid!==e.sid||!Number.isInteger(end.count)||end.count<1||end.count>20000||!Number.isInteger(end.blocks)||end.blocks<1||end.blocks>3000||!Number.isSafeInteger(end.start_ms)||!Number.isSafeInteger(end.stop_ms)||end.stop_ms<end.start_ms||head.started_epoch_ms!==end.start_ms)throw Error('本地记录未封口或身份不一致，先保留');
   return {entry:e,head:head,end:end,prefix:prefix};
  });
 }
 function scan(options){
  let g;try{g=begin();}catch(e){return Promise.reject(e);}
  catalog=[];discovery={list_entries:0,get_entries:0,recursive_entries:0,candidates:0,records:0,flat_records:0,empty_dirs:0,unreadable_dirs:0,known_found:0,known_missing:0,known_absent:0,known_errors:[],root_error:'',get_error:'',examples:[],warning:''};
  const out=[],seen={},kept=[],locators=[];let rootOK=false,rootListing=null;
  function add(raw,hint){
   const r=directory.relative(raw);if(r===null)return null;
   const flat=/^s5joint_([A-Za-z0-9_-]{1,64})_(head|tail|b[0-9]{4})\.json$/.exec(r);
   if(flat&&!hint){const id='flat:'+flat[1];if(seen[id])return seen[id];if(out.length>=256)throw Error('会话超过256条，保留原状');const e={id:id,native_sid:null,sid:flat[1],dir:ROOT,storage_layout:'legacy_flat',hint:false};seen[id]=e;out.push(e);return e;}
   const id=r.split('/')[0];
   if(!/^s5joint_[A-Za-z0-9_-]{3,129}$/.test(id))return null;
   if(hint&&r!==id+'/')return null;
   if(seen[id])return seen[id];if(out.length>=256)throw Error('会话超过256条，保留原状');
   const m=/^s5joint_([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})_([A-Za-z0-9_-]{1,64})$/.exec(id);
   const e={id:id,native_sid:m?m[1]:null,sid:m?m[2]:null,dir:ROOT+id+'/',hint:!!hint};seen[id]=e;out.push(e);return e;
  }
  function consume(result){check(g);result.fileList.forEach(v=>{const raw=v&&typeof v.uri==='string'?v.uri:v&&v.name,r=directory.relative(raw);if(r&&/^s5loc_[A-Za-z0-9_-]+\.json$/.test(r)&&locators.indexOf(ROOT+r)<0){if(locators.length>=256)throw Error('记录定位文件超过安全上限');locators.push(ROOT+r);}if(discovery.examples.length<2)discovery.examples.push(String(raw).slice(0,110));add(raw,false);});}
  function readLocators(){let at=0;discovery.locators=locators.length;discovery.invalid_locators=0;
   function next(){check(g);if(at>=locators.length)return Promise.resolve();const path=locators[at++];return readObject(path).then(v=>{check(g);const ref=index.decode(path,v);if(!ref){discovery.invalid_locators++;return;}const e=add(ref.dir,true);if(e){e.native_sid=ref.native_sid;e.sid=ref.sid;}},()=>{check(g);discovery.invalid_locators++;}).then(next);}return next();
  }
  function owned(head,e){return layout.owned(head,e)&&(e.storage_layout==='legacy_flat'||e.id==='s5joint_'+head.native_sid+'_'+head.sid);}
  function identify(e,entries){
   let sid=e.sid;
   if(!sid&&entries)entries.some(v=>{const raw=v&&typeof v.uri==='string'?v.uri:v&&v.name;if(typeof raw!=='string'||raw.indexOf(e.dir)!==0)return false;const m=/^s5joint_([A-Za-z0-9_-]{1,64})_head\.json$/.exec(raw.slice(e.dir.length));if(m){sid=m[1];return true;}return false;});
   if(!sid)return Promise.reject(Error('目录身份尚未确认'));
   return readObject(e.dir+'s5joint_'+sid+'_head.json').then(head=>{check(g);if(!owned(head,Object.assign({},e,{sid:sid})))throw Error('目录头部身份不符');e.native_sid=head.native_sid;e.sid=head.sid;e.headVerified=true;return e;});
  }
  return directory.read(call,file,ROOT,{discoverDirectories:true}).then(result=>{
   check(g);rootOK=true;rootListing=result;discovery.list_entries=result.diagnostic.list_entries;discovery.get_entries=result.diagnostic.get_entries;discovery.get_error=result.diagnostic.get_error;discovery.root_get_skipped_for_flat_files=!!result.diagnostic.get_skipped_for_flat_files||rootFilesObserved;if(result.diagnostic.get_skipped_for_flat_files)rootFilesObserved=true;consume(result);
   if((!out.length||(options&&options.deep))&&typeof file.get==='function')return directory.tree(call,ROOT).then(v=>{check(g);discovery.recursive_entries=v.fileList.length;consume(v);}).catch(e=>{check(g);discovery.get_error=String(e.message||e);});
  }).catch(e=>{check(g);discovery.root_error=String(e.message||e);}).then(readLocators).then(()=>{
   check(g);if((o.recoveryDirectories||[]).length>256)throw Error('历史身份提示超过安全上限');(o.recoveryDirectories||[]).forEach(uri=>add(uri,true));discovery.candidates=out.length;let at=0;
   function next(){
    check(g);if(at>=out.length){
     catalog=kept.sort((a,b)=>(a.sid||a.id)<(b.sid||b.id)?1:-1);discovery.records=catalog.length;discovery.directory_records=kept.filter(e=>e.storage_layout!=='legacy_flat').length;
     if(!catalog.length)discovery.warning='未找到记录，不能据此认定旧记录已不存在';
     else if(discovery.known_found||discovery.root_error||discovery.get_error||discovery.unreadable_dirs||discovery.known_missing||discovery.root_get_skipped_for_flat_files)discovery.warning='已找到的记录可核对；其他残留是否存在尚未确认';
     if(!rootOK&&!catalog.length)throw Error('系统目录读取失败，请打开扫描详情；尚未删除');
     return catalog.map(x=>({id:x.id,label:x.sid||x.id}));
    }
    const e=out[at++];if(o.onStatus)o.onStatus({phase:'discovering',checked:at,files:out.length,busy:true});
    if(e.storage_layout==='legacy_flat'){
     e.scanListing=rootListing;discovery.flat_records++;return identify(e).then(()=>{kept.push(e);},error=>{check(g);e.scanError=String(error.message||error);discovery.unreadable_dirs++;kept.push(e);}).then(next);
    }
    // Hints are not evidence of existence: require the live owned head before admission.
    const pre=e.hint?identify(e):Promise.resolve(e);
    return pre.then(()=>directory.read(call,file,e.dir,{preferListWhenPopulated:true})).then(v=>{
     check(g);if(!v.fileList.length){return identify(e).then(()=>{discovery.unreadable_dirs++;kept.push(e);if(e.hint)discovery.known_found++;},()=>{check(g);discovery.empty_dirs++;});}
     e.scanListing=v;
     if(e.sid){kept.push(e);if(e.hint)discovery.known_found++;return;}
     return identify(e,v.fileList).then(()=>{kept.push(e);},()=>{check(g);discovery.unreadable_dirs++;});
    }).catch(error=>{check(g);if(e.hint&&!e.headVerified){if(error.code===301){discovery.known_absent++;return;}discovery.known_missing++;discovery.known_errors.push({id:e.id,error:String(error.message||error).slice(0,150)});return;}discovery.unreadable_dirs++;if(e.sid){kept.push(e);if(e.hint)discovery.known_found++;}}).then(next);
   }return next();
  });
 }
 function summary(id){
  let g,e;try{g=begin();e=entry(id);}catch(error){return Promise.reject(error);}
  if(e.scanError)return Promise.resolve({id:id,complete:false,incomplete:false,rows:null,error:e.scanError,label:e.sid});
  return localNames(e,g,true).then(names=>{
   if(names.indexOf('s5joint_'+e.sid+'_tail.json')>=0)return meta(e,g).then(m=>{
    const prefix='s5joint_'+e.sid+'_',expected=[prefix+'head.json',prefix+'tail.json'];
    for(let i=0;i<m.end.blocks;i++)expected.push(prefix+'b'+('0000'+i).slice(-4)+'.json');
    const missing=expected.filter(n=>names.indexOf(n)<0),extra=names.filter(n=>expected.indexOf(n)<0);
    if(extra.length)throw Error('封口以外存在额外文件，保留原状');
    return {id:id,complete:missing.length===0,incomplete:false,partial:missing.length>0,missing_files:missing.length,expected_files:expected.length,file_count:names.length,rows:m.end.count,duration_ms:m.end.stop_ms-m.end.start_ms,start_ms:m.end.start_ms,label:e.sid};
   });
   return failedMeta(e,g,names).then(m=>({id:id,complete:false,incomplete:true,rows:null,file_count:m.names.length,start_ms:m.head.started_epoch_ms,label:e.sid}));
  }).catch(error=>{check(g);return {id:id,complete:false,incomplete:false,rows:null,error:String(error.message||error),label:e.sid};});
 }
 function prepareIncompleteDelete(id,confirmLoss){
  if(confirmLoss!==true)return Promise.reject(Error('必须先确认无备份失败记录删除后不可恢复'));
  let g,e;try{g=begin();e=entry(id);}catch(error){return Promise.reject(error);}
  return failedMeta(e,g).then(m=>{
   const digests={};let index=0;
   function next(){check(g);if(index>=m.names.length)return Promise.resolve();const name=m.names[index++];
    return call('readText',e.dir+name).then(v=>{check(g);if(!v||typeof v.text!=='string'||v.text.length>32768)throw Error('失败记录内容不可核对，保留原状');digests[name]=hash(v.text);return next();});
   }
   return next().then(()=>{
    check(g);child=cleanup.create({file:file,setTimeout:later,clearTimeout:clear,manifest:{schema:1,backup_basis:'unbacked_incomplete',targets:[{native_sid:e.native_sid,sid:e.sid,incomplete:true,backup_verified_on_pc:false,backup_zip_sha256:null,file_sha256:digests}]},onStatus:s=>{if(g===generation&&o.onStatus)o.onStatus(s);}});return child.prepare();
   }).then(s=>{check(g);preparedId=id;return Object.assign({},s,{prepared_id:id});});
  });
 }
 // Preview reads only owned metadata. A tail never proves that all blocks exist.
 function preview(id){
  let g,e;try{g=begin();e=entry(id);}catch(error){return Promise.reject(error);}
  if(e.scanError)return Promise.resolve({id:id,complete:false,incomplete:false,rows:null,error:e.scanError,label:e.sid});
  return meta(e,g).then(m=>({id:id,sealed:true,complete:false,incomplete:false,blocks_verified:false,rows:m.end.count,expected_files:m.end.blocks+2,duration_ms:m.end.stop_ms-m.end.start_ms,start_ms:m.end.start_ms,label:e.sid})).catch(error=>{
   check(g);if(error.code!==301)return {id:id,complete:false,incomplete:false,rows:null,error:String(error.message||error),label:e.sid};
   return readObject(e.dir+'s5joint_'+e.sid+'_head.json').then(head=>{check(g);if(!layout.owned(head,e))throw Error('头部身份不符');return {id:id,complete:false,incomplete:true,blocks_verified:false,rows:null,start_ms:head.started_epoch_ms,label:e.sid};}).catch(err=>({id:id,complete:false,incomplete:false,rows:null,error:String(err.message||err),label:e.sid}));
  });
 }
 function completeSnapshot(e,g){
  return meta(e,g).then(m=>{
   const digests=[];let index=0,rows=0,last=-1;
   function next(){
    check(g);if(index>=m.end.blocks){if(rows!==m.end.count)throw Error('本地块总行数与封口不符');return Promise.resolve();}
    const i=index++;return call('readText',m.prefix+'b'+('0000'+i).slice(-4)+'.json').then(v=>{
     check(g);if(!v||typeof v.text!=='string'||v.text.length>32768)throw Error('本地块无效');const block=JSON.parse(v.text);
     if(!Array.isArray(block)||block.length<1||block.length>32)throw Error('本地块格式无效');
     block.forEach(r=>{if(!Array.isArray(r)||r.length!==5||r[0]!==rows||!Number.isSafeInteger(r[1])||r[1]<m.end.start_ms||r[1]>m.end.stop_ms||r[1]<=last||!r.slice(2).every(x=>typeof x==='number'&&isFinite(x)))throw Error('本地样本顺序或数值异常');last=r[1];rows++;});
     digests.push(hash(v.text));if(o.onStatus&&index%20===0)o.onStatus({phase:'checking',checked:index,deleted:0,files:m.end.blocks+2,busy:true,backup_basis:'user_confirmed_export'});return next();
    });
   }
   return next().then(()=>({card:null,native_sid:e.native_sid,sid:e.sid,backup_verified_on_pc:false,backup_confirmed_by_user:true,backup_zip_sha256:null,rows:m.end.count,block_sha256:digests,end:m.end}));
  });
 }
 function prepareBatchDelete(ids,confirmed){
  if(confirmed!==true)return Promise.reject(Error('必须先确认所选导出包仍保留'));
  if(!Array.isArray(ids)||ids.length<1||ids.length>256||new Set(ids).size!==ids.length)return Promise.reject(Error('所选记录为空、重复或超限'));
  let g,entries;try{g=begin();entries=ids.slice().sort().map(entry);}catch(error){return Promise.reject(error);}
  const targets=[];let at=0;
  function next(){check(g);if(at>=entries.length)return Promise.resolve();return completeSnapshot(entries[at++],g).then(t=>{targets.push(t);return next();});}
  return next().then(()=>{
   check(g);child=cleanup.create({file:file,setTimeout:later,clearTimeout:clear,manifest:{schema:1,backup_basis:'user_confirmed_export',targets:targets},onStatus:s=>{if(g===generation&&o.onStatus)o.onStatus(s);}});return child.prepare();
  }).then(s=>{check(g);preparedId=ids.slice().sort().join('|');return Object.assign({},s,{prepared_id:preparedId,prepared_ids:ids.slice().sort()});});
 }
 function prepareDelete(id,confirmed){return prepareBatchDelete([id],confirmed);}

 function restore(hints){
  const cache=require('./view-cache.js');if(!cache.valid(hints))return Promise.reject(Error('上次列表身份无效'));
  let g;try{g=begin();}catch(e){return Promise.reject(e);}catalog=[];const kept=[];let at=0;
  function next(){
   check(g);if(at>=hints.length){catalog=kept;discovery={records:kept.length,restored_from_identity_cache:true,warning:'上次列表已重新核对；刷新可查找新增记录'};return Promise.resolve(catalog.map(e=>({id:e.id,label:e.sid})));}
   const row=hints[at++],loc=layout.location({native_sid:row[0],sid:row[1],storage_layout:row[2]==='f'?'legacy_flat':'isolated_session_directory'}),e=Object.assign({},loc,{id:row[2]==='f'?'flat:'+row[1]:'s5joint_'+row[0]+'_'+row[1]});
   return readObject(e.dir+'s5joint_'+e.sid+'_head.json').then(h=>{check(g);if(layout.owned(h,e))kept.push(e);},error=>{check(g);if(error.code!==301){e.scanError=String(error.message||error);kept.push(e);}}).then(next);
  }return next();
 }

 // A local snapshot is not a PC backup. Consent is required only at purge.
 function prepareSelection(ids){
  if(!Array.isArray(ids)||!ids.length||ids.length>256||new Set(ids).size!==ids.length)return Promise.reject(Error('请选择至少一条记录，不能重复'));
  let g,entries;try{g=begin();entries=ids.slice().sort().map(entry);}catch(error){return Promise.reject(error);}
  const targets=[];let at=0,totalChecked=0;
  function progress(files){if(o.onStatus)o.onStatus({phase:'snapshotting',checked:totalChecked,deleted:0,files:files,busy:true,session_index:at,sessions:entries.length});}
  function snapshot(e){
   return localNames(e,g).then(names=>{
    const prefix='s5joint_'+e.sid+'_';if(names.indexOf(prefix+'head.json')<0)throw Error('没有可验证的会话头部，保留此条');
    return readObject(e.dir+prefix+'head.json').then(head=>{
    check(g);if(!layout.owned(head,e))throw Error('会话头部身份不符，保留此条');
     if(names.indexOf(prefix+'tail.json')<0)return {kind:'incomplete',head:head};
     return meta(e,g).then(m=>{
      const expected=[prefix+'head.json',prefix+'tail.json'];for(let i=0;i<m.end.blocks;i++)expected.push(prefix+'b'+('0000'+i).slice(-4)+'.json');
      if(names.some(n=>expected.indexOf(n)<0))throw Error('封口范围外存在额外文件，未删除');
      return {kind:names.length===expected.length?'complete':'partial',head:head,end:m.end};
     });
    }).then(info=>{
     const digests={};let ni=0,rows=0,last=-1;
     function readNext(){
      check(g);if(ni>=names.length){if(info.kind==='complete'&&rows!==info.end.count)throw Error('行数与封口不符，保留此条');return Promise.resolve();}
      const name=names[ni++];return call('readText',e.dir+name).then(v=>{
       check(g);if(!v||typeof v.text!=='string'||v.text.length>32768)throw Error('记录内容无法核对，未删除');
       if(info.kind==='complete'&&/b[0-9]{4}\.json$/.test(name)){
        const block=JSON.parse(v.text);if(!Array.isArray(block)||!block.length||block.length>32)throw Error('数据块格式异常，保留此条');
        block.forEach(r=>{if(!Array.isArray(r)||r.length!==5||r[0]!==rows||!Number.isSafeInteger(r[1])||r[1]<info.end.start_ms||r[1]>info.end.stop_ms||r[1]<=last||!r.slice(2).every(x=>typeof x==='number'&&isFinite(x)))throw Error('样本顺序或数值异常，保留此条');last=r[1];rows++;});
       }
       if(name===prefix+'head.json'&&cleanup.canonical(JSON.parse(v.text))!==cleanup.canonical(info.head))throw Error('核对期间头部改变，未删除');
       if(name===prefix+'tail.json'&&cleanup.canonical(JSON.parse(v.text))!==cleanup.canonical(info.end))throw Error('核对期间封口改变，未删除');
       digests[name]=hash(v.text);totalChecked++;if(ni===1||ni%10===0||ni===names.length)progress(names.length);return readNext();
      });
     }
     progress(names.length);return readNext().then(()=>({native_sid:e.native_sid,sid:e.sid,storage_layout:e.storage_layout||'isolated_session_directory',source_state:info.kind,started_ms:info.head.started_epoch_ms,file_sha256:digests}));
    });
   });
  }
  function next(){check(g);if(at>=entries.length)return Promise.resolve();return snapshot(entries[at++]).then(t=>{targets.push(t);return next();});}
  return next().then(()=>{
   check(g);child=cleanup.create({file:file,setTimeout:later,clearTimeout:clear,manifest:{schema:1,backup_basis:'selected_local_snapshot',targets:targets},onStatus:s=>{if(g===generation&&o.onStatus)o.onStatus(s);}});return child.prepareFromSnapshot();
  }).then(s=>{check(g);preparedId=ids.slice().sort().join('|');return Object.assign({},s,{prepared_id:preparedId});});
 }

 return {scan:scan,restore:restore,preview:preview,releasePrepared:function(){active();generation++;preparedId=null;if(child)child.cancel();child=null;},releaseInventories:function(){catalog.forEach(e=>{delete e.scanListing;});},catalogHints:function(){return catalog.filter(e=>typeof e.native_sid==='string'&&typeof e.sid==='string').map(e=>[e.native_sid,e.sid,e.storage_layout==='legacy_flat'?'f':'i']);},summary:summary,discovery:function(){return JSON.parse(JSON.stringify(discovery));},prepareDelete:prepareDelete,prepareBatchDelete:prepareBatchDelete,prepareIncompleteDelete:prepareIncompleteDelete,prepareSelection:prepareSelection,
  forgetDeleted:function(ids){const s=child&&child.state();if(!s||s.phase!=='complete'||s.verified_absent_files!==s.files||ids.slice().sort().join('|')!==preparedId)throw Error('删除结果尚未核实，不能移除列表');generation++;catalog=catalog.filter(e=>ids.indexOf(e.id)<0);preparedId=null;},
  purge:function(c){if(!child||!preparedId||!c||c.preparedId!==preparedId)return Promise.reject(Error('核对记录与当前选择不符，请重新选择'));return child.purge(c);},
  state:function(){return child?Object.assign({},child.state(),{prepared_id:preparedId}):{phase:'idle',busy:false,prepared_id:null};},
  suspend:function(){if(child)return child.suspend();},resume:function(){if(child)return Object.assign({},child.resume(),{prepared_id:preparedId});return null;},
  cancel:function(){generation++;preparedId=null;if(child)child.cancel();}};
}
module.exports={create:create};
