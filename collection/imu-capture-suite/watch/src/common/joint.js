// Independent diagnostic. Date.now is callback arrival, not native sampling time.
const capture=require('./sensor-capture.js');
function crc32(text){let c=0xffffffff;for(let i=0;i<text.length;i++){if(text.charCodeAt(i)>127)throw Error('ASCII payload required');c^=text.charCodeAt(i);for(let j=0;j<8;j++)c=(c>>>1)^((c&1)?0xedb88320:0);}return ('00000000'+((c^0xffffffff)>>>0).toString(16)).slice(-8);}
function valid(s){return typeof s==='string'&&/^[A-Za-z0-9_-]{1,64}$/.test(s);}
function create(o){
 const duration=o.requestedDurationMs===undefined?20000:o.requestedDurationMs;
 if(!Number.isInteger(duration)||[20000,60000,120000,300000,600000].indexOf(duration)<0)throw Error('unsupported duration');
 const now=o.now||Date.now,random=o.random||Math.random;let phase='idle',error='',sid='',native='',start=0,stop=0,reason='',driver=null,rows=[],blocks=[],flushed=0;
 let writing=Promise.resolve(),flushDone=false,pending=null,seq=0,observations=0,nextClock=0,nextFlush=0,upload=0,last=0,started=false,sealing=false,sealedTail=null;
 const root='internal://files/';
 function state(){return {phase:phase,error:error,count:rows.length,blocks:blocks.length,sent_blocks:upload,elapsed_ms:start?Math.max(0,(stop||now())-start):0,requested_duration_ms:duration,clock_observations:observations,sid:sid,native_sid:native};}
 function notify(){if(o.onStatus)o.onStatus(state());}
 function fail(e){if(phase==='complete'||phase==='failed')return;error=String(e&&e.message||e);phase='failed';if(driver)driver.stop();pending=null;notify();}
 function call(name,options){return new Promise((resolve,reject)=>{let done=false;const timer=typeof setTimeout==='function'?setTimeout(()=>{if(!done){done=true;reject(Error('本机文件等待超时'));}},8000):null;
  const complete=(f,v)=>{if(done)return;done=true;if(timer!==null)clearTimeout(timer);f(v);};
  try{o.file[name](Object.assign({},options,{success:v=>complete(resolve,v),fail:(m,c)=>complete(reject,Error('文件操作失败 '+m+' '+c))}));}catch(e){complete(reject,e);}
 });}
 function write(suffix,text){return call('writeText',{uri:root+'s5joint_'+sid+'_'+suffix,text:text,append:false});}
 function send(packet,type){if(JSON.stringify(packet).length>1280){fail('本次消息超出已准备长度，部分保留');return;}pending={type:type,packet:packet,at:now()};try{o.send(packet,e=>fail(e||'消息发送失败'));}catch(e){fail(e);}}
 function flush(){
  while(flushed<rows.length){const part=rows.slice(flushed,flushed+8),index=blocks.length,payload=JSON.stringify(part);flushed+=part.length;
   const packet={p:'J_DATA1',sid:sid,native_sid:native,index:index,payload:payload,crc32:crc32(payload)};blocks.push(packet);
   writing=writing.then(()=>write('b'+('0000'+index).slice(-4)+'.json',payload));
  }
  writing=writing.catch(e=>{fail(e);throw e;});return writing;
 }
 function clock(){const t=now();send({p:'J_CLK_REQ1',sid:sid,native_sid:native,seq:seq,w1_ms:t},'clock_reply');nextClock=t+2000;}
 function tail(){const source=driver?driver.state():{},acquisition={};['callback_count','valid_xyz_callbacks','accepted_rows','first_accepted_callback_epoch_ms','last_accepted_callback_epoch_ms','arrival_time_source','hardware_timestamp_verified','unit','axis_convention','cleanup'].forEach(k=>{if(source[k]!==undefined)acquisition[k]=source[k];});return {p:'J_END1',sid:sid,native_sid:native,count:rows.length,blocks:blocks.length,start_ms:start,stop_ms:stop,stop_reason:reason,clock_observations:observations,acquisition:acquisition};}
 function nextUpload(){
  if(phase==='failed'||!flushDone||pending)return;
  if(!sealedTail){if(sealing)return;sealing=true;const value=tail();write('tail.json',JSON.stringify(value)).then(()=>{if(phase==='failed')return;sealedTail=value;sealing=false;nextUpload();}).catch(fail);return;}
  phase='uploading';
  if(upload<blocks.length)send(blocks[upload],'data');else send(sealedTail,'end');notify();
 }
 function finish(why){
  if(phase!=='recording')return;phase='finishing';reason=why;stop=now();if(driver)driver.stop();
  flush().then(()=>{if(phase==='failed')return;flushDone=true;nextUpload();}).catch(fail);notify();
 }
 function begin(arrival){
  phase='opening';start=arrival;
  call('list',{uri:root}).then(result=>{
   if(phase!=='opening')throw Error('本次开始已取消');const list=result&&result.fileList;if(!Array.isArray(list))throw Error('无法核对本机记录目录');
   if(list.some(r=>String(r.uri||r.name||'').indexOf('s5joint_'+sid+'_')>=0))throw Error('本次记录名已存在，未覆盖');
   return write('head.json',JSON.stringify({kind:'head',schema_version:1,sid:sid,native_sid:native,started_epoch_ms:start,requested_duration_ms:duration,app_version:'0.2.2',sensor_path:'generic',requested_interval:'high',acceleration_unit:'unknown',axis_convention:'unverified',hardware_timestamp:false,wrist:'not_recorded'}));
  }).then(()=>{
   if(phase!=='opening')return;phase='recording';nextFlush=now()+1000;last=now();
   driver=capture.create(o.sensor,{now:now,onValue:(p,t)=>{if(phase!=='recording')return false;if(t-start>=duration){finish('duration');return false;}if(rows.length>=20000){fail('本次样本上限，部分保留');return false;}rows.push([rows.length,t,p.x,p.y,p.z]);return true;},onFail:e=>fail(e.message||e)});
   driver.start({sensorPath:'generic',interval:'high'});if(phase==='recording')clock();notify();
  }).catch(fail);
 }
 return {state:state,
  start(){if(started)return;started=true;sid='j_'+now().toString(36)+'_'+Math.floor(random()*0xffffffff).toString(16);phase='connecting';send({p:'J_HELLO1',sid:sid,w1_ms:now(),duration_ms:duration},'hello');notify();},
  receive(value,arrival){
   let p=value;try{if(typeof p==='string')p=JSON.parse(p);else if(p&&typeof p.data==='string')p=JSON.parse(p.data);}catch(e){return;}
   if(!p||!pending||p.sid!==sid)return;if(p.p==='J_ERR1'){fail(p.error||'手机拒绝本次消息');return;}
   if(pending.type==='hello'&&p.p==='J_HELLO_ACK1'){
    if(!valid(p.native_sid)||p.duration_ms!==duration){fail('手机会话身份或时长不符');return;}native=p.native_sid;pending=null;begin(arrival);return;
   }
   if(p.native_sid!==native)return;
   if(pending.type==='clock_reply'&&p.p==='J_CLK_REP1'){
    const req=pending.packet;if(p.seq!==req.seq||p.w1_ms!==req.w1_ms||!Number.isSafeInteger(p.p2_us)||!Number.isSafeInteger(p.p3_us)||p.p3_us<p.p2_us||arrival<req.w1_ms||arrival-req.w1_ms>5000){fail('对时时刻回显无效');return;}
    send({p:'J_CLK_OBS1',sid:sid,native_sid:native,seq:req.seq,w1_ms:req.w1_ms,w4_ms:arrival,p2_us:p.p2_us,p3_us:p.p3_us},'clock_ack');return;
   }
   if(pending.type==='clock_ack'&&p.p==='J_CLK_ACK1'&&p.seq===seq&&p.saved===true){pending=null;seq++;observations++;if(phase==='finishing')nextUpload();notify();return;}
   if(pending.type==='data'&&p.p==='J_DATA_ACK1'&&p.index===upload&&p.crc32===blocks[upload].crc32&&p.saved===true){pending=null;upload++;nextUpload();return;}
   if(pending.type==='end'&&p.p==='J_END_ACK1'&&p.saved===true&&p.count===rows.length){pending=null;phase='complete';notify();}
  },
  tick(){const t=now();if(phase==='failed'||phase==='complete'||phase==='idle')return;if(t<last){fail('回调墙钟倒退，部分保留');return;}last=t;
   if(pending&&t-pending.at>8000){fail('消息等待超时，部分记录保留');return;}
   if(phase==='recording'){if(t-start>=duration){finish('duration');return;}if(t>=nextFlush){flush().catch(fail);nextFlush=t+1000;notify();}if(!pending&&t>=nextClock)clock();}
  },
  stop(why){if(phase==='recording')finish(why==='hidden'?'hidden':'user');else if(['idle','complete','failed','finishing','uploading'].indexOf(phase)<0)fail('开始已取消，已保存部分保留');},
 };
}
module.exports={create:create,crc32:crc32};
