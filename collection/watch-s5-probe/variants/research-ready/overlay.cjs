// Engineering startup guard and truthful display cache; no sensor resubscription.
function one(s,a,b){if(s.split(a).length!==2)throw Error('Research-ready marker mismatch: '+a.slice(0,90));return s.replace(a,b);}
const POLICY="{schema_version:1,mode:'stop_and_preserve_slow_high_start',check_after_ms:5000,minimum_callback_span_ms:2500,minimum_arrival_per_second:10,applies_to:'generic_high_duration_at_least_10s',rate_semantics:'JS_callback_arrival_not_hardware_or_research_gate',retry:'none'}";
function core(s){
 s=one(s,"app_version:'0.4.12'","app_version:'0.4.13'");
 s=one(s,"background_continuity:'unverified',acquisition_reporting_policy:","background_continuity:'unverified',startup_rate_policy:options.inputProbe===true?null:"+POLICY+",acquisition_reporting_policy:");
 s=one(s,"reject(Error('文件操作超时'));}},8000);","reject(Error('文件操作超时'));}},method==='list'||method==='readText'?30000:8000);");
 s=one(s,'let inputReport=null,acquisitionReport=null,acquisitionHolds=0,screenObservation=null;',
  "let inputReport=null,acquisitionReport=null,acquisitionHolds=0,screenObservation=null;\n  const startupPolicy=head.metadata.startup_rate_policy;const startupEnabled=!!startupPolicy&&head.metadata.sensor_path==='generic'&&head.metadata.requested_interval==='high'&&head.metadata.requested_duration_ms>=10000;\n  let startupReport={schema_version:1,status:startupEnabled?'pending':'not_applicable',evaluated_epoch_ms:null,elapsed_ms:null,count:null,callback_span_ms:null,arrival_per_second:null};");
 s=one(s,'    elapsed_ms:(stopped===null?',"    startup_rate_status:startupReport.status,elapsed_ms:(stopped===null?");
 s=one(s,'  function notify(){',`  function checkStartup(t){
    if(startupReport.status!=='pending'||t-head.started_epoch_ms<startupPolicy.check_after_ms)return false;
    const span=first!==null&&last!==null?last-first:null,rate=span>0?(count-1)*1000/span:null;
    const sufficient=span!==null&&span>=startupPolicy.minimum_callback_span_ms&&count>=2&&finite(rate);
    startupReport={schema_version:1,status:!sufficient?'insufficient':rate<startupPolicy.minimum_arrival_per_second?'stopped_slow':'passed',evaluated_epoch_ms:t,elapsed_ms:t-head.started_epoch_ms,count:count,callback_span_ms:span,arrival_per_second:rate};
    if(startupReport.status==='passed')return false;
    stop(sufficient?'startup_rate_low':'startup_rate_unconfirmed');return true;
  }
  function notify(){`);
 s=one(s,"    status='stopping';stopReason=", "    if(startupReport.status==='pending')startupReport.status='not_checked_before_stop';\n    status='stopping';stopReason=");
 s=one(s,'      tail.runtime_timing_observation=timing.snapshot();','      tail.runtime_timing_observation=timing.snapshot();\n      tail.startup_rate_observation=Object.assign({},clone(startupReport),{status:startupReport.status===\'pending\'?\'not_checked_before_stop\':startupReport.status});');
 s=one(s,'        if(t-lastFlush>=head.metadata.storage_policy.timed_flush_ms)pump();','        if(checkStartup(t))return;\n        if(t-lastFlush>=head.metadata.storage_policy.timed_flush_ms)pump();');
 return s;
}
function catalog(s){
 s=one(s,'let snapshot=null,cache=[],generation=0,','let snapshot=null,stale=false,staleError=\'\',cache=[],generation=0,');
 s=one(s,'function invalidate(){generation++;snapshot=null;cache=[];last={available:false};}',"function invalidate(){generation++;stale=true;staleError='记录已变更';last={available:!!snapshot,stale:true};}");
 s=one(s,'if(!snapshot||snapshot.groups[g.id]!==g)','if(stale||!snapshot||snapshot.groups[g.id]!==g)');
 s=one(s,"last={available:true,source:source,", "last={available:true,source:stale?'stale':source,stale:stale,error:stale?staleError:null,");
 s=one(s,'return c?copy(c.item):descriptor(g);',"const item=c?copy(c.item):descriptor(g);if(stale){item.catalog_stale=true;item.catalog_ready=true;}return item;");
 s=one(s,'if(options.reuse&&snapshot)','if(options.reuse&&snapshot&&!stale)');
 s=one(s,'const ticket=++generation,started=Date.now();snapshot=null;last={available:false};','const ticket=++generation,started=Date.now();stale=true;last={available:!!snapshot,stale:true};');
 s=one(s,'   cache=[];timing.organize_ms=',"   stale=false;staleError='';cache=[];timing.organize_ms=");
 s=one(s,'  }).catch(e=>{if(ticket===generation)invalidate();throw e;});',"  }).catch(e=>{if(ticket===generation){stale=true;staleError=String(e.message||e);if(snapshot)return view(trashed,options.offset,'stale');last={available:false,stale:true,error:staleError};}throw e;});");
 s=one(s,'  const g=snapshot.groups[id],found=cache.find',"  if(stale){const g=snapshot.groups[id],c=cache.find(c=>c.id===id&&c.signature===g.signature);return Object.assign(c?copy(c.item):descriptor(g),{catalog_stale:true,catalog_ready:true});}\n  const g=snapshot.groups[id],found=cache.find");
 return s;
}
function page(s){
 s=one(s,'v0.4.12','v0.4.13');
 s=one(s,'operation.fileObservation={timeout_ms:8000,','operation.fileObservation={timeout_ms:30000,');
 s=one(s,"Error('导出读取文件超时；原记录保留')),8000);","Error('导出读取文件超时；原记录保留')),30000);");
 s=one(s,"this.catalogNote=state.source==='cached'?'目录缓存 · 点此刷新':'目录已刷新 · 点此刷新';","this.alert=state.stale===true;this.catalogNote=state.stale?(state.error||'目录待刷新')+' · 上次列表 · 点此刷新':state.source==='cached'?'目录缓存 · 点此刷新':'目录已刷新 · 点此刷新';");
 s=one(s,"this.capacityText=state.used>=40?'已满40条 · 回收区仍占名额':'占用 '+state.used+'/40 · 含回收区';","this.capacityText=state.stale?'上次会话 '+state.used+'/40 · 待刷新':state.used>=40?'会话已满40条 · 含回收区':'会话 '+state.used+'/40 · 含回收区';");
 s=one(s,"this.recordPosition='0 / 0';this.recordTitle='目录读取失败';","this.recordPosition='— / —';this.recordTitle='目录暂未读取';");
 s=one(s,"this.capacityText='容量待刷新';","this.capacityText='会话数未知 · 原记录保留';");
 s=one(s,"this.recordQuality=item?(item.state==='sealed'?","this.recordQuality=item?(item.catalog_stale?'上次列表 · 操作前重新核验':item.state==='sealed'?");
 s=one(s,"(s.stop_reason==='sensor_silence'?'采集已中断", "(s.stop_reason==='startup_rate_low'?'启动回调偏慢 · 已停止保存 '+s.persisted+'条，请导出':s.stop_reason==='startup_rate_unconfirmed'?'启动节奏未确认 · 已停止保存，请导出':s.stop_reason==='sensor_silence'?'采集已中断");
 s=one(s,"    }else if(s.status==='stopping')this.status='正在保存余下数据，请稍等';","    }else if(s.status==='stopping')this.status='正在保存余下数据，请稍等';\n    else if(s.status==='recording')this.status=s.startup_rate_status==='pending'?'正在检查high启动节奏（约5秒）':'采集中 · 保亮分块保存';");
 return s;
}
module.exports={core,catalog,page};
