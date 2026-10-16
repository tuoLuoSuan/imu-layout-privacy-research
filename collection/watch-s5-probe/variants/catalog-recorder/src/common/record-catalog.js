// Advisory list summaries only. Export and mutation continue through the original store.
const ROOT='internal://files/',ID=/^[0-9]{1,16}_[a-f0-9]{6}$/;
function copy(v){return JSON.parse(JSON.stringify(v));}
function wrap(base,file,normalize){
 normalize=normalize||require('./directory-entries.js').normalize;
 let snapshot=null,cache=[];
 function invalidate(){snapshot=null;cache=[];}
 function call(method,args){
  return new Promise((resolve,reject)=>{
   let done=false;const timer=setTimeout(()=>finish(Error('文件操作超时')),8000);
   function finish(error,data){if(done)return;done=true;clearTimeout(timer);error?reject(error):resolve(data);}
   try{file[method](Object.assign({},args,{success:d=>finish(null,d),fail:(m,c)=>finish(Error('文件操作失败 '+c))}));}catch(e){finish(e);}
  });
 }
 function group(id){if(typeof id!=='string'||!ID.test(id)||!snapshot||!snapshot[id])throw Error('请刷新记录列表');return snapshot[id];}
 function descriptor(g){return {id:g.id,state:g.deleting?'deleting':'unread',trashed:g.trashed,count:null,duration_ms:null,catalog_ready:g.deleting};}
 function remember(g,item){
  cache=cache.filter(c=>c.id!==g.id);cache.push({id:g.id,signature:g.signature,item:copy(item)});if(cache.length>8)cache.shift();return item;
 }
 function list(trashed){
  snapshot=null;
  return call('list',{uri:ROOT}).then(data=>{
   const names=normalize(data&&data.fileList).map(e=>e.uri.slice(ROOT.length));
   const all=Object.create(null);names.forEach(n=>{const m=/^s5r_([0-9]{1,16}_[a-f0-9]{6})_(head|tail|trash|purge|b[0-9]{4})\.json$/.exec(n);if(m)(all[m[1]]||(all[m[1]]=[])).push(n);});
   const ids=Object.keys(all).filter(id=>all[id].indexOf('s5r_'+id+'_head.json')>=0).sort().reverse();
   if(ids.length>40)throw Error('超过40条，请先整理记录');
   const groups=Object.create(null);ids.forEach(id=>{const prefix='s5r_'+id+'_',own=all[id].sort();
    const deleting=own.indexOf(prefix+'purge.json')>=0;groups[id]={id:id,names:own,signature:own.join('|'),deleting:deleting,trashed:deleting||own.indexOf(prefix+'trash.json')>=0};});
   snapshot=groups;cache=cache.filter(c=>groups[c.id]&&groups[c.id].signature===c.signature);
   return ids.filter(id=>groups[id].trashed===!!trashed).map(id=>{const g=groups[id],found=cache.find(c=>c.id===id&&c.signature===g.signature);return found?copy(found.item):descriptor(g);});
  }).catch(e=>{invalidate();throw e;});
 }
 function read(name){return call('readText',{uri:ROOT+name}).then(data=>{if(typeof data.text!=='string'||data.text.length>65536)throw Error('会话文件过大或无效');return JSON.parse(data.text);});}
 function describe(id){
  return Promise.resolve().then(()=>{
   const g=group(id),found=cache.find(c=>c.id===id&&c.signature===g.signature);
   if(found){cache=cache.filter(c=>c!==found).concat([found]);return copy(found.item);}
   if(g.deleting)return descriptor(g);
   const prefix='s5r_'+id+'_',blocks=g.names.filter(n=>/_b[0-9]{4}\.json$/.test(n)).sort();
   return Promise.resolve().then(()=>{
    if(blocks.length>400||blocks.some((n,i)=>n!==prefix+'b'+('0000'+i).slice(-4)+'.json'))throw Error('会话数据块缺失或超限');
    return read(prefix+'head.json');
   }).then(head=>{
    if(head.kind!=='head'||head.session_id!==id||head.schema_version!==2||typeof head.started_epoch_ms!=='number'||!isFinite(head.started_epoch_ms))throw Error('会话元数据损坏');
    return (g.names.indexOf(prefix+'tail.json')>=0?read(prefix+'tail.json'):Promise.resolve(null)).then(tail=>{
     if(tail&&(tail.kind!=='tail'||tail.session_id!==id||tail.blocks!==blocks.length||!tail.quality||!Array.isArray(tail.quality.warnings)||!Number.isInteger(tail.persisted)||tail.persisted<0||tail.persisted>40000||typeof tail.stopped_epoch_ms!=='number'||!isFinite(tail.stopped_epoch_ms)))throw Error('封口与块数量不符');
     return remember(g,{id:id,trashed:g.trashed,state:tail?'sealed':'interrupted',count:tail?tail.persisted:null,
      duration_ms:tail?tail.stopped_epoch_ms-head.started_epoch_ms:null,stop_reason:tail?tail.stop_reason:'unknown_interruption',
      tail:tail?{quality:{warnings:tail.quality.warnings.slice()}}:null,catalog_ready:true});
    });
   }).catch(e=>({id:id,state:'corrupt',issue:String(e.message||e),trashed:g.trashed,count:null,duration_ms:null,catalog_ready:true}));
  });
 }
 const result=Object.assign({},base,{list:list,describe:describe});
 ['start','trash','restore','purge'].forEach(name=>{result[name]=function(){const args=arguments;invalidate();return base[name].apply(base,args);};});
 return result;
}
module.exports={wrap:wrap};
