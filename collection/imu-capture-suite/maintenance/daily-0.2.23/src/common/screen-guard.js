// Ordinary screen policy only. API success is not an external screen-power measurement.
function copy(v){return JSON.parse(JSON.stringify(v));}
function create(env){
 env=env||{};const now=env.now||Date.now,later=env.setTimeout||setTimeout,clear=env.clearTimeout||clearTimeout;
 let api=null,attempted=false,cancelled=false,acquirePromise=null,releasePromise=null,lateCleanup=false,acquisitionEstablished=false;
 const report={schema_version:1,mode:'foreground_keep_awake',api:'@system.brightness.setKeepScreenOn',physical_screen_verified:false,
  acquire:{status:'not_requested'},release:{status:'not_requested'},late_release_attempts:0};
 function state(){return copy(report);}
 function failure(message,code){return {message:String(message&&message.message!==undefined?message.message:message).slice(0,160),code:typeof code==='number'&&isFinite(code)?code:typeof code==='string'?code.slice(0,80):null};}
 function request(value,done,late){
  const started=now();let finished=false,timer=null;
  function finish(status,message,code){
   if(finished){if(status==='success'&&value&&late)late();return;}
   finished=true;if(timer!==null)clear(timer);
   const result={status:status,requested_epoch_ms:started,completed_epoch_ms:now()};
   if(status!=='success')result.error=failure(message,code);done(result);
  }
  timer=later(()=>finish('timeout','screen callback timeout'),3000);
  try{api.setKeepScreenOn({keepScreenOn:value,success:()=>finish('success'),fail:(m,c)=>finish('failed',m,c)});}
  catch(e){finish('exception',e);}
 }
 function releaseLateSuccess(){
  if(lateCleanup||!api)return;lateCleanup=true;report.late_release_attempts++;
  request(false,result=>{report.late_release=result;});
 }
 function release(){
  cancelled=true;if(releasePromise)return releasePromise;
  if(!api){report.release={status:'not_requested'};return Promise.resolve(state());}
  report.release={status:'pending'};
  releasePromise=new Promise(resolve=>request(false,result=>{report.release=result;resolve(state());}));
  return releasePromise;
 }
 function acquire(){
  if(acquirePromise)return acquirePromise;
  if(attempted||cancelled)return Promise.reject(Error('保亮已取消，未开始录制'));attempted=true;
  try{api=env.load();if(!api||typeof api.setKeepScreenOn!=='function')throw Error('screen method unavailable');}
  catch(e){api=null;report.acquire={status:'unavailable',error:failure(e)};return Promise.reject(Error('保亮接口不可用，未开始录制'));}
  report.acquire={status:'pending'};
  acquirePromise=new Promise((resolve,reject)=>request(true,result=>{
   report.acquire=result;
   if(result.status!=='success'){reject(Error('保亮请求失败（'+result.status+'），未开始录制'));return;}
   if(cancelled){releaseLateSuccess();reject(Error('保亮已取消，未开始录制'));return;}
   acquisitionEstablished=true;resolve(state());
  },()=>{if(!acquisitionEstablished)releaseLateSuccess();}));
  return acquirePromise;
 }
 return {state:state,acquire:acquire,release:release};
}
module.exports={create:create};
