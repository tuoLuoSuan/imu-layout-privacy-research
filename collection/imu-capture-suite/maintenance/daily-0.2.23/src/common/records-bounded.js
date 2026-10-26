// Batch consent freezes per-record content signatures. Full file hash maps live
// in one original cleanup engine at a time, never one engine per selected record.
const records=require('./records.js'),index=require('./catalog-index.js'),cache=require('./view-cache.js'),hash=require('./ascii-sha256.js').hash;
function create(o){
 let generation=0,phase='idle',busy=false,error='',uncertain=false,snapshots=[],token=null,preparedId=null,files=0,doneIds=[],completedIds=[],totals={requests:0,deleted:0,absent:0},at=0,mode='',sessions=0;
 const core=records.create({file:o.file,recoveryDirectories:o.recoveryDirectories,onStatus:s=>{if(o.onStatus&&busy)o.onStatus(Object.assign({},s,{phase:mode==='preparing'?'snapshotting':s.phase==='snapshotting'?'rechecking':s.phase,session_index:at,sessions:sessions}));}});
 function state(){const s=core.state();return {phase:phase,busy:busy||!!s.busy,error:error,uncertain:uncertain||!!s.uncertain,files:files,expected_files:files,checked:s.checked||0,deleted:totals.deleted+(s.deleted||0),delete_requests:totals.requests+(s.delete_requests||0),verified_absent_files:totals.absent+(s.verified_absent_files||0),token:token,prepared_id:preparedId,sessions:sessions,complete_sessions:snapshots.reduce((n,s)=>n+s.complete,0),partial_sessions:snapshots.reduce((n,s)=>n+s.partial,0),incomplete_sessions:snapshots.reduce((n,s)=>n+s.incomplete,0),removed_ids:doneIds.slice(),retained_signature_records:snapshots.length,retained_full_file_records:s.prepared_id?1:0};}
 function check(g){if(g!==generation)throw Error('页面或选择已改变，已停止');}
 function begin(kind){if(busy||core.state().busy)throw Error('文件操作尚未结束');generation++;token=null;preparedId=null;error='';uncertain=false;doneIds=[];completedIds=[];totals={requests:0,deleted:0,absent:0};mode=kind;return generation;}
 function failure(e,g){if(g===generation){const s=core.state();uncertain=uncertain||!!s.uncertain;error=String(e.message||e);phase='error';busy=false;token=null;preparedId=null;}throw e;}
 function scan(){let g;try{g=begin('reading');}catch(e){return Promise.reject(e);}busy=true;phase='reading';snapshots=[];files=0;
  return index.load(o.file).then(v=>cache.load(o.file).then(saved=>index.merge([index.fromDirectories(o.recoveryDirectories),v.hints,saved.hints||[]]))).then(refs=>{check(g);return core.restore(refs);}).then(rows=>{check(g);busy=false;phase='idle';return rows;}).catch(e=>failure(e,g));
 }
 function recordSignature(id,s){return {id:id,token:s.token,files:s.files,complete:s.complete_sessions||0,partial:s.partial_sessions||0,incomplete:s.incomplete_sessions||0};}
 function same(a,s){if(a.token!==s.token||a.files!==s.files||a.id!==s.prepared_id)throw Error('所选记录内容已改变，已停止');}
 function prepareSelection(ids){let g;try{g=begin('preparing');if(!Array.isArray(ids)||!ids.length||ids.length>256||new Set(ids).size!==ids.length)throw Error('所选记录为空、重复或超限');}catch(e){return Promise.reject(e);}busy=true;phase='checking';snapshots=[];files=0;at=0;sessions=ids.length;
  const selected=ids.slice().sort();function next(){check(g);if(at>=selected.length){preparedId=selected.join('|');token='bounded_'+g+'_'+hash(snapshots.map(s=>s.id+' '+s.token).join('\n'));phase='ready';busy=false;return state();}const id=selected[at++];return core.prepareSelection([id]).then(s=>{check(g);snapshots.push(recordSignature(id,s));files+=s.files;core.releasePrepared();return next();});}
  return Promise.resolve().then(next).catch(e=>failure(e,g));
 }
 function purge(c){
  if(busy||phase!=='ready'||!token||!c||c.token!==token||c.preparedId!==preparedId||!c.confirmPermanent)return Promise.reject(Error('请先核对并确认所选记录'));
  if(snapshots.some(s=>s.complete)&&c.confirmBackup!==true)return Promise.reject(Error('请确认所需导出包已保留'));
  if(snapshots.some(s=>s.partial||s.incomplete)&&c.confirmUnbackedLoss!==true)return Promise.reject(Error('请确认接受不完整内容丢失'));
  if(snapshots.some(s=>s.partial)&&c.confirmPartial!==true)return Promise.reject(Error('请确认缺块内容永久丢失'));
  if(snapshots.some(s=>s.incomplete)&&c.confirmFailedRecord!==true)return Promise.reject(Error('请确认未完成记录永久丢失'));
  const g=generation;token=null;busy=true;phase='rechecking';mode='validating';at=0;
  // All signatures must still match before the first irreversible operation.
  function validateAll(){check(g);if(at>=snapshots.length)return Promise.resolve();const expected=snapshots[at++];return core.prepareSelection([expected.id]).then(s=>{check(g);same(expected,s);core.releasePrepared();return validateAll();});}
  function deleteNext(){check(g);if(at>=snapshots.length){phase='complete';busy=false;completedIds=snapshots.map(s=>s.id).sort();return state();}const expected=snapshots[at++];return core.prepareSelection([expected.id]).then(s=>{check(g);same(expected,s);return core.purge(Object.assign({},c,{token:s.token,preparedId:s.prepared_id}));}).then(r=>{check(g);core.forgetDeleted([expected.id]);doneIds.push(expected.id);totals.requests+=r.delete_requests;totals.deleted+=r.deleted;totals.absent+=r.verified_absent_files;core.releasePrepared();return deleteNext();});}
  return validateAll().then(()=>{check(g);at=0;phase='deleting';mode='deleting';return deleteNext();}).catch(e=>failure(e,g));
 }
 function cancel(){generation++;token=null;preparedId=null;core.cancel();busy=false;if(phase!=='complete')phase='cancelled';}
 return {scan:scan,summary:id=>core.preview(id),releaseInventories:()=>core.releaseInventories(),catalogHints:()=>core.catalogHints(),discovery:()=>Object.assign({},core.discovery(),{scope:'verified_known_identity_paths',unregistered_orphans_not_fully_enumerated:true}),prepareSelection:prepareSelection,purge:purge,state:state,cancel:cancel,forgetDeleted:ids=>{if(phase!=='complete'||ids.slice().sort().join('|')!==completedIds.join('|')||totals.absent!==files)throw Error('所选删除结果尚未全部核实');}};
}
module.exports={create:create};
