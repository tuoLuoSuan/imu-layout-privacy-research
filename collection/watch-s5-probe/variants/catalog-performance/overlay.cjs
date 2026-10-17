function one(s,a,b){if(s.split(a).length!==2)throw Error('Catalog performance marker mismatch: '+a.slice(0,90));return s.replace(a,b);}
function core(s){return one(s,"app_version:'0.4.10'","app_version:'0.4.11'");}
function page(s){
 s=one(s,'v0.4.10','v0.4.11');
 s=one(s,"trashMode:false,recordPosition:","catalogNote:'',capacityText:'',trashMode:false,recordPosition:");
 s=one(s,'this._catalogGeneration=0;','this._catalogResume=false;this._catalogLoading=false;this._catalogOffset=0;this._catalogTotal=0;this._catalogGeneration=0;');
 s=one(s,"this.settingsMode=false;this.refreshRecords();},","this.settingsMode=false;this.refreshRecords(true,0,0);},");
 // Cancel only list/summary UI work; export and acquisition lifecycle stays unchanged.
 s=one(s,'onHide(){','onHide(){this.cancelCatalogView();');s=one(s,'onDestroy(){','onDestroy(){this.cancelCatalogView();');
 s=one(s,'onShow(){','onShow(){this.resumeCatalogView();');
 const begin=s.indexOf('  refreshRecords(){'),end=s.indexOf('  recordAction(){',begin);
 if(begin<0||end<begin)throw Error('Catalog methods unavailable');
 s=s.slice(0,begin)+`  cancelCatalogView(){
    this._catalogGeneration++;
    if(this._catalogLoading){this._catalogResume=true;this._catalogLoading=false;this.loading=false;}
  },
  resumeCatalogView(){if(this._catalogResume&&!this._destroyed){this._catalogResume=false;if(this.tab==='records'&&!this.busy())this.refreshRecords(true,this._catalogOffset,this._selection);}},
  reloadRecords(){if(this.tab!=='records'||this.confirmMode||this.exportChoice||this.transferMode||this.settingsMode)return;this.refreshRecords(false,0,0);},
  refreshRecords(reuse,offset,selection){
    if(this.busy())return;
    const generation=++this._catalogGeneration;
    this.loading=true;this._catalogLoading=true;this._legacy=null;this.alert=false;this.catalogNote='正在读取目录…';this.status=this.catalogNote;
    this._store.list(this.trashMode,{reuse:reuse===true,offset:offset||0}).then(items=>{
      if(this._destroyed||generation!==this._catalogGeneration)return;
      const state=this._store.catalogState();this._catalogOffset=state.offset;this._catalogTotal=state.total;
      this.catalogNote=state.source==='cached'?'目录缓存 · 点此刷新':'目录已刷新 · 点此刷新';
      this.status=this.catalogNote;
      this.capacityText=state.used>=40?'已满40条 · 回收区仍占名额':'占用 '+state.used+'/40 · 含回收区';
      this.loading=false;this._catalogLoading=false;this._items=items;this._selection=Math.min(selection||0,Math.max(0,items.length-1));this.renderRecord();
    }).catch(e=>{if(this._destroyed||generation!==this._catalogGeneration)return;this._items=[];this._selection=0;this._catalogTotal=0;this.recordPosition='0 / 0';this.recordTitle='目录读取失败';this.recordDetail='原记录保留，请点刷新重试';this.recordQuality='';this.catalogNote='刷新失败 · 点此重试';this.capacityText='容量待刷新';this._catalogLoading=false;this.reportError(e);});
  },
  renderRecord(){
    const selected=this._items[this._selection];
    this.recordPosition=this._items.length?String(this._catalogOffset+this._selection+1)+' / '+this._catalogTotal:'0 / 0';
    if(selected&&!selected.catalog_ready){
      const generation=++this._catalogGeneration,index=this._selection;this.loading=true;this._catalogLoading=true;
      this.recordTitle='会话 '+selected.id.slice(-6);this.recordDetail='正在读取当前记录…';this.recordQuality='其它记录按需读取';
      this._store.describe(selected.id).then(item=>{
        if(this._destroyed||generation!==this._catalogGeneration)return;
        this.loading=false;this._catalogLoading=false;this._items[index]=item;this.renderRecord();
      }).catch(e=>{if(!this._destroyed&&generation===this._catalogGeneration){this._catalogLoading=false;this.reportError(e);}});
      return;
    }
    const item=selected;
    this.recordTitle=item?'会话 '+item.id.slice(-6):'尚无记录';
    this.recordDetail=item?(item.count===null?'条数待核':item.count+'条')+' · '+(item.duration_ms===null?'时长待核':(item.duration_ms/1000).toFixed(1)+'秒'):'可开始新采集或恢复旧记录';
    this.recordQuality=item?(item.state==='sealed'?(item.tail.quality.warnings.length?'有告警 · 请核报告':'已封口 · 尚待外部核验'):item.state==='interrupted'?'中断记录 · 部分数据可导出':item.state==='deleting'?'删除未完成 · 可再次确认':'损坏 · 请保留文件'):'新旧记录分别保留';
  },
  moveRecord(delta){
    if(this.busy()||!this._catalogTotal)return;
    this._legacy=null;const target=(this._catalogOffset+this._selection+delta+this._catalogTotal)%this._catalogTotal,offset=Math.floor(target/40)*40;
    if(offset!==this._catalogOffset){this.refreshRecords(true,offset,target-offset);return;}
    this._selection=target-offset;this.renderRecord();
  },
  previousRecord(){this.moveRecord(-1);},nextRecord(){this.moveRecord(1);},
  toggleTrash(){if(this.busy())return;this.trashMode=!this.trashMode;this.refreshRecords(true,0,0);},
`+s.slice(end);
 // Reuse existing vertical space: status is the refresh action, record card remains 105px.
 s=one(s,'class="{{alert ? \'status warning\' : \'status\'}}"','class="{{alert ? \'status warning\' : \'status\'}}" onclick="reloadRecords"');
 s=one(s,'{{trashMode ? \'回收区\' : \'本机记录\'}} {{recordPosition}}</text><text class="record-info">{{recordTitle}}</text><text class="caption">{{recordDetail}}</text><text class="caption">{{recordQuality}}</text>',
   '{{trashMode ? \'回收\' : \'记录\'}} {{recordPosition}} · {{recordTitle}}</text><text class="record-info">{{recordDetail}}</text><text class="caption">{{recordQuality}}</text><text class="caption">{{capacityText}}</text>');
 return s;
}
module.exports={core,page};
