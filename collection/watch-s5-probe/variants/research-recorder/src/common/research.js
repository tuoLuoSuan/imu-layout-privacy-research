// Portable core: platform APIs are injected. No hardware clock, fsync or background guarantee.
const ROOT = 'internal://files/';
const PREFIX = 's5r_';
const ID = /^[0-9]{1,16}_[a-f0-9]{6}$/;
const DURATIONS = [2, 10, 30, 60, 180, 300];
const INTERVALS = ['game', 'ui', 'normal'];
function finite(n) { return typeof n === 'number' && isFinite(n); }
function ascii(value) { return JSON.stringify(value).replace(/[\u007f-\uffff]/g, c => '\\u' + ('0000' + c.charCodeAt(0).toString(16)).slice(-4)); }
function clone(value) { return JSON.parse(JSON.stringify(value)); }
function validId(id) { if (typeof id !== 'string' || !ID.test(id)) throw Error('无效会话ID'); return id; }
function filename(id, suffix) { return PREFIX + validId(id) + '_' + suffix + '.json'; }
function allowedName(id, name) {
  validId(id);
  if (typeof name !== 'string' || !new RegExp('^'+PREFIX+id+'_(head|tail|trash|purge|b[0-9]{4})\\.json$').test(name)) throw Error('无效会话文件');
  return name;
}
function crc32(text) {
  let crc = -1;
  for (let i = 0; i < text.length; i++) { crc ^= text.charCodeAt(i); for (let j=0;j<8;j++) crc=(crc>>>1)^(0xedb88320&-(crc&1)); }
  return ('00000000' + ((crc ^ -1) >>> 0).toString(16)).slice(-8);
}
function frames(id, part, text) {
  validId(id);
  if (!Number.isInteger(part) || part < 0 || part > 401 || /[^\x00-\x7f]/.test(text) || text.length > 65536) throw Error('导出分段无效');
  const total = Math.max(1,Math.ceil(text.length/300)), sum = crc32(text), out=[];
  for(let i=0;i<total;i++) out.push(['IMUS5','2',id,part,i+1,total,sum,text.slice(i*300,(i+1)*300)].join('|'));
  return out;
}

function createStore(file, env) {
  env = env || {}; const now = env.now || Date.now;
  let active = null, opening = false;
  function call(method, args) {
    return new Promise((resolve,reject) => {
      let done=false;
      const timer=setTimeout(()=>{if(!done){done=true;reject(Error('文件操作超时'));}},8000);
      function finish(error,data){if(done)return;done=true;clearTimeout(timer);error?reject(error):resolve(data);}
      try { file[method](Object.assign({},args,{success:d=>finish(null,d),fail:(m,c)=>finish(Object.assign(Error('文件操作失败 '+c),{code:c}))})); }
      catch(e){finish(e);}
    });
  }
  function directory(){return call('list',{uri:ROOT}).then(d=>d.fileList || []);}
  function read(id,name){
    return Promise.resolve().then(()=>allowedName(id,name)).then(n=>call('readText',{uri:ROOT+n})).then(d=>{
      if(typeof d.text!=='string'||d.text.length>65536)throw Error('会话文件过大或无效');return d.text;
    });
  }
  function parsed(id,name){return read(id,name).then(JSON.parse);}
  function inventory(id){
    return Promise.resolve().then(()=>validId(id)).then(()=>directory()).then(list=>{
      const names=list.map(x=>x.uri.indexOf(ROOT)===0?x.uri.slice(ROOT.length):x.uri).filter(n=>n.indexOf(PREFIX+id+'_')===0);
      if(names.indexOf(filename(id,'purge'))>=0)throw Error('永久删除未完成，请在回收区继续');
      const head=filename(id,'head'),tail=filename(id,'tail');
      if(names.indexOf(head)<0)throw Error('会话元数据缺失');
      const blocks=names.filter(n=>/_b[0-9]{4}\.json$/.test(n)).sort();
      if(blocks.length>400)throw Error('块数量超出边界');
      blocks.forEach((n,i)=>{if(n!==filename(id,'b'+('0000'+i).slice(-4)))throw Error('会话数据块缺失');});
      return {id:id,files:[head].concat(blocks).concat(names.indexOf(tail)>=0?[tail]:[]),trashed:names.indexOf(filename(id,'trash'))>=0};
    });
  }
  function inspect(id){
    return inventory(id).then(inv=>parsed(id,inv.files[0]).then(head=>{
      if(head.kind!=='head'||head.session_id!==id||head.schema_version!==2)throw Error('会话元数据损坏');
      const hasTail=inv.files[inv.files.length-1]===filename(id,'tail');
      return (hasTail?parsed(id,filename(id,'tail')):Promise.resolve(null)).then(tail=>{
        if(tail&&(tail.kind!=='tail'||tail.session_id!==id||tail.blocks!==inv.files.length-2||!tail.quality||!Array.isArray(tail.quality.warnings)||!Number.isInteger(tail.persisted)||tail.persisted<0||tail.persisted>40000))throw Error('封口与块数量不符');
        return {id:id,head:head,tail:tail,trashed:inv.trashed,state:tail?'sealed':'interrupted',count:tail?tail.persisted:null,
          duration_ms:tail?tail.stopped_epoch_ms-head.started_epoch_ms:null,stop_reason:tail?tail.stop_reason:'unknown_interruption'};
      });
    }));
  }
  function list(trashed){
    return directory().then(entries=>{
      const ids=entries.map(x=>x.uri.indexOf(ROOT)===0?x.uri.slice(ROOT.length):x.uri)
        .map(n=>/^s5r_([0-9]{1,16}_[a-f0-9]{6})_head\.json$/.exec(n)).filter(Boolean).map(m=>m[1]).sort().reverse();
      if(ids.length>40)throw Error('超过40条，请先整理记录');
      let chain=Promise.resolve([]);
      ids.forEach(id=>{chain=chain.then(out=>inspect(id).catch(e=>{
        const names=entries.map(x=>x.uri.indexOf(ROOT)===0?x.uri.slice(ROOT.length):x.uri);
        const deleting=names.indexOf(filename(id,'purge'))>=0;
        return {id:id,state:deleting?'deleting':'corrupt',issue:e.message,trashed:deleting||names.indexOf(filename(id,'trash'))>=0,count:null,duration_ms:null};
      }).then(item=>{if(item.trashed===!!trashed)out.push(item);return out;}));});
      return chain;
    });
  }
  function write(id,suffix,value){return call('writeText',{uri:ROOT+filename(id,suffix),text:ascii(value),append:false});}
  const store={list:list,inventory:inventory,readPart:read,inspect:inspect,
    start:function(options,onChange){
      options=options||{};
      return Promise.resolve().then(()=>{
        if(opening || (active && active.state().status!=='sealed'))throw Error('请先保存上一条记录');
        const duration=options.durationSeconds===undefined?2:options.durationSeconds,interval=options.interval||'game';
        if(DURATIONS.indexOf(duration)<0||INTERVALS.indexOf(interval)<0)throw Error('采集设置无效');
        ['participant','room'].forEach(k=>{if(options[k]!==undefined&&options[k]!==null&&!new RegExp(k==='participant'?'^P[0-9]{2}$':'^R[0-9]{2}$').test(options[k]))throw Error('匿名编号无效');});
        if(options.wrist && ['left','right','not_recorded'].indexOf(options.wrist)<0)throw Error('腕侧无效');
        opening=true;
        return directory().then(entries=>{
          const names=entries.map(x=>x.uri.indexOf(ROOT)===0?x.uri.slice(ROOT.length):x.uri);
          if(names.filter(n=>/^s5r_.*_head\.json$/.test(n)).length>=40)throw Error('已达40条，请先整理记录');
          const started=now();if(!finite(started)||started<0)throw Error('回调时钟不可用');
          const id=String(Math.floor(started))+'_'+('000000'+Math.floor(Math.random()*16777216).toString(16)).slice(-6);
          if(names.some(n=>n.indexOf(PREFIX+id+'_')===0))throw Error('会话ID冲突，请重试');
          const head={kind:'head',schema_version:2,session_id:id,started_epoch_ms:started,
            row_fields:['sequence','callback_epoch_ms','x','y','z','page_state'],
            metadata:{app_version:'0.3.0',app_package:'org.imuresearch.s5probe',sensor:'accelerometer',
              device_model_reported:'Xiaomi Watch S5',firmware_reported:'3.102.036',device_metadata_source:'user_report_not_device_query',
              time_source:'Date.now_callback_arrival',hardware_timestamp:false,acceleration_unit:'unknown',axis_convention:'unverified',
              requested_interval:interval,requested_duration_ms:duration*1000,participant:options.participant||null,room:options.room||null,
              wrist:options.wrist||'not_recorded',activity_instruction:options.label||'not_recorded',label_source:'instruction_not_action_truth',
              background_continuity:'unverified',max_buffered_rows:512,block_rows:128}};
          return write(id,'head',head).then(()=>{active=createSession(file,head,now,onChange);return active;});
        }).then(result=>{opening=false;return result;},error=>{opening=false;throw error;});
      });
    },
    trash:function(id){return inspect(id).then(item=>{if(active&&active.state().id===id&&active.state().status!=='sealed')throw Error('采集尚未封口');return write(id,'trash',{session_id:id,trashed_epoch_ms:now()});});},
    restore:function(id){return Promise.resolve().then(()=>validId(id)).then(()=>call('delete',{uri:ROOT+filename(id,'trash')}));},
    purge:function(id,confirmation){
      return Promise.resolve().then(()=>{validId(id);if(confirmation!==id)throw Error('删除确认不匹配');return directory();}).then(entries=>{
        const present=entries.map(x=>x.uri.indexOf(ROOT)===0?x.uri.slice(ROOT.length):x.uri);
        const journal=filename(id,'purge');
        const prepare=present.indexOf(journal)>=0?parsed(id,journal):inspect(id).then(item=>{
          if(!item.trashed)throw Error('请先移到回收区');if(item.state!=='sealed')throw Error('中断记录请先导出，禁止永久删除');
          return inventory(id).then(inv=>{
            const value={session_id:id,files:inv.files.slice(1).reverse().concat([filename(id,'trash'),filename(id,'head')])};
            return write(id,'purge',value).then(()=>value);
          });
        });
        return prepare.then(plan=>{
          if(plan.session_id!==id||!Array.isArray(plan.files)||plan.files.length>403)throw Error('删除清单损坏');
          plan.files.forEach(n=>{allowedName(id,n);if(n===journal)throw Error('删除清单冲突');});
          let chain=Promise.resolve();
          plan.files.concat([journal]).filter(n=>present.indexOf(n)>=0||n===journal).forEach(n=>{
            chain=chain.then(()=>call('delete',{uri:ROOT+n}));
          });return chain;
        });
      });
    }
  };
  return store;
}

function createSession(file,head,now,onChange){
  let status='recording',rows=[],events=[],flight=null,index=0,count=0,persisted=0,previous=null,first=null,last=null;
  let stopReason=null,stopped=null,invalid=0,zero=0,maxGap=0,gaps100=0,gaps1000=0,warnings=[],failure='',timedOut=false;
  let lastFlush=now(),lastTick=lastFlush,lastReceived=lastFlush,tailPending=false;
  const id=head.session_id;
  function warn(w){if(warnings.indexOf(w)<0)warnings.push(w);}
  function state(){return {id:id,status:status,count:count,persisted:persisted,buffered:rows.length+(flight?flight.rows.length:0),
    stop_reason:stopReason,error:failure,warnings:warnings.slice(),invalid_samples:invalid,zero_intervals:zero,max_gap_ms:maxGap,
    measured_callback_hz:first!==null&&last>first?(count-1)*1000/(last-first):null,
    elapsed_ms:(stopped===null?now():stopped)-head.started_epoch_ms,retryable:status==='failed'&&!timedOut};}
  function notify(){if(onChange)onChange(state());}
  function event(type,detail){
    if(status==='sealed')return;
    if(events.length>=32){warn('event_overflow');return;}
    events.push({callback_epoch_ms:now(),type:String(type).slice(0,40),detail:detail===undefined?null:String(detail).slice(0,120)});
  }
  function fail(reason,error,timeout){
    if(status==='sealed'||timedOut)return;
    status='failed';stopReason=reason;stopped=stopped===null?now():stopped;failure=String(error);timedOut=!!timeout;
    warn(reason);event(reason,error);notify();
  }
  function stop(reason){
    if(status!=='recording')return;
    status='stopping';stopReason=reason||'manual';stopped=now();event('stop_requested',stopReason);
    if(['manual','duration'].indexOf(stopReason)<0)warn(stopReason);
    notify();pump();
  }
  function pump(){
    if(status==='failed'||status==='sealed'||tailPending||(flight&&flight.writing))return;
    if(!flight&&(rows.length||events.length)){
      flight={rows:rows.splice(0,128),events:events.splice(0,32),writing:false};
    }
    if(flight){
      const current=flight;
      if(!current.text)current.text=ascii({kind:'block',schema_version:2,session_id:id,index:index,rows:current.rows,events:current.events});
      if(current.text.length>32768){fail('block_too_large','块大小超限');return;}
      current.writing=true;current.started=now();
      try{file.writeText({uri:ROOT+filename(id,'b'+('0000'+index).slice(-4)),text:current.text,append:false,
        success:()=>{
          if(timedOut||flight!==current)return;
          persisted+=current.rows.length;index++;flight=null;lastFlush=now();
          // Yield to platform callbacks instead of a recursive synthetic synchronous writer.
          if(status==='stopping'||rows.length>=128)pump();notify();
        },fail:(m,c)=>{if(timedOut||flight!==current)return;current.writing=false;fail('storage_error','写入失败 '+c);}});}
      catch(e){current.writing=false;fail('storage_error',e.message);}
      return;
    }
    if(status==='stopping'){
      if(!count)warn('no_samples');
      const tail={kind:'tail',schema_version:2,session_id:id,stopped_epoch_ms:stopped,stop_reason:stopReason,count:count,persisted:persisted,blocks:index,
        quality:{warnings:warnings.slice(),invalid_samples:invalid,zero_intervals:zero,max_gap_ms:maxGap,gaps_over_100ms:gaps100,gaps_over_1s:gaps1000,
          classification:'not_hardware_validated',time_basis:'callback_wall_clock',background_verified:false}};
      tailPending=true;lastFlush=now();
      try{file.writeText({uri:ROOT+filename(id,'tail'),text:ascii(tail),append:false,success:()=>{if(timedOut)return;tailPending=false;status='sealed';notify();},
        fail:(m,c)=>{if(timedOut)return;tailPending=false;fail('storage_error','封口失败 '+c);}});}
      catch(e){tailPending=false;fail('storage_error',e.message);}
    }
  }
  event('session_start');
  return {
    state:state,event:event,stop:stop,
    push:function(value,page){
      if(status!=='recording')return false;
      const t=now();if(!finite(t)){invalid++;warn('invalid_samples');return false;}
      if(t<lastTick||(previous!==null&&t<previous)){stop('clock_regression');return false;}
      if(t-head.started_epoch_ms>=head.metadata.requested_duration_ms){stop('duration');return false;}
      lastReceived=t;
      if(!value||!finite(value.x)||!finite(value.y)||!finite(value.z)){invalid++;warn('invalid_samples');return false;}
      if(rows.length+(flight?flight.rows.length:0)>=512){stop('queue_overflow');return false;}
      if(previous!==null){const gap=t-previous;if(gap===0)zero++;if(gap>maxGap)maxGap=gap;if(gap>100)gaps100++;if(gap>1000){gaps1000++;warn('callback_gap_over_1s');}}
      previous=t;last=t;if(first===null)first=t;
      rows.push([count++,t,value.x,value.y,value.z,page==='hidden'?'hidden':'visible']);
      if(count>=40000)stop('sample_limit');else if(rows.length>=128)pump();
      return true;
    },
    tick:function(){
      const t=now();
      if((flight&&flight.writing&&t-flight.started>8000)||(tailPending&&t-lastFlush>8000)){fail('write_timeout','文件回调超过8秒，重开后检查部分记录',true);return;}
      if(status==='recording'){
        if(t<lastTick){stop('clock_regression');return;}lastTick=t;
        if(t-head.started_epoch_ms>=head.metadata.requested_duration_ms){stop('duration');return;}
        if(t-lastReceived>3000){stop('sensor_silence');return;}
        if(t-lastFlush>=2000)pump();
      }
      notify();
    },
    retry:function(){if(status!=='failed'||timedOut)return;status='stopping';failure='';event('save_retry');pump();notify();}
  };
}

module.exports={createStore:createStore,frames:frames,crc32:crc32,ascii:ascii,DURATIONS:DURATIONS,INTERVALS:INTERVALS};
