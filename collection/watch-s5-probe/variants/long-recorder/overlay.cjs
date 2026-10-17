// Independent 0.4.8: only the 1800-second option uses the longer timed flush.
function once(source,from,to){
  if(source.split(from).length!==2)throw Error('Long recorder marker mismatch: '+from.slice(0,90));
  return source.replace(from,to);
}
function core(source){
  let out=once(source,"app_version:'0.4.7'","app_version:'0.4.8'");
  out=once(out,'const DURATIONS = [2, 10, 30, 60, 180, 300];','const DURATIONS = [2, 10, 30, 60, 180, 300, 1800];');
  out=once(out,"background_continuity:'unverified',max_buffered_rows:512,block_rows:128}};",
    "background_continuity:'unverified',max_buffered_rows:512,block_rows:128,storage_policy:{schema_version:1,row_trigger:128,timed_flush_ms:duration===1800?8000:2000,write_timeout_ms:8000,max_buffered_rows:512,semantics:'JS_scheduling_dependent_no_durability_guarantee'}}};");
  out=once(out,'if(t-lastFlush>=2000)pump();',
    'if(t-lastFlush>=head.metadata.storage_policy.timed_flush_ms)pump();');
  return out;
}
function page(source){
  let out=once(source,'v0.4.7','v0.4.8');
  out=once(out,'[2,10,30,60,180,300]','[2,10,30,60,180,300,1800]');
  out=once(out,"i===0?String(value)+' 秒'", "i===0?(value>=60?String(value/60)+' 分钟':String(value)+' 秒')");
  out=once(out,'{{durationSeconds}}秒',"{{durationSeconds >= 60 ? (durationSeconds / 60) + '分钟' : durationSeconds + '秒'}}");
  return out;
}
module.exports={core,page};
