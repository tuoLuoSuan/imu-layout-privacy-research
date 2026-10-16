// Read-only observation of the platform response. No URI repair, index, or record writes.
const ROOT='internal://files/';
function type(value){return value===null?'null':Array.isArray(value)?'array':typeof value;}
function clip(value){return value.length>160?value.slice(0,160)+'…':value;}
function shape(value){
 const result={type:type(value),keys:[],arrays:[]};
 if(value===null||typeof value!=='object')return result;
 result.keys=Object.keys(value).slice(0,8);
 const candidates=Array.isArray(value)?[{name:'返回值本身',value:value}]:result.keys.map(k=>({name:k,value:value[k]}));
 candidates.filter(p=>Array.isArray(p.value)).forEach(p=>{
  result.arrays.push({name:p.name,count:p.value.length,entries:p.value.slice(0,3).map(entry=>{
   const item={type:type(entry)};
   if(entry&&typeof entry==='object'){
    item.keys=Object.keys(entry).slice(0,8);
    ['uri','name'].forEach(k=>{if(typeof entry[k]==='string')item[k]=clip(entry[k]);});
   }else if(typeof entry==='string')item.value=clip(entry);
   return item;
  })});
 });
 return result;
}
function probe(file,method,timeoutMs){
 return new Promise(resolve=>{
  let done=false;
  const timer=setTimeout(()=>finish({method:method,status:'timeout',error:'超过8秒（或测试时限）未回调'}),timeoutMs);
  function finish(result){if(done)return;done=true;clearTimeout(timer);resolve(result);}
  const args={uri:ROOT,success:value=>finish({method:method,status:'success',shape:shape(value)}),
   fail:(message,code)=>finish({method:method,status:'failed',error:clip(String(code)+' '+String(message))})};
  if(method==='get')args.recursive=false;
  try{
   if(typeof file[method]!=='function')throw Error('file.'+method+' 不可用');
   file[method](args);
  }catch(e){finish({method:method,status:'failed',error:clip(String(e.message||e))});}
 });
}
function pagesFor(probes){
 const pages=[];
 function add(title,text){
  const lines=[];let line='',width=0;
  for(let i=0;i<text.length;i++){
   const c=text.charAt(i),size=c.charCodeAt(0)>127?2:1;
   if(c==='\n'){lines.push(line);line='';width=0;continue;}
   if(width+size>30){lines.push(line);line='';width=0;}
   line+=c;width+=size;
  }
  if(line)lines.push(line);
  for(let i=0;i<lines.length;i+=4)pages.push({title:title+(lines.length>4?' · '+(Math.floor(i/4)+1):''),detail:lines.slice(i,i+4).join('\n')});
 }
 probes.forEach(p=>{
  if(p.status!=='success'){add('file.'+p.method+' · '+p.status,p.error);return;}
  const s=p.shape;
  add('file.'+p.method+' 返回','类型：'+s.type+'\n字段：'+s.keys.join(', ')+
   '\n'+(s.arrays.length?s.arrays.map(a=>a.name+'：'+a.count+'项').join('\n'):'没有数组字段'));
  s.arrays.forEach(a=>a.entries.forEach((entry,i)=>{
   const detail=entry.uri!==undefined?'uri='+entry.uri:entry.name!==undefined?'name='+entry.name:entry.value!==undefined?'字符串='+entry.value:'无uri/name；类型='+entry.type;
   // Line breaks are display-only; original strings remain in probes, never used as paths.
   add(p.method+' '+a.name+' 第'+(i+1)+'项',detail);
  }));
 });
 return pages;
}
function inspect(file,options){
 const timeout=options&&options.timeoutMs!==undefined?options.timeoutMs:8000;
 return probe(file,'list',timeout).then(list=>probe(file,'get',timeout).then(get=>{
  const probes=[list,get];return {probes:probes,pages:pagesFor(probes)};
 }));
}
module.exports={inspect:inspect};
