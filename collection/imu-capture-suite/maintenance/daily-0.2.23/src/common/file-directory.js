// Both native directory interfaces are read-only. Never turn a foreign URI into a basename.
const ROOT='internal://files/';
function relative(raw){
 if(typeof raw!=='string')return null;
 let s=raw;if(s.indexOf(ROOT)===0){s=s.slice(ROOT.length).replace(/^\/+/, '');}
 else if(s.indexOf('://')>=0||s.charAt(0)==='/')return null;
 // Native __read_dir_c joins dirname + '/' + leaf even when dirname already
 // ends in '/'. Collapse separators only inside the already checked files root.
 // Dot segments, encoded paths, other schemes and absolute OS paths stay invalid.
 s=s.replace(/\/+/g,'/');
 if(!/^[A-Za-z0-9_-][A-Za-z0-9_.-]*(\/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*\/?$/.test(s))return null;
 return s;
}
function merge(base,groups){
 const out=[],seen={};
 function add(entry,parent,depth){
  if(depth>4||out.length>=20000)throw Error('目录条目过多或层级异常，保留原状');
  const raw=entry&&typeof entry.uri==='string'?entry.uri:entry&&entry.name;
  let uri=raw;
  if(typeof raw==='string'){
   if(raw.indexOf(ROOT)===0){const r=relative(raw);if(r!==null)uri=ROOT+r;}
   else if(relative(raw)!==null){
    const normalized=relative(raw);
    const scope=relative(parent);
    // Root-relative children already contain the selected directory.
    // Preserve that scope instead of appending it a second time.
    uri=scope&&normalized.indexOf(scope)===0?ROOT+normalized:parent+normalized;
   }
  }
  const key=typeof uri==='string'?uri:'#invalid'+out.length;
  if(!seen[key]){seen[key]=true;out.push({uri:uri});}
  if(entry&&Array.isArray(entry.subFiles)){
   if(typeof uri!=='string'||uri.indexOf(ROOT)!==0||relative(uri)===null)throw Error('子目录路径无法核对');
   entry.subFiles.forEach(e=>add(e,uri.replace(/\/$/,'')+'/',depth+1));
  }
 }
 groups.forEach(g=>g.forEach(e=>add(e,base,0)));return out;
}
function read(call,file,uri,options){
 const groups=[],d={list_entries:0,get_entries:0,list_error:'',get_error:'',get_available:typeof file.get==='function',get_ok:false};let ok=false;
 return call('list',uri).then(v=>{
  if(!v||!Array.isArray(v.fileList))throw Error('list返回格式无效');d.list_entries=v.fileList.length;groups.push(v.fileList);ok=true;
 }).catch(e=>{d.list_error=String(e.message||e);}).then(()=>{
  const flat=uri===ROOT&&options&&options.preferRootFiles&&!options.discoverDirectories&&groups.some(g=>g.some(e=>{const r=relative(e&&typeof e.uri==='string'?e.uri:e&&e.name);return r!==null&&/^s5joint_[A-Za-z0-9_-]{1,64}_(head|tail|b[0-9]{4})\.json$/.test(r);}));
  if(flat)d.get_skipped_for_flat_files=true;
  if(!d.get_available||flat||(options&&options.preferList&&ok)||(options&&options.preferListWhenPopulated&&groups.some(g=>g.length)))return;
  return call('get',uri,{recursive:false}).then(v=>{
   if(!v||v.type!=='dir'||!Array.isArray(v.subFiles))throw Error('get没有返回目录内容');
   d.get_ok=true;d.get_entries=v.subFiles.length;groups.push(v.subFiles);ok=true;
  }).catch(e=>{d.get_error=String(e.message||e);});
 }).then(()=>{if(!ok)throw Error(d.list_error+'；'+d.get_error);return {fileList:merge(uri,groups),diagnostic:d};});
}
function tree(call,uri){return call('get',uri,{recursive:true}).then(v=>{
 if(!v||v.type!=='dir'||!Array.isArray(v.subFiles))throw Error('递归目录返回无效');
 return {fileList:merge(uri,[v.subFiles])};
});}
module.exports={read:read,tree:tree,relative:relative,compact:function(base,entries){if(!Array.isArray(entries))throw Error('目录返回格式无效');return merge(base,[entries]);}};
