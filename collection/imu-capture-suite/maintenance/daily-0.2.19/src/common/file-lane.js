// Maintenance only: one native request, compact before resolving a Promise,
// then return to the native event loop before the next request starts.
const directory=require('./file-directory.js');
function create(native,env){
 env=env||{};const timeout=env.timeoutMs||30000;let queue=[],active=null,maxNative=0,serial=0,halted=false;
 function rejectQueued(){const rest=queue;queue=[];rest.forEach(job=>setTimeout(()=>{if(job.options.fail)job.options.fail('上个原生文件请求未确认，请退出此页后再处理',-2);job.options=null;},0));}
 function compact(method,uri,v){if(method==='list')return {fileList:directory.compact(uri,v&&v.fileList)};if(method==='get')return {type:v&&v.type,subFiles:directory.compact(uri,v&&v.subFiles)};if(method==='readText')return {text:v&&v.text};return {};}
 function pump(){if(halted){rejectQueued();return;}if(active||!queue.length)return;const job=queue.shift();active=job;maxNative=Math.max(maxNative,1);let done=false;const guard=setTimeout(()=>{halted=true;finish(false,'原生文件请求超时，结果未确认',-2);rejectQueued();},timeout);
  function finish(ok,value,code){if(done)return;done=true;clearTimeout(guard);job.ok=ok;job.value=value;job.code=code;setTimeout(deliver,0);}
  const options=Object.assign({},job.options,{complete:function(){},success:v=>{try{finish(true,compact(job.method,job.options.uri,v));}catch(e){finish(false,String(e.message||e),-1);}},fail:(m,c)=>finish(false,m,c)});
  try{native[job.method](options);}catch(e){finish(false,String(e.message||e),-1);}
 }
 function deliver(){const job=active;if(!job)return;active=null;try{if(job.ok){if(job.options.success)job.options.success(job.value);}else if(job.options.fail)job.options.fail(job.value,job.code);}finally{job.options=null;job.value=null;setTimeout(pump,0);}}
 const file={};['list','get','readText','writeText','delete'].forEach(method=>{if(typeof native[method]==='function')file[method]=options=>{queue.push({id:++serial,method:method,options:options});pump();};});
 return {file:file,close:function(){halted=true;rejectQueued();},state:()=>({queued:queue.length,native_inflight:active?1:0,max_native_inflight:maxNative,halted:halted})};
}
module.exports={create:create};
