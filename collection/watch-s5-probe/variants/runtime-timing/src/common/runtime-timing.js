// Bounded Date.now observations on the recorder's existing JS loop, not a profiler or hardware clock.
const NAMES=['callback_body_ms','callback_between_ms','tick_body_ms','tick_entry_gap_ms','tick_between_ms','notify_body_ms','block_encode_ms','write_call_ms','write_ack_ms'];
const BOUNDS=[0,1,5,20,100,500,1000,2000,null];
function finite(n){return typeof n==='number'&&isFinite(n);}
function policy(){return {schema_version:1,mode:'bounded_runtime_observation',clock:'Date.now_wall_clock_not_monotonic',top_limit:5,extra_timers:0,physical_or_hardware_verified:false};}
function create(now){
 const metrics={};let lastCallbackExit=null,lastTickEntry=null,lastTickExit=null,invalidReads=0;
 NAMES.forEach(k=>{metrics[k]={count:0,total_ms:0,max_ms:0,pending:0,invalid:0,histogram:BOUNDS.map(()=>0),top:[]};});
 function read(){try{const t=now();if(finite(t))return t;}catch(e){}invalidReads++;return null;}
 function record(name,start,end,context){
  const m=metrics[name];if(!m)return;
  if(!finite(start)||!finite(end)||end<start){m.invalid++;return;}
  const dt=end-start;m.count++;m.total_ms+=dt;m.max_ms=Math.max(m.max_ms,dt);
  let i=0;while(BOUNDS[i]!==null&&dt>BOUNDS[i])i++;m.histogram[i]++;
  if(m.top.length<5||dt>m.top[m.top.length-1].duration_ms){
   m.top.push({start_epoch_ms:start,end_epoch_ms:end,duration_ms:dt,context:finite(context)?context:null});
   m.top.sort((a,b)=>b.duration_ms-a.duration_ms);if(m.top.length>5)m.top.pop();
  }
 }
 function begin(name,at){if(metrics[name])metrics[name].pending++;return at===undefined?read():at;}
 function end(name,start,at,context){const m=metrics[name];if(!m)return;if(m.pending<=0){m.invalid++;return;}m.pending--;record(name,start,at===undefined?read():at,context);}
 return {begin:begin,end:end,
  callbackEnter:function(count){const at=read();if(lastCallbackExit!==null)record('callback_between_ms',lastCallbackExit,at,count);return begin('callback_body_ms',at);},
  callbackExit:function(start,count){const at=read();end('callback_body_ms',start,at,count);lastCallbackExit=at;},
  tickEnter:function(count){const at=read();if(lastTickEntry!==null)record('tick_entry_gap_ms',lastTickEntry,at,count);if(lastTickExit!==null)record('tick_between_ms',lastTickExit,at,count);lastTickEntry=at;return begin('tick_body_ms',at);},
  tickExit:function(start,count){const at=read();end('tick_body_ms',start,at,count);lastTickExit=at;},
  snapshot:function(){
   const copy={};NAMES.forEach(k=>{const m=metrics[k];copy[k]={count:m.count,total_ms:m.total_ms,max_ms:m.max_ms,pending:m.pending,invalid:m.invalid,histogram:m.histogram.slice(),top:m.top.map(x=>Object.assign({},x))};});
   return {schema_version:1,clock:policy().clock,cutoff:'tail_construction',retention:'summary_histogram_and_top5_per_metric',histogram_upper_bounds_ms:BOUNDS.slice(),invalid_clock_reads:invalidReads,metrics:copy,
    interpretation:'same_JS_loop_and_wall_clock; pending_spans_not_completed; async_ACK_is_not_synchronous_blocking; observation_adds_overhead'};
  }
 };
}
module.exports={create:create,policy:policy};
