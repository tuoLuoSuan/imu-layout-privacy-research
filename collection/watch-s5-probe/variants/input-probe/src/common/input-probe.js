// Ordinary JS-facing input observation. No sensor identity/precision/time claims from typeof.
const MAX_CALLBACKS=128,MAX_RAW=2048,MAX_TOTAL=24576;
function finite(v){return typeof v==='number'&&isFinite(v);}
function text(v){try{return String(v);}catch(e){return '[unprintable]';}}
function errorValue(message,code){
 const raw=text(message&&message.message!==undefined?message.message:message);
 return {message:raw.slice(0,2048),message_truncated:raw.length>2048,code:finite(code)?code:typeof code==='string'?code.slice(0,2048):null,code_truncated:typeof code==='string'&&code.length>2048};
}
function inspect(sensor){
 const d={method_types:{},accelerometer_type:null,eligible:false,issues:[]};
 ['subscribe','unsubscribe','subscribeAccelerometer','unsubscribeAccelerometer','getRecentData','checkAvailable'].forEach(k=>{
  try{d.method_types[k]=typeof sensor[k];}catch(e){d.method_types[k]='getter_error';d.issues.push({field:k,error:errorValue(e)});}
 });
 try{const types=sensor.DATA_TYPES;d.data_types_type=typeof types;
  if(types&&Number.isSafeInteger(types.ACCELEROMETER)&&types.ACCELEROMETER>=0)d.accelerometer_type=types.ACCELEROMETER;
 }catch(e){d.issues.push({field:'DATA_TYPES',error:errorValue(e)});}
 d.eligible=d.method_types.subscribe==='function'&&d.method_types.unsubscribe==='function'&&d.accelerometer_type!==null;
 return d;
}
function asciiLength(s){return s.replace(/[\u007f-\uffff]/g,c=>'\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4)).length;}
function snapshot(value){
 let nodes=0;
 const out=JSON.stringify(value,function(k,v){
  if(++nodes>128||typeof v==='undefined'||typeof v==='function'||typeof v==='symbol'||typeof v==='bigint'||(typeof v==='number'&&!finite(v)))throw Error('callback is not bounded finite JSON');
  return v;
 });
 if(typeof out!=='string')throw Error('callback is not JSON');return out;
}
function xyz(value){
 if(!value||typeof value!=='object'||Array.isArray(value))return null;
 const p=['x','y','z'].every(k=>finite(value[k]))?value:value.ACCELEROMETER;
 return p&&['x','y','z'].every(k=>finite(p[k]))?p:null;
}
function create(env){
 const now=env.now||Date.now,sensor=env.sensor;let attempted=false,session=null,phase='idle',inCall=false,handle=null,started=null,rawBytes=0;
 let requestedEnd=null,finished=false;
 const report={schema_version:1,api:'@system.sensor.subscribe',requested_interval:'high',requested_duration_ms:2000,
  declaration:env.declaration||null,result:'not_started',callbacks:[],subscribe_return:null,error:null,
  cleanup:{status:'not_subscribed'},raw_json_ascii_budget:MAX_TOTAL,max_callbacks:MAX_CALLBACKS,
  arrival_time_source:'Date.now_callback_arrival',performance_clock_semantics:'runtime_api_not_hardware_or_cross_device_verified',
  hardware_time_semantics:'unverified',batching_semantics:'native_batch_boundaries_not_exposed_by_callback',unit:'unknown',axis_convention:'unverified'};
 function state(){return {phase:phase,result:report.result,callbacks:report.callbacks.length,eligible:!!(report.declaration&&report.declaration.eligible),error:report.error,session_id:session?session.state().id:null};}
 function notify(){if(env.onState)env.onState(state());}
 function finish(reason){
  if(finished)return;if(!requestedEnd)requestedEnd=reason;
  if(!session||inCall)return;
  finished=true;report.result=requestedEnd;report.stopped_callback_epoch_ms=now();
  if(handle!==null){try{sensor.unsubscribe(handle);report.cleanup={status:'unsubscribe_returned',handle:handle};}
   catch(e){report.cleanup={status:'unsubscribe_exception',handle:handle,error:errorValue(e)};}}
  else if(report.subscribe_return)report.cleanup={status:'handle_unavailable'};
  phase='saving';session.setInputProbe(report);session.stop(report.result==='completed'?'duration':'input_'+report.result);notify();
 }
 function callback(value){
  if(finished||requestedEnd)return;
  const t=now();if(!finite(t)||t<started){finish('clock_regression');return;}
  if(t-started>=2000){finish(report.callbacks.length?'completed':'no_callbacks');return;}
  let raw;
  try{raw=snapshot(value);}catch(e){report.error=errorValue(e);finish('raw_not_json');return;}
  const bytes=asciiLength(raw);
  if(bytes>MAX_RAW||rawBytes+bytes>MAX_TOTAL){report.rejected_raw_ascii_bytes=bytes;finish('raw_budget_exceeded');return;}
  let mono=null;
  if(typeof env.monotonic==='function')try{const m=env.monotonic();if(finite(m))mono=m;else report.performance_read_error='non_finite';}
   catch(e){report.performance_read_error=errorValue(e);}
  const copy=JSON.parse(raw),p=xyz(copy);
  const observation={callback_index:report.callbacks.length,callback_epoch_ms:t,performance_now_ms:mono,raw_json:raw,row_sequence:null};
  rawBytes+=bytes;report.callbacks.push(observation);
  if(asciiLength(JSON.stringify(report))>43008){report.callbacks.pop();rawBytes-=bytes;finish('report_budget_exceeded');return;}
  if(!p){finish('unknown_shape');return;}
  observation.row_sequence=session.state().count;
  if(!session.push(p,env.pageState?env.pageState():'visible',t)){observation.row_sequence=null;finish('row_rejected');return;}
  if(report.callbacks.length>=MAX_CALLBACKS)finish('callback_limit');else notify();
 }
 return {state:state,stop:finish,
  start:function(){
   if(attempted)return Promise.reject(Error('input candidate runs only once per app launch'));
   attempted=true;phase='preparing';notify();
   return env.store.start({durationSeconds:2,interval:'game',inputProbe:true},s=>{
    if(s.status==='failed'){phase='storage_failed';notify();}
    if(s.status==='sealed'){phase='complete';notify();}
   }).then(s=>{
    session=s;started=now()-s.state().elapsed_ms;
    if(!report.declaration)report.declaration=inspect(sensor);
    if(requestedEnd){finish(requestedEnd);return;}
    if(!report.declaration.eligible){finish('unavailable');return;}
    report.started_callback_epoch_ms=now();
    if(report.started_callback_epoch_ms-started>=2000){finish('setup_timeout');return;}
    report.result='running';phase='running';inCall=true;
    try{
     const returned=sensor.subscribe({type:report.declaration.accelerometer_type,interval:'high',reserved:false,callback:callback,
      fail:(message,code)=>{if(finished||requestedEnd)return;report.error=errorValue(message,code);finish('native_fail');}});
     report.subscribe_return={type:typeof returned,value:finite(returned)?returned:null};
     if(Number.isSafeInteger(returned)&&returned>=0)handle=returned;
     else if(!requestedEnd)requestedEnd='invalid_handle';
    }catch(e){report.error=errorValue(e);requestedEnd=requestedEnd||'native_exception';}
    inCall=false;if(requestedEnd)finish(requestedEnd);else notify();
   }).catch(e=>{phase='storage_failed';report.error=errorValue(e);notify();throw e;});
  },
  tick:function(){
   if(phase==='running'&&!finished){const t=now();
    if(t<started)finish('clock_regression');else if(t-started>=2000)finish(report.callbacks.length?'completed':'no_callbacks');
   }
   if(session)session.tick();
  }
 };
}
module.exports={inspect:inspect,create:create};
