// Explicit report dispatch policy only; raw callback capture and final report shape stay intact.
function once(s,a,b){if(s.split(a).length!==2)throw Error('Lifecycle reporting marker mismatch: '+a.slice(0,90));return s.replace(a,b);}
function core(s){
 s=once(s,"app_version:'0.4.11'","app_version:'0.4.12'");
 return once(s,"background_continuity:'unverified',runtime_timing_policy:",
  "background_continuity:'unverified',acquisition_reporting_policy:options.inputProbe===true?null:{schema_version:1,mode:'lifecycle_only',raw_callback_capture:'unchanged',final_report:'before_seal'},runtime_timing_policy:");
}
function sensor(s){
 s=once(s,'env=env||{};const now=env.now||Date.now;',
  "env=env||{};const reportMode=env.reportMode===undefined?'per_callback':env.reportMode;if(['per_callback','lifecycle_only'].indexOf(reportMode)<0)throw Error('unknown acquisition report mode');const now=env.now||Date.now;");
 return once(s,'inCallback=false;clean();notify();if(timing)',"inCallback=false;clean();if(reportMode==='per_callback'||stopWanted)notify();if(timing)");
}
function page(s){
 s=once(s,'v0.4.11','v0.4.12');
 return once(s,'sensorCapture.create(sensor,{now:Date.now,runtimeTiming:',"sensorCapture.create(sensor,{now:Date.now,reportMode:'lifecycle_only',runtimeTiming:");
}
module.exports={core,sensor,page};
