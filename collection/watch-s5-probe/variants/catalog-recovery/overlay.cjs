// Independent directory/cleanup profile. Capture and transport stay frozen apart from version.
function one(s,a,b){if(s.split(a).length!==2)throw Error('Catalog recovery marker mismatch: '+a.slice(0,100));return s.replace(a,b);}
function core(s){
 s=one(s,"app_version:'0.4.13'","app_version:'0.4.14'");
 s=one(s,'let active = null, opening = false;','let active = null, opening = false, batchBusy = false, mutationBusy = false;');
 s=one(s,'  function inventory(id){','  function inventory(id,knownEntries){');
 s=one(s,'then(()=>directory()).then(list=>{','then(()=>knownEntries||directory()).then(list=>{');
 s=one(s,'  function inspect(id){\n    return inventory(id)', '  function inspect(id,knownEntries){\n    return inventory(id,knownEntries)');
 s=one(s,'  const store={list:list,inventory:inventory,readPart:read,inspect:inspect,',`  function mutation(work){
    let owns=false;return Promise.resolve().then(()=>{if(batchBusy||mutationBusy||opening)throw Error('正在整理记录，请稍等');mutationBusy=true;owns=true;return work();})
      .then(value=>{if(owns)mutationBusy=false;return value;},error=>{if(owns)mutationBusy=false;throw error;});
  }
  function trash(id,entries){return inspect(id,entries).then(item=>{if(active&&active.state().id===id&&active.state().status!=='sealed')throw Error('采集尚未封口');return write(id,'trash',{session_id:id,trashed_epoch_ms:now()});});}
  function restore(id,entries){return inspect(id,entries).then(item=>{if(!item.trashed)throw Error('该记录已不在回收区，请刷新');return call('delete',{uri:ROOT+filename(id,'trash')});});}
  function purge(id,confirmation,knownEntries){
    return Promise.resolve().then(()=>{validId(id);if(confirmation!==id)throw Error('删除确认不匹配');return knownEntries||directory();}).then(entries=>{
      const present=entries.map(x=>x.uri.indexOf(ROOT)===0?x.uri.slice(ROOT.length):x.uri),journal=filename(id,'purge');
      const prepare=present.indexOf(journal)>=0?parsed(id,journal):inspect(id,entries).then(item=>{
        if(!item.trashed)throw Error('请先移到回收区');if(item.state!=='sealed')throw Error('中断记录请先导出，禁止永久删除');
        return inventory(id,entries).then(inv=>{const value={session_id:id,files:inv.files.slice(1).reverse().concat([filename(id,'trash'),filename(id,'head')])};return write(id,'purge',value).then(()=>value);});
      });
      return prepare.then(plan=>{
        if(plan.session_id!==id||!Array.isArray(plan.files)||plan.files.length>403)throw Error('删除清单损坏');
        plan.files.forEach(n=>{allowedName(id,n);if(n===journal)throw Error('删除清单冲突');});
        let chain=Promise.resolve();plan.files.concat([journal]).filter(n=>present.indexOf(n)>=0||n===journal).forEach(n=>{chain=chain.then(()=>call('delete',{uri:ROOT+n}));});return chain;
      });
    });
  }
  function batch(action,ids,options){
    options=options||{};let owns=false;
    return Promise.resolve().then(()=>{
      if(['trash','restore','purge'].indexOf(action)<0||!Array.isArray(ids)||!ids.length||ids.length>40)throw Error('批量选择无效');
      ids=ids.slice();ids.forEach(validId);if(ids.some((id,i)=>ids.indexOf(id)!==i))throw Error('批量选择重复');
      if(action==='purge'&&(!Array.isArray(options.confirmed_ids)||JSON.stringify(options.confirmed_ids)!==JSON.stringify(ids)))throw Error('删除确认不匹配');
      if(batchBusy||mutationBusy||opening||(active&&active.state().status!=='sealed'))throw Error('正在采集或整理记录，请稍等');
      batchBusy=true;owns=true;
      const result={action:action,requested:ids.slice(),completed:[],failed_id:null,error:null,cancelled:false,uncertain:false};
      function cancelled(){return typeof options.shouldCancel==='function'&&options.shouldCancel()===true;}
      function progress(id){if(typeof options.onProgress==='function'){try{options.onProgress({completed:result.completed.length,total:ids.length,current:id});}catch(e){/* UI observers cannot change file semantics. */}}}
      if(cancelled()){result.cancelled=true;return result;}
      return directory().then(entries=>{
        let chain=Promise.resolve();ids.forEach(id=>{chain=chain.then(()=>{
          if(result.error||result.cancelled)return;
          if(cancelled()){result.cancelled=true;return;}progress(id);
          const operation=action==='trash'?trash(id,entries):action==='restore'?restore(id,entries):purge(id,id,entries);
          return operation.then(()=>{result.completed.push(id);progress(null);},e=>{result.failed_id=id;result.error=String(e.message||e);result.uncertain=/超时/.test(result.error);});
        });});return chain.then(()=>result);
      }).catch(e=>{result.error=String(e.message||e);result.uncertain=/超时/.test(result.error);return result;});
    }).then(value=>{if(owns)batchBusy=false;return value;},error=>{if(owns)batchBusy=false;throw error;});
  }
  const store={list:list,inventory:id=>inventory(id),readPart:read,inspect:id=>inspect(id),batch:batch,`);
 s=one(s,"        if(opening || (active && active.state().status!=='sealed'))", "        if(batchBusy||mutationBusy)throw Error('正在整理记录，请稍等');\n        if(opening || (active && active.state().status!=='sealed'))");
 const start=s.indexOf('    trash:function(id)'),end=s.indexOf('\n  };\n  return store;',start);
 if(start<0||end<0)throw Error('Missing mutation block');
 s=s.slice(0,start)+`    trash:id=>mutation(()=>trash(id)),restore:id=>mutation(()=>restore(id)),purge:(id,confirmation)=>mutation(()=>purge(id,confirmation))`+s.slice(end);
 return s;
}
function catalog(s){
 s=one(s,'cache=[],generation=0,','cache=[],generation=0,pendingScan=null,');
 s=one(s,"setTimeout(()=>finish(Error('文件操作超时')),8000)","setTimeout(()=>finish(Error('文件操作超时')),30000)");
 s=one(s,' function list(trashed,options){',' function scan(trashed,options){');
 const marker=' function read(name)';
 s=one(s,marker,` function list(trashed,options){
  options=options||{};
  if(pendingScan)return pendingScan.then(()=>view(trashed,options.offset,'fresh'));
  if(options.reuse&&snapshot&&!stale)return Promise.resolve(view(trashed,options.offset,'cached'));
  const work=scan(trashed,options);let held;
  held=work.then(value=>{if(pendingScan===held)pendingScan=null;return value;},e=>{if(pendingScan===held)pendingScan=null;throw e;});
  pendingScan=held;return held;
 }
`+marker);
 s=one(s,"['start','trash','restore','purge'].forEach", "['start','trash','restore','purge','batch'].forEach");
 s=one(s,"const operation=name==='restore'?base.inspect(args[0]).then(item=>{if(!item.trashed)throw Error('该记录已不在回收区，请刷新');return base.restore.apply(base,args);}):Promise.resolve().then(()=>base[name].apply(base,args));", "const operation=Promise.resolve().then(()=>base[name].apply(base,args));");
 return s;
}
function page(s){
 s=one(s,'v0.4.13','v0.4.14');
 s=one(s,"confirmMode:false,confirmTitle:'',", "batchMode:false,batchCount:0,batchCurrent:false,batchRunning:false,backupRequired:false,backupAcknowledged:false,confirmMode:false,confirmTitle:'',");
 s=one(s,'  onInit(){\n    this._exportScreen=null;', '  onInit(){\n    this._batchSelected=[];this._batchRunning=false;this._batchCancel=false;this._catalogTimer=null;\n    this._exportScreen=null;');
 s=one(s,"onShow(){this.resumeCatalogView();this._pageState='visible';", "onShow(){this._pageState='visible';this.resumeCatalogView();");
 s=one(s,'busy(){return this.exportMode', 'busy(){return this._batchRunning||this.exportMode');
 s=one(s,"showRecords(){if(this.busy())return;this.tab='records';", "showRecords(){if(this.busy())return;this.trashMode=false;this.batchMode=false;this.tab='records';");
 const a=s.indexOf('  cancelCatalogView(){'),b=s.indexOf('  loadLegacy(){',a);if(a<0||b<0)throw Error('Missing catalog page');
 const methods=require('./catalog-page.cjs');s=s.slice(0,a)+'  '+Object.values(methods).map(fn=>fn.toString()).join(',\n  ')+',\n'+s.slice(b);
 s=one(s,'      try{begin();}', '      try{begin();}'); // Assert inherited synchronous launch remains intact.
 s=one(s,"    this.status='正在请求导出保亮…';", "    this.status=kind==='catalog'?'正在请求目录保亮…':kind==='batch'?'正在准备整理…':'正在请求导出保亮…';");
 s=one(s,'    this.loading=false;this.transferring=false;this.alert=true;', "    if(operation.kind==='catalog'){this._catalogLoading=false;this.stopCatalogProgress();}\n    this.loading=false;this.transferring=false;this.alert=true;");
 s=one(s,"'导出保亮释放未确认，请检查屏幕状态'", "'保亮释放未确认，请检查屏幕状态'");
 s=one(s,'      <div if="{{!settingsMode &amp;&amp; !confirmMode', '      <div if="{{!batchMode &amp;&amp; !settingsMode &amp;&amp; !confirmMode');
 s=one(s,'          <div class="retry" onclick="extraAction"><text class="parameter-text">{{trashMode ? \'永久删除…\' : \'恢复旧版记录\'}}</text></div>',
 '          <div class="diagnostic-actions"><div class="diagnostic-link" onclick="openBatch"><text class="diagnostic-link-text">批量整理…</text></div><div class="diagnostic-link" onclick="extraAction"><text class="diagnostic-link-text">{{trashMode ? \'永久删除…\' : \'恢复旧版记录\'}}</text></div></div>');
 s=one(s,'      <div if="{{confirmMode}}" class="body">',`      <div if="{{batchMode &amp;&amp; !confirmMode}}" class="body">
        <div class="card record-card"><text class="card-title">{{trashMode ? '整理回收区' : '整理记录'}} · 已选{{batchCount}}条</text><text class="record-info">{{recordPosition}} · {{recordTitle}}</text><text class="caption">{{recordDetail}}</text><text class="caption">{{trashMode ? '永久删除前请核验外部备份' : '移回收可恢复，仍占会话名额'}}</text></div>
        <div class="row"><div class="button secondary" onclick="previousRecord"><text class="button-text">上一条</text></div><div class="button secondary" onclick="nextRecord"><text class="button-text">下一条</text></div><div class="button primary" onclick="toggleBatchItem"><text class="button-text light">{{batchCurrent ? '取消选中' : '选中'}}</text></div></div>
        <div class="row"><div class="button secondary" onclick="selectOlder"><text class="button-text">选本页旧记录</text></div><div class="button secondary" onclick="clearBatchSelection"><text class="button-text">清空选择</text></div></div>
        <div if="{{!trashMode}}" class="row"><div class="button danger" onclick="prepareTrashBatch"><text class="button-text light">移到回收区</text></div><div class="button secondary" onclick="closeBatch"><text class="button-text">返回</text></div></div>
        <div if="{{trashMode}}" class="row"><div class="button secondary" onclick="prepareRestoreBatch"><text class="button-text">批量恢复</text></div><div class="button danger" onclick="preparePurgeBatch"><text class="button-text light">永久删除…</text></div></div>
        <div if="{{trashMode}}" class="retry" onclick="closeBatch"><text class="parameter-text">返回记录</text></div>
      </div>
      <div if="{{confirmMode}}" class="body">`);
 s=one(s,'        <div class="row"><div class="button secondary" onclick="cancelConfirm"><text class="button-text">取消</text>',`        <div if="{{backupRequired}}" class="retry" onclick="acknowledgeBackup"><text class="parameter-text">{{backupAcknowledged ? '✓ 已核验外部备份' : '点此确认：已核验外部备份'}}</text></div>
        <div class="row"><div class="button secondary" onclick="cancelConfirm"><text class="button-text">{{batchRunning ? '完成本条后停止' : '取消'}}</text>`);
 return s;
}
module.exports={core,catalog,page};
