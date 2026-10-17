// UX methods for one foreground directory transaction and explicit batch confirmation.
module.exports={
  stopCatalogProgress(){if(this._catalogTimer!==null)clearInterval(this._catalogTimer);this._catalogTimer=null;},
  cancelCatalogView(){
    this._catalogGeneration++;this.stopCatalogProgress();this._batchCancel=true;
    if(this._catalogLoading){this._catalogResume=true;this._catalogLoading=false;this.loading=false;this.status='读取已取消 · 点此刷新';this.finishExportScreen();}
  },
  resumeCatalogView(){
    if(this._destroyed)return;
    if(this._deferredBatch){const value=this._deferredBatch;this.finishBatchView(value.result,value.ids);return;}
    if(this._catalogResume){this._catalogResume=false;if(this.tab==='records')this.status='读取未完成 · 点此刷新';}
  },
  reloadRecords(){
    if(this._batchRunning){this._batchCancel=true;this.status='本条完成后停止 · 不会继续下一条';return;}
    if(this._catalogLoading){this.cancelCatalogView();return;}
    if(this.tab!=='records'||this.confirmMode||this.exportChoice||this.transferMode||this.settingsMode||this.batchMode)return;
    this.refreshRecords(false,0,0);
  },
  runCatalog(work){
    if(this.busy()||this._exportScreen||this._screenReleasePending)return;
    const generation=++this._catalogGeneration;
    this.startExportScreen('catalog',()=>{
      const op=this._exportScreen;
      if(generation!==this._catalogGeneration){this.finishExportScreen();return;}
      this.loading=true;this._catalogLoading=true;
      const started=Date.now();this._catalogPhase='正在读取目录';
      const update=()=>{if(!this._destroyed&&generation===this._catalogGeneration&&this.exportScreenCurrent(op))this.status=this._catalogPhase+' · '+Math.floor((Date.now()-started)/1000)+'秒 · 点此取消';};
      update();this._catalogTimer=setInterval(update,1000);
      Promise.resolve().then(work).then(()=>{
        if(this._destroyed||generation!==this._catalogGeneration||!this.exportScreenCurrent(op))return;
        this.stopCatalogProgress();this.loading=false;this._catalogLoading=false;this.status=this.catalogNote||'记录已读取 · 点此刷新';this.finishExportScreen();
      }).catch(e=>{
        if(this._destroyed||generation!==this._catalogGeneration||!this.exportScreenCurrent(op))return;
        this.stopCatalogProgress();this.loading=false;this._catalogLoading=false;this.alert=true;this.status=String(e.message||e)+' · 点此刷新';this.finishExportScreen();
      });
    });
    if(this._exportScreen&&this._exportScreen.kind==='catalog')this._catalogLoading=true;
  },
  refreshRecords(reuse,offset,selection){
    this.runCatalog(()=>{
      const generation=this._catalogGeneration;this._legacy=null;this.alert=false;this.catalogNote='';
      return this._store.list(this.trashMode,{reuse:reuse===true,offset:offset||0}).then(items=>{
        if(this._destroyed||generation!==this._catalogGeneration)return;
        const state=this._store.catalogState();this._catalogOffset=state.offset;this._catalogTotal=state.total;
        this.alert=state.stale===true;this.catalogNote=state.stale?(state.error||'目录待刷新')+' · 上次列表 · 点此刷新':'目录已读取 · 点此刷新';
        this.capacityText=state.stale?'上次会话 '+state.used+'/40 · 待刷新':state.used>=40?'会话已满40条 · 含回收区':'会话 '+state.used+'/40 · 含回收区';
        this._items=items;this._selection=Math.min(selection||0,Math.max(0,items.length-1));return this.describeSelected(generation);
      }).catch(e=>{
        if(this._destroyed||generation!==this._catalogGeneration)return;
        this._items=[];this._selection=0;this._catalogTotal=0;this.recordPosition='— / —';this.recordTitle='目录暂未读取';this.recordDetail='原记录保留，请点状态刷新';this.recordQuality='';this.capacityText='会话数未知 · 原记录保留';throw e;
      });
    });
  },
  describeSelected(generation){
    const item=this._items[this._selection],index=this._selection;
    if(!item||item.catalog_ready){this.renderRecord();return Promise.resolve();}
    this._catalogPhase='正在读取当前摘要';this.recordTitle='会话 '+item.id.slice(-6);this.recordDetail='正在读取当前记录…';
    return this._store.describe(item.id).then(value=>{if(this._destroyed||generation!==this._catalogGeneration)return;this._items[index]=value;this.renderRecord();});
  },
  renderRecord(){
    const item=this._items[this._selection];
    this.recordPosition=this._items.length?String(this._catalogOffset+this._selection+1)+' / '+this._catalogTotal:'0 / 0';
    this.recordTitle=item?'会话 '+item.id.slice(-6):'尚无记录';
    this.recordDetail=item?(item.count===null?'条数待核':item.count+'条')+' · '+(item.duration_ms===null?'时长待核':(item.duration_ms/1000).toFixed(1)+'秒'):'可开始新采集或恢复旧记录';
    this.recordQuality=item?(item.catalog_stale?'上次列表 · 操作前重新核验':item.state==='sealed'?(item.tail.quality.warnings.length?'有告警 · 请核报告':'已封口 · 尚待外部核验'):item.state==='interrupted'?'中断记录 · 部分数据可导出':item.state==='deleting'?'删除未完成 · 可再次确认':'损坏 · 请保留文件'):'新旧记录分别保留';
    this.updateBatchSelection();
  },
  moveRecord(delta){
    if(this.busy()||!this._catalogTotal)return;
    this._legacy=null;const target=(this._catalogOffset+this._selection+delta+this._catalogTotal)%this._catalogTotal,offset=Math.floor(target/40)*40;
    if(offset!==this._catalogOffset){this.refreshRecords(true,offset,target-offset);return;}
    this._selection=target-offset;
    if(this._items[this._selection]&&!this._items[this._selection].catalog_ready)this.runCatalog(()=>this.describeSelected(this._catalogGeneration));else this.renderRecord();
  },
  previousRecord(){this.moveRecord(-1);},nextRecord(){this.moveRecord(1);},
  toggleTrash(){if(this.busy())return;this.trashMode=!this.trashMode;this.refreshRecords(true,0,0);},
  recordAction(){
    if(this.busy()||this._legacy)return;const item=this._items[this._selection];if(!item)return;
    this._confirmIds=[item.id];this.backupRequired=false;this.backupAcknowledged=false;
    this.confirmMode=true;this.confirmTitle=this.trashMode?'恢复这条记录？':'移到回收区？';this.confirmHint='移回收可恢复，仍占会话名额';this.confirmButton=this.trashMode?'恢复记录':'移到回收区';this._confirm=this.trashMode?'batch_restore':'batch_trash';
  },
  extraAction(){
    if(this.busy())return;if(!this.trashMode){this.loadLegacy();return;}
    const item=this._items[this._selection];if(!item)return;this._confirmIds=[item.id];this.confirmMode=true;this.confirmTitle='永久删除这条记录？';this.confirmHint='无法撤销 · 请先核验电脑上的完整原件';this.confirmButton='永久删除';this._confirm='batch_purge';this.backupRequired=true;this.backupAcknowledged=false;
  },
  openBatch(){
    if(this.busy()||this._legacy||!this._items.length)return;
    this.batchMode=true;this._batchSelected=[];this.updateBatchSelection();this.status='逐条选中，或选本页旧记录（留最新）';
  },
  updateBatchSelection(){const item=this._items[this._selection];this.batchCount=this._batchSelected.length;this.batchCurrent=!!item&&this._batchSelected.indexOf(item.id)>=0;},
  toggleBatchItem(){if(this.busy()||!this.batchMode)return;const item=this._items[this._selection];if(!item)return;const at=this._batchSelected.indexOf(item.id);if(at<0){if(this._batchSelected.length>=40){this.status='每批最多40条';return;}this._batchSelected.push(item.id);}else this._batchSelected.splice(at,1);this.updateBatchSelection();},
  clearBatchSelection(){if(this.busy())return;this._batchSelected=[];this.updateBatchSelection();},
  selectOlder(){
    if(this.busy()||!this.batchMode)return;
    this._batchSelected=this._items.filter((item,index)=>this._catalogOffset+index>0).map(item=>item.id);this.updateBatchSelection();this.status='已选本页旧记录 · 保留列表最新一条';
  },
  closeBatch(){if(this.busy())return;this.batchMode=false;this._batchSelected=[];this.updateBatchSelection();this.refreshRecords(true,0,0);},
  prepareTrashBatch(){this.prepareBatch('trash');},prepareRestoreBatch(){this.prepareBatch('restore');},preparePurgeBatch(){this.prepareBatch('purge');},
  prepareBatch(action){
    if(this.busy()||!this.batchMode||!this._batchSelected.length)return;
    if(['trash','restore','purge'].indexOf(action)<0||(!this.trashMode&&action!=='trash')||(this.trashMode&&action==='trash'))return;
    this._confirmIds=this._batchSelected.slice();this._confirm='batch_'+action;this.confirmMode=true;this.backupRequired=action==='purge';this.backupAcknowledged=false;
    this.confirmTitle=(action==='purge'?'永久删除':action==='restore'?'恢复':'移到回收区')+' '+this._confirmIds.length+'条？';this.confirmButton=action==='purge'?'永久删除':action==='restore'?'恢复':'移到回收区';
    this.confirmHint=action==='purge'?'无法撤销 · 请先核验外部完整原件':'逐条处理 · 可在回收区恢复，仍占名额';
  },
  acknowledgeBackup(){if(!this.busy()&&this.backupRequired)this.backupAcknowledged=!this.backupAcknowledged;},
  cancelConfirm(){if(this._batchRunning){this._batchCancel=true;this.status='本条完成后停止 · 已完成的不回滚';return;}if(!this.busy()){this.confirmMode=false;this.backupRequired=false;}},
  finishBatchView(result,ids){
    this._deferredBatch=null;this._catalogResume=false;this.batchRunning=false;this.loading=false;this.confirmMode=false;this.backupRequired=false;this.batchMode=false;this._batchSelected=[];
    this._items=this._items.filter(item=>result.completed.indexOf(item.id)<0);this._selection=0;this._catalogTotal=Math.max(0,this._catalogTotal-result.completed.length);this.renderRecord();
    this.capacityText='目录已变更 · 点状态刷新';this.alert=!!result.error;
    this.status='已完成 '+result.completed.length+'/'+ids.length+'条'+(result.error?' · '+result.error+(result.uncertain?' · 本条结果待刷新核验':''):result.cancelled?' · 已停止，余下保留':' · 点此刷新');
  },
  confirmAction(){
    if(this.busy()||!this._confirmIds||!this._confirmIds.length)return;
    const action=this._confirm.slice(6),ids=this._confirmIds.slice();
    if(action==='purge'&&!this.backupAcknowledged){this.status='请先点选“已核验外部备份”';return;}
    this._batchCancel=false;
    this.startExportScreen('batch',()=>{
      const op=this._exportScreen;this._batchRunning=true;this.batchRunning=true;this.loading=true;this.status='正在检查目录 · 点取消可在本条后停止';
      const current=()=>this.exportScreenCurrent(op);
      this._store.batch(action,ids,{confirmed_ids:action==='purge'?ids:undefined,shouldCancel:()=>this._batchCancel||this._destroyed||this._pageState!=='visible',onProgress:progress=>{
        if(current())this.status='已完成 '+progress.completed+'/'+progress.total+'条'+(progress.current?' · 正在处理本条':'');
      }}).then(result=>{
        this._lastBatch=result;this._batchRunning=false;
        this._deferredBatch={result:result,ids:ids};
        if(!this._destroyed&&this._pageState==='visible')this.finishBatchView(result,ids);
        if(current())this.finishExportScreen();
      }).catch(e=>{
        this._batchRunning=false;const result={completed:[],failed_id:null,error:String(e.message||e),cancelled:false,uncertain:false};this._lastBatch=result;this._deferredBatch={result:result,ids:ids};
        if(!this._destroyed&&this._pageState==='visible')this.finishBatchView(result,ids);
        if(current())this.finishExportScreen();
      });
    });
  }
};
