function once(s,a,b){if(s.split(a).length!==2)throw Error('Runtime timing marker mismatch: '+a.slice(0,90));return s.replace(a,b);}
function core(s){
 s=once(s,"app_version:'0.4.9'","app_version:'0.4.10'");
 s=once(s,"const continuityObserver = require('./continuity-observer.js');","const continuityObserver = require('./continuity-observer.js');\nconst runtimeTiming = require('./runtime-timing.js');");
 s=once(s,"background_continuity:'unverified',max_buffered_rows:512,block_rows:128,storage_policy:","background_continuity:'unverified',runtime_timing_policy:runtimeTiming.policy(),max_buffered_rows:512,block_rows:128,storage_policy:");
 s=once(s,'const id=head.session_id;const continuity=','const timing=runtimeTiming.create(now);const id=head.session_id;const continuity=');
 s=once(s,'function notify(){if(onChange)onChange(state());}',"function notify(){if(onChange){const at=timing.begin('notify_body_ms');try{onChange(state());}finally{timing.end('notify_body_ms',at,now(),count);}}}");
 s=once(s,"if(!current.text)current.text=ascii({kind:'block',schema_version:2,session_id:id,index:index,rows:current.rows,events:current.events});","if(!current.text){const at=timing.begin('block_encode_ms');try{current.text=ascii({kind:'block',schema_version:2,session_id:id,index:index,rows:current.rows,events:current.events});}finally{timing.end('block_encode_ms',at,now(),index);}}");
 s=once(s,'current.writing=true;current.started=now();',"current.writing=true;current.started=now();current.timingIndex=index;timing.begin('write_ack_ms',current.started);const callAt=timing.begin('write_call_ms',current.started);");
 s=once(s,'if(timedOut||flight!==current)return;\n          persisted+=',"if(timedOut||flight!==current)return;\n          timing.end('write_ack_ms',current.started,now(),current.timingIndex);\n          persisted+=");
 s=once(s,"fail:(m,c)=>{if(timedOut||flight!==current)return;current.writing=false;fail('storage_error','写入失败 '+c);}});}","fail:(m,c)=>{if(timedOut||flight!==current)return;timing.end('write_ack_ms',current.started,now(),current.timingIndex);current.writing=false;fail('storage_error','写入失败 '+c);}});}");
 s=once(s,"catch(e){current.writing=false;fail('storage_error',e.message);}","catch(e){timing.end('write_ack_ms',current.started,now(),current.timingIndex);current.writing=false;fail('storage_error',e.message);}\n      finally{timing.end('write_call_ms',callAt,now(),current.timingIndex);}");
 s=once(s,'tail.continuity_observation=continuity.snapshot(stopped,count);','tail.continuity_observation=continuity.snapshot(stopped,count);\n      tail.runtime_timing_observation=timing.snapshot();');
 s=once(s,'state:state,event:event,stop:stop,','state:state,event:event,stop:stop,runtimeTiming:function(){return timing;},');
 s=once(s,'tick:function(){\n      const t=now();',"tick:function(){\n      const tickAt=timing.tickEnter(count);try{\n      const t=now();");
 s=once(s,"      notify();\n    },\n    retry:function()", "      notify();\n      }finally{timing.tickExit(tickAt,count);}\n    },\n    retry:function()");
 return s;
}
function sensor(s){
 s=once(s,'if(stopWanted)return;inCallback=true;if(env.beforeCallback)env.beforeCallback();',"if(stopWanted)return;inCallback=true;if(env.beforeCallback)env.beforeCallback();\n  const timing=env.runtimeTiming,bodyAt=timing?timing.callbackEnter(r.callback_count):null;");
 return once(s,'finally{inCallback=false;clean();notify();if(env.afterCallback)env.afterCallback();}',"finally{inCallback=false;clean();notify();if(timing)timing.callbackExit(bodyAt,r.callback_count);if(env.afterCallback)env.afterCallback();}");
}
function page(s){s=once(s,'v0.4.9','v0.4.10');return once(s,'sensorCapture.create(sensor,{now:Date.now,onValue:','sensorCapture.create(sensor,{now:Date.now,runtimeTiming:s.runtimeTiming(),onValue:');}
module.exports={core,sensor,page};
