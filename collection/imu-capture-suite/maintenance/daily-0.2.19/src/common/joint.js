// Independent diagnostic. Date.now is callback arrival, not native sampling time.
const capture=require('./sensor-capture.js');
function crc32(text){let c=0xffffffff;for(let i=0;i<text.length;i++){if(text.charCodeAt(i)>127)throw Error('ASCII payload required');c^=text.charCodeAt(i);for(let j=0;j<8;j++)c=(c>>>1)^((c&1)?0xedb88320:0);}return ('00000000'+((c^0xffffffff)>>>0).toString(16)).slice(-8);}
function valid(s){return typeof s==='string'&&/^[A-Za-z0-9_-]{1,64}$/.test(s);}
function create(o){
 const duration=o.requestedDurationMs===undefined?20000:o.requestedDurationMs;
 if(!Number.isInteger(duration)||[20000,60000,120000,300000,600000].indexOf(duration)<0)throw Error('unsupported duration');
 const now=o.now||Date.now,random=o.random||Math.random,schedule=typeof o.setTimeout==='function'?o.setTimeout:setTimeout,unschedule=typeof o.clearTimeout==='function'?o.clearTimeout:clearTimeout;let phase='idle',error='',sid='',native='',start=0,stop=0,reason='',driver=null,rows=[],blocks=[],flushed=0;
 let writing=Promise.resolve(),flushDone=false,pending=null,seq=0,observations=0,nextClock=0,nextFlush=0,upload=0,last=0,started=false,sealing=false,sealedTail=null,lastStage='unknown',lastUri='',failureNotified=false,failureAttempted=false;
 const root='internal://files/';let sessionRoot='',fileOperation='',fileWaitMs=0;
 function state(){return {phase:phase,error:error,stage:lastStage,uri:lastUri,file_operation:fileOperation,file_wait_ms:fileWaitMs,session_root_uri:sessionRoot,failure_notified:failureNotified,failure_notification_attempted:failureAttempted,count:rows.length,blocks:blocks.length,sent_blocks:upload,elapsed_ms:start?Math.max(0,(stop||now())-start):0,requested_duration_ms:duration,clock_observations:observations,sid:sid,native_sid:native};}
 function notify(){if(o.onStatus)o.onStatus(state());}
 // At most 216 UTF-8 bytes; avoid splitting or emitting lone surrogate units.
 function failurePacket(){return {p:'J_FAIL1',sid:sid,native_sid:native,stage:lastStage,error:String(error).slice(0,72).replace(/[\uD800-\uDFFF]/g,'?'),count:rows.length,blocks:blocks.length,start_ms:start,stop_ms:stop||now(),stop_reason:'failure'};}
 function fail(e,stage){if(phase==='complete'||phase==='failed')return;if(stage)lastStage=stage;if(e&&e.stage)lastStage=e.stage;error=String(e&&e.message||e);phase='failed';if(!stop)stop=now();if(driver)driver.stop();pending=null;
  if(native&&sid&&!failureAttempted){failureAttempted=true;try{o.send(failurePacket(),()=>{});}catch(_){}}
  notify();}
 function call(name,options,stage){return new Promise((resolve,reject)=>{let done=false;const opStage=stage||name,startedAt=now();lastStage=opStage;fileOperation=name;fileWaitMs=0;lastUri=options&&options.uri?String(options.uri):'';if(phase==='opening')notify();const timer=typeof schedule==='function'?schedule(()=>{if(!done){done=true;fileWaitMs=Math.max(0,now()-startedAt);const e=Error('本机文件等待超时（'+opStage+'/'+name+'）');e.stage=opStage;reject(e);}},8000):null;
  const complete=(f,v)=>{if(done)return;done=true;fileWaitMs=Math.max(0,now()-startedAt);if(timer!==null&&typeof unschedule==='function')unschedule(timer);f(v);};
  try{if(typeof o.file[name]!=='function')throw Error('文件接口不可用（'+name+'）');o.file[name](Object.assign({},options,{success:v=>complete(resolve,v),fail:(m,c)=>{const e=Error('文件操作失败（'+opStage+'/'+name+'） '+m+' '+c);e.stage=opStage;complete(reject,e);}}));}catch(e){e.stage=opStage;complete(reject,e);}
 });}
 function write(suffix,text,stage){return call('writeText',{uri:sessionRoot+'s5joint_'+sid+'_'+suffix,text:text,append:false},stage);}
 function send(packet,type){if(JSON.stringify(packet).length>1280){fail('本次消息超出已准备长度，部分保留','transport');return;}pending={type:type,packet:packet,at:now()};try{o.send(packet,e=>fail(e||'消息发送失败','transport'));}catch(e){fail(e,'transport');}}
 function flush(){
  while(flushed<rows.length){const part=rows.slice(flushed,flushed+8),index=blocks.length,payload=JSON.stringify(part);flushed+=part.length;
   const packet={p:'J_DATA1',sid:sid,native_sid:native,index:index,payload:payload,crc32:crc32(payload)};blocks.push(packet);
   writing=writing.then(()=>{if(phase==='failed')return;return write('b'+('0000'+index).slice(-4)+'.json',payload,'block');});
  }
  writing=writing.catch(e=>{fail(e,'block');throw e;});return writing;
 }
 function clock(){const t=now();send({p:'J_CLK_REQ1',sid:sid,native_sid:native,seq:seq,w1_ms:t},'clock_reply');nextClock=t+2000;}
 function tail(){const source=driver?driver.state():{},acquisition={};['callback_count','valid_xyz_callbacks','accepted_rows','first_accepted_callback_epoch_ms','last_accepted_callback_epoch_ms','arrival_time_source','hardware_timestamp_verified','unit','axis_convention','cleanup'].forEach(k=>{if(source[k]!==undefined)acquisition[k]=source[k];});return {p:'J_END1',sid:sid,native_sid:native,count:rows.length,blocks:blocks.length,start_ms:start,stop_ms:stop,stop_reason:reason,clock_observations:observations,acquisition:acquisition};}
 function nextUpload(){
  if(phase==='failed'||!flushDone||pending)return;
  if(!sealedTail){if(sealing)return;sealing=true;const value=tail();write('tail.json',JSON.stringify(value),'tail').then(()=>{if(phase==='failed')return;sealedTail=value;sealing=false;nextUpload();}).catch(fail);return;}
  phase='uploading';
  if(upload<blocks.length)send(blocks[upload],'data');else send(sealedTail,'end');notify();
 }
 function finish(why){
  if(phase!=='recording')return;phase='finishing';reason=why;stop=now();if(driver)driver.stop();
  flush().then(()=>{if(phase==='failed')return;flushDone=true;nextUpload();}).catch(fail);notify();
 }
 function begin(arrival){
  phase='opening';start=arrival;sessionRoot=root+'s5joint_'+native+'_'+sid+'/';
  // mkdir can succeed for an existing directory: it is not an exclusive-create lock.
  // Check only this session directory and refuse every nonempty result before writing.
  call('mkdir',{uri:sessionRoot,recursive:false},'mkdir').then(()=>{
   if(phase!=='opening')throw Error('本次开始已取消');return call('list',{uri:sessionRoot},'list');
  }).then(result=>{
   if(phase!=='opening')throw Error('本次开始已取消');const list=result&&result.fileList;if(!Array.isArray(list))throw Error('无法核对本机记录目录');
   if(list.length!==0)throw Error('本次记录目录非空，未覆盖');
   return write('head.json',JSON.stringify({kind:'head',schema_version:1,sid:sid,native_sid:native,started_epoch_ms:start,requested_duration_ms:duration,app_version:'0.2.19',storage_strategy:'isolated_session_directory',storage_root_uri:sessionRoot,sensor_path:'generic',requested_interval:'high',acceleration_unit:'unknown',axis_convention:'unverified',hardware_timestamp:false,wrist:'not_recorded'}),'head');
  }).then(()=>{
   if(phase!=='opening')return;phase='recording';nextFlush=now()+1000;last=now();
   driver=capture.create(o.sensor,{now:now,onValue:(p,t)=>{if(phase!=='recording')return false;if(t-start>=duration){finish('duration');return false;}if(rows.length>=20000){fail('本次样本上限，部分保留','sensor');return false;}rows.push([rows.length,t,p.x,p.y,p.z]);return true;},onFail:e=>fail(e.message||e,'sensor')});
   driver.start({sensorPath:'generic',interval:'high'});if(phase==='recording')clock();notify();
  }).catch(fail);
 }
 return {state:state,
  start(){if(started)return;started=true;sid='j_'+now().toString(36)+'_'+Math.floor(random()*0xffffffff).toString(16);phase='connecting';send({p:'J_HELLO1',sid:sid,w1_ms:now(),duration_ms:duration},'hello');notify();},
  receive(value,arrival){
   let p=value;try{if(typeof p==='string')p=JSON.parse(p);else if(p&&typeof p.data==='string')p=JSON.parse(p.data);}catch(e){return;}
   if(phase==='failed'){if(failureAttempted&&p&&p.p==='J_FAIL_ACK1'&&p.sid===sid&&p.native_sid===native&&p.saved===true&&!failureNotified){failureNotified=true;notify();}return;}
   if(phase==='complete')return;
   if(!p||!pending||p.sid!==sid)return;if(p.p==='J_ERR1'){fail(p.error||'手机拒绝本次消息','transport');return;}
   if(pending.type==='hello'&&p.p==='J_HELLO_ACK1'){
    if(!valid(p.native_sid)||p.duration_ms!==duration){fail('手机会话身份或时长不符','hello');return;}native=p.native_sid;pending=null;begin(arrival);return;
   }
   if(p.native_sid!==native)return;
   if(pending.type==='clock_reply'&&p.p==='J_CLK_REP1'){
    const req=pending.packet;if(p.seq!==req.seq||p.w1_ms!==req.w1_ms||!Number.isSafeInteger(p.p2_us)||!Number.isSafeInteger(p.p3_us)||p.p3_us<p.p2_us||arrival<req.w1_ms||arrival-req.w1_ms>5000){fail('对时时刻回显无效','clock');return;}
    send({p:'J_CLK_OBS1',sid:sid,native_sid:native,seq:req.seq,w1_ms:req.w1_ms,w4_ms:arrival,p2_us:p.p2_us,p3_us:p.p3_us},'clock_ack');return;
   }
   if(pending.type==='clock_ack'&&p.p==='J_CLK_ACK1'&&p.seq===seq&&p.saved===true){pending=null;seq++;observations++;if(phase==='finishing')nextUpload();notify();return;}
   if(pending.type==='data'&&p.p==='J_DATA_ACK1'&&p.index===upload&&p.crc32===blocks[upload].crc32&&p.saved===true){pending=null;upload++;nextUpload();return;}
   if(pending.type==='end'&&p.p==='J_END_ACK1'&&p.saved===true&&p.count===rows.length){pending=null;phase='complete';notify();}
  },
  tick(){const t=now();if(phase==='failed'||phase==='complete'||phase==='idle')return;if(t<last){fail('回调墙钟倒退，部分保留','tick');return;}last=t;
   if(pending&&t-pending.at>8000){fail('消息等待超时，部分记录保留','transport');return;}
   if(phase==='recording'){if(t-start>=duration){finish('duration');return;}if(t>=nextFlush){flush().catch(fail);nextFlush=t+1000;notify();}if(!pending&&t>=nextClock)clock();}
  },
  stop(why){if(phase==='recording')finish(why==='hidden'?'hidden':'user');else if(['idle','complete','failed','finishing','uploading'].indexOf(phase)<0)fail('开始已取消，已保存部分保留','cancel');},
 };
}
module.exports={create:create,crc32:crc32};
