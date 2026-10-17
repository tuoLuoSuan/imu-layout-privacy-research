// Process-local display cache. Core inventory/inspect remain authoritative for operations.
const ROOT='internal://files/',ID=/^[0-9]{1,16}_[a-f0-9]{6}$/,WINDOW=40;
function copy(v){return JSON.parse(JSON.stringify(v));}
function wrap(base,file,normalize){
 normalize=normalize||require('./directory-entries.js').normalize;
 let snapshot=null,cache=[],generation=0,last={available:false},timing={native_list_ms:0,organize_ms:0,summary_ms:0};
 function invalidate(){generation++;snapshot=null;cache=[];last={available:false};}
 function current(g){if(!snapshot||snapshot.groups[g.id]!==g)throw Error('记录列表已变更，请刷新');}
 function call(method,args){return new Promise((resolve,reject)=>{
  let done=false;const timer=setTimeout(()=>finish(Error('文件操作超时')),8000);
  function finish(error,data){if(done)return;done=true;clearTimeout(timer);error?reject(error):resolve(data);}
  try{file[method](Object.assign({},args,{success:d=>finish(null,d),fail:(m,c)=>finish(Error('文件操作失败 '+c))}));}catch(e){finish(e);}
 });}
 function descriptor(g){return {id:g.id,state:g.deleting?'deleting':'unread',trashed:g.trashed,count:null,duration_ms:null,catalog_ready:g.deleting};}
 function remember(g,item){current(g);cache=cache.filter(c=>c.id!==g.id);cache.push({id:g.id,signature:g.signature,item:copy(item)});if(cache.length>WINDOW)cache.shift();return item;}
 function view(trashed,offset,source){
  const ids=snapshot.ids.filter(id=>snapshot.groups[id].trashed===!!trashed),total=ids.length;
  offset=Number.isInteger(offset)&&offset>=0?Math.floor(offset/WINDOW)*WINDOW:0;
  if(offset>=total)offset=total?Math.floor((total-1)/WINDOW)*WINDOW:0;
  last={available:true,source:source,total:total,offset:offset,window:WINDOW,used:snapshot.used,trashed:snapshot.trashed,limit:40,timing:copy(timing)};
  return ids.slice(offset,offset+WINDOW).map(id=>{const g=snapshot.groups[id],c=cache.find(c=>c.id===id&&c.signature===g.signature);return c?copy(c.item):descriptor(g);});
 }
 function list(trashed,options){
  options=options||{};
  if(options.reuse&&snapshot)return Promise.resolve(view(trashed,options.offset,'cached'));
  const ticket=++generation,started=Date.now();snapshot=null;last={available:false};
  return call('list',{uri:ROOT}).then(data=>{
   if(ticket!==generation)throw Error('记录列表已变更，请刷新');
   const organize=Date.now();timing.native_list_ms=Math.max(0,organize-started);
   const names=normalize(data&&data.fileList).map(e=>e.uri.slice(ROOT.length)),all=Object.create(null);
   names.forEach(n=>{const m=/^s5r_([0-9]{1,16}_[a-f0-9]{6})_(head|tail|trash|purge|b[0-9]{4})\.json$/.exec(n);if(m)(all[m[1]]||(all[m[1]]=[])).push(n);});
   const ids=Object.keys(all).filter(id=>all[id].indexOf('s5r_'+id+'_head.json')>=0).sort().reverse(),groups=Object.create(null);
   let trashedCount=0;
   ids.forEach(id=>{const prefix='s5r_'+id+'_',own=all[id].sort(),deleting=own.indexOf(prefix+'purge.json')>=0;
    const trashed=deleting||own.indexOf(prefix+'trash.json')>=0;if(trashed)trashedCount++;
    groups[id]={id:id,names:own,signature:own.join('|'),deleting:deleting,trashed:trashed};});
   // Match the original start guard, including malformed head filenames occupying quota.
   snapshot={ids:ids,groups:groups,used:names.filter(n=>/^s5r_.*_head\.json$/.test(n)).length,trashed:trashedCount};
   // Even equal filenames do not prove equal head/tail contents after an explicit refresh.
   cache=[];timing.organize_ms=Math.max(0,Date.now()-organize);
   return view(trashed,options.offset,'fresh');
  }).catch(e=>{if(ticket===generation)invalidate();throw e;});
 }
 function read(name){return call('readText',{uri:ROOT+name}).then(data=>{if(typeof data.text!=='string'||data.text.length>65536)throw Error('会话文件过大或无效');return JSON.parse(data.text);});}
 function describe(id){return Promise.resolve().then(()=>{
  if(typeof id!=='string'||!ID.test(id)||!snapshot||!snapshot.groups[id])throw Error('请刷新记录列表');
  const g=snapshot.groups[id],found=cache.find(c=>c.id===id&&c.signature===g.signature);
  if(found){cache=cache.filter(c=>c!==found).concat([found]);return copy(found.item);}
  if(g.deleting)return descriptor(g);
  const started=Date.now(),prefix='s5r_'+id+'_',blocks=g.names.filter(n=>/_b[0-9]{4}\.json$/.test(n)).sort();
  return Promise.resolve().then(()=>{
   if(blocks.length>400||blocks.some((n,i)=>n!==prefix+'b'+('0000'+i).slice(-4)+'.json'))throw Error('会话数据块缺失或超限');
   return read(prefix+'head.json');
  }).then(head=>{
   current(g);
   if(head.kind!=='head'||head.session_id!==id||head.schema_version!==2||typeof head.started_epoch_ms!=='number'||!isFinite(head.started_epoch_ms))throw Error('会话元数据损坏');
   return (g.names.indexOf(prefix+'tail.json')>=0?read(prefix+'tail.json'):Promise.resolve(null)).then(tail=>{
    current(g);
    if(tail&&(tail.kind!=='tail'||tail.session_id!==id||tail.blocks!==blocks.length||!tail.quality||!Array.isArray(tail.quality.warnings)||!Number.isInteger(tail.persisted)||tail.persisted<0||tail.persisted>40000||typeof tail.stopped_epoch_ms!=='number'||!isFinite(tail.stopped_epoch_ms)))throw Error('封口与块数量不符');
    return remember(g,{id:id,trashed:g.trashed,state:tail?'sealed':'interrupted',count:tail?tail.persisted:null,duration_ms:tail?tail.stopped_epoch_ms-head.started_epoch_ms:null,stop_reason:tail?tail.stop_reason:'unknown_interruption',tail:tail?{quality:{warnings:tail.quality.warnings.slice()}}:null,catalog_ready:true});
   });
  }).catch(e=>{current(g);return {id:id,state:'corrupt',issue:String(e.message||e),trashed:g.trashed,count:null,duration_ms:null,catalog_ready:true};})
   .then(item=>{timing.summary_ms=Math.max(0,Date.now()-started);return item;});
 });}
 const result=Object.assign({},base,{list:list,describe:describe,invalidateCatalog:invalidate,catalogState:()=>copy(Object.assign({},last,{timing:timing}))});
 ['start','trash','restore','purge'].forEach(name=>{result[name]=function(){
  const args=arguments;invalidate();
  // Original restore only removes the marker. Require a live source check before that mutation.
  const operation=name==='restore'?base.inspect(args[0]).then(item=>{if(!item.trashed)throw Error('该记录已不在回收区，请刷新');return base.restore.apply(base,args);}):Promise.resolve().then(()=>base[name].apply(base,args));
  return operation.then(value=>{invalidate();return value;},error=>{invalidate();if(name==='start'&&error.message==='已达40条，请先整理记录')throw Error('新建上限40条，回收区仍占名额；旧记录可浏览和导出，请先核验备份，勿直接删除');throw error;});
 };});
 return result;
}
module.exports={wrap:wrap};
