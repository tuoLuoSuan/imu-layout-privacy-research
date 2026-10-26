// Uses only the selected ordinary accelerometer API. No polling, rounding or auto-fallback.
function finite(n){return typeof n==='number'&&isFinite(n);}
function clone(v){return JSON.parse(JSON.stringify(v));}
function asciiLength(s){return s.replace(/[\u007f-\uffff]/g,c=>'\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4)).length;}
function snapshot(v){
 let nodes=0;const text=JSON.stringify(v,(k,x)=>{if(++nodes>96||typeof x==='undefined'||typeof x==='function'||typeof x==='symbol'||typeof x==='bigint'||(typeof x==='number'&&!finite(x)))throw Error('non-finite or unsupported callback JSON');return x;});
 if(typeof text!=='string'||asciiLength(text)>2048)throw Error('callback snapshot exceeds 2KiB');return text;
}
function errorValue(message,code){
 const text=String(message&&message.message!==undefined?message.message:message),c=typeof code==='string'?code:null;
 return {message:text.slice(0,512),message_truncated:text.length>512,code:finite(code)?code:c===null?null:c.slice(0,256),code_truncated:c!==null&&c.length>256};
}
function create(sensor,env){
 env=env||{};const now=env.now||Date.now;let attempted=false,inCall=false,inCallback=false,stopWanted=false,subscribed=false,handle=null,cleaned=false;
 const r={schema_version:1,status:'idle',sensor_path:null,api:null,requested_interval:null,accelerometer_type:null,subscribe_return:null,
  callback_count:0,valid_xyz_callbacks:0,accepted_rows:0,fractional_xyz_scalars:0,
  first_callback_json:null,last_callback_json:null,first_accepted_callback_epoch_ms:null,last_accepted_callback_epoch_ms:null,
  rejected_callback_json:null,error:null,cleanup:{status:'not_subscribed'},arrival_time_source:'Date.now_callback_arrival',
  hardware_timestamp_verified:false,unit:'unknown',axis_convention:'unverified'};
 function state(){return clone(r);}
 function notify(){if(env.onChange)env.onChange(state());}
 function clean(){
  if(!stopWanted||cleaned)return;
  if(inCall||inCallback){r.cleanup={status:'pending_native_return'};return;}
  cleaned=true;
  if(subscribed){
   if(r.sensor_path==='generic'&&handle===null)r.cleanup={status:'handle_unavailable'};
   else try{if(r.sensor_path==='generic')sensor.unsubscribe(handle);else sensor.unsubscribeAccelerometer();r.cleanup={status:'unsubscribe_returned',handle:handle};}
    catch(e){r.cleanup={status:'unsubscribe_exception',handle:handle,error:errorValue(e)};}
  }
  r.status=r.error?'failed':'stopped';notify();
 }
 function stop(){stopWanted=true;clean();return state();}
 function fail(message,code){
  if(r.error)return;r.error=errorValue(message,code);stopWanted=true;r.status='failed';clean();notify();if(env.onFail)env.onFail(clone(r.error));
 }
 function callback(value){
  if(stopWanted)return;inCallback=true;if(env.beforeCallback)env.beforeCallback();
  try{
   const t=now();r.callback_count++;
   if(!finite(t)){fail('callback wall clock unavailable');return;}
   let raw;
   try{raw=snapshot(value);}catch(e){fail(e);return;}
   const copy=JSON.parse(raw);let p=copy;
   if(r.sensor_path==='generic'){
    p=copy&&copy.ACCELEROMETER;
    if(!copy||Array.isArray(copy)||Object.keys(copy).length!==1||!p||Array.isArray(p)||Object.keys(p).sort().join(',')!=='x,y,z'){
     r.rejected_callback_json=raw;fail('generic callback shape changed');return;
    }
   }
   if(!p||!['x','y','z'].every(k=>finite(p[k]))){r.rejected_callback_json=raw;fail('invalid accelerometer XYZ');return;}
   r.valid_xyz_callbacks++;
   const accepted=env.onValue?env.onValue(p,t)!==false:true;
   if(accepted){
    r.accepted_rows++;r.fractional_xyz_scalars+=['x','y','z'].filter(k=>p[k]!==Math.floor(p[k])).length;
    if(r.first_callback_json===null){r.first_callback_json=raw;r.first_accepted_callback_epoch_ms=t;}
    r.last_callback_json=raw;r.last_accepted_callback_epoch_ms=t;
   }else stopWanted=true;
  }catch(e){fail(e);}
  finally{inCallback=false;clean();notify();if(env.afterCallback)env.afterCallback();}
 }
 return {state:state,stop:stop,start:function(options){
  if(attempted)throw Error('capture subscription already attempted');attempted=true;
  options=options||{};r.sensor_path=options.sensorPath;r.requested_interval=options.interval;
  const generic=options.sensorPath==='generic',legacy=options.sensorPath==='legacy';r.api=generic?'@system.sensor.subscribe':legacy?'@system.sensor.subscribeAccelerometer':null;
  if((!generic&&!legacy)||(generic?['high','mid','low']:['game','ui','normal']).indexOf(options.interval)<0){fail('API and requested interval mismatch');return state();}
  r.status='starting';inCall=true;
  try{
   if(generic){
    if(typeof sensor.subscribe!=='function'||typeof sensor.unsubscribe!=='function')throw Error('generic subscribe/unsubscribe unavailable');
    const types=sensor.DATA_TYPES,type=types&&types.ACCELEROMETER;
    if(!Number.isSafeInteger(type)||type<0)throw Error('ACCELEROMETER constant unavailable');r.accelerometer_type=type;subscribed=true;
    const ret=sensor.subscribe({type:type,interval:options.interval,reserved:false,callback:callback,fail:fail});
    r.subscribe_return={type:typeof ret,value:finite(ret)?ret:null};
    if(Number.isSafeInteger(ret)&&ret>=0)handle=ret;else fail('generic returned invalid subscription handle');
   }else{
    if(typeof sensor.subscribeAccelerometer!=='function'||typeof sensor.unsubscribeAccelerometer!=='function')throw Error('dedicated accelerometer unavailable');
    subscribed=true;sensor.subscribeAccelerometer({interval:options.interval,callback:callback,fail:fail});r.subscribe_return={type:'void',value:null};
   }
  }catch(e){fail(e);}
  finally{inCall=false;if(!stopWanted)r.status='active';clean();notify();}
  return state();
 }};
}
module.exports={create:create};
