// All observations share the recorder JS loop and Date.now. No external liveness claim.
function policy(){return {schema_version:1,heartbeat_period_ms:1000,tick_delay_warning_ms:1500,silence_limit_ms:3000,time_basis:'JS_callback_wall_clock',external_liveness_reference:false};}
function create(started,emit){
 const p=policy();let first=null,last=null,acceptedRows=0,lastTick=started,lastHeartbeat=started,ticks=0,beats=0,late=0,maxTickGap=0,maxQuiet=0;
 function quiet(t){return Math.max(0,t-(last===null?started:last));}
 return {
  accepted:function(t,count){maxQuiet=Math.max(maxQuiet,quiet(t));if(first===null)first=t;last=t;acceptedRows=count;},
  tick:function(t,count){
   ticks++;const gap=t-lastTick;maxTickGap=Math.max(maxTickGap,gap);if(gap>p.tick_delay_warning_ms)late++;lastTick=t;
   if(t-lastHeartbeat>=p.heartbeat_period_ms){
    lastHeartbeat=t;beats++;if(emit)emit('capture_heartbeat',JSON.stringify({i:beats,n:count,a:last,g:quiet(t)}),t);
   }
  },
  snapshot:function(t,count){
   const finalQuiet=quiet(t),maxNoAccepted=Math.max(maxQuiet,finalQuiet);
   return {schema_version:1,semantics:'JS_wall_clock_observations_only',accepted_rows:acceptedRows,
    first_accepted_epoch_ms:first,last_accepted_epoch_ms:last,started_epoch_ms:started,stopped_epoch_ms:t,
    start_gap_ms:(first===null?t:first)-started,terminal_gap_ms:finalQuiet,max_no_accepted_gap_ms:maxNoAccepted,
    tick_count:ticks,heartbeat_count:beats,last_tick_epoch_ms:lastTick,max_tick_gap_ms:maxTickGap,
    terminal_tick_gap_ms:Math.max(0,t-lastTick),late_tick_count:late,silence_observed:maxNoAccepted>p.silence_limit_ms,
    external_liveness_reference:false};
  }
 };
}
module.exports={create:create,policy:policy};
