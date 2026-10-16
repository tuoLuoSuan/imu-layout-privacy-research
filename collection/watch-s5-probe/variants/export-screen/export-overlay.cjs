function one(s,a,b){if(s.split(a).length!==2)throw Error('Export screen marker mismatch: '+a.slice(0,100));return s.replace(a,b);}
function page(ux){
 ux=one(ux,'v0.4.4','v0.4.5');
 ux=one(ux,'  onInit(){','  onInit(){\n    this._exportScreen=null;this._exportScreenPending=false;this._exportScreenGeneration=0;this._lastExportScreen=null;');
 ux=one(ux,'busy(){return ', 'busy(){return this.exportMode||this._exportScreenPending||');
 ux=one(ux,'  startWireless(){',`  exportScreenCurrent(operation){
    return operation&&!operation.releasing&&this._exportScreen===operation&&this._exportScreenGeneration===operation.generation&&!this._destroyed&&this._pageState==='visible';
  },
  startExportScreen(kind,begin){
    if(this.busy()||this._exportScreen||this._screenReleasePending)return;
    const operation={kind:kind,generation:++this._exportScreenGeneration,releasing:false,
      guard:screenGuard.create({load:()=>require('@system.brightness'),now:Date.now,setTimeout:setTimeout,clearTimeout:clearTimeout})};
    this._exportScreen=operation;this._exportScreenPending=true;this.loading=true;this.alert=false;this.exportChoice=false;
    if(kind==='wireless'){this.transferMode=true;this.transferring=false;this.transferPercent=0;this.transferProgress='准备中';this.transferStatus='正在请求导出保亮…';}
    this.status='正在请求导出保亮…';
    const acquired=operation.guard.acquire();operation.acquireDone=acquired.then(()=>null,()=>null);
    acquired.then(()=>{
      if(!this.exportScreenCurrent(operation))return;
      this.loading=false;this._exportScreenPending=false;
      try{begin();}catch(e){this.exportScreenError(operation,e);}
    }).catch(e=>{if(!operation.releasing)this.exportScreenError(operation,e);});
  },
  exportScreenError(operation,error){
    if(this._exportScreen!==operation)return;
    this.loading=false;this.transferring=false;this.alert=true;
    const message=String(error.message||error).replace(/录制/g,'导出');this.status=message;
    if(operation.kind==='wireless')this.transferStatus=message;
    this.finishExportScreen();
  },
  finishExportScreen(){
    const operation=this._exportScreen;if(!operation||operation.releasing)return;
    operation.releasing=true;this._exportScreenGeneration++;this._exportScreenPending=true;this.loading=false;
    if(operation.kind==='qr'){this.pauseQr();this.exportMode=false;this._frames=[];this.qrValue='';}
    const released=operation.guard.release();
    Promise.all([operation.acquireDone,released]).then(()=>{
      const finish=()=>{
        const report=operation.guard.state();
        if(report.late_release_attempts&&!report.late_release){setTimeout(finish,50);return;}
        if(this._exportScreen!==operation)return;
        this._lastExportScreen=Object.assign({purpose:operation.kind},report);
        this._exportScreen=null;this._exportScreenPending=false;
        if(this._destroyed)return;
        const uncertain=(report.release.status!=='success'&&report.acquire.status!=='unavailable')||(report.late_release&&report.late_release.status!=='success');
        if(uncertain){this.alert=true;this.status='导出保亮释放未确认，请检查屏幕状态';if(operation.kind==='wireless')this.transferStatus+=' · 保亮释放未确认';}
        else if(operation.kind==='wireless'&&report.acquire.status==='success')this.transferStatus+=' · 保亮已释放';
        else if(operation.kind==='qr'&&report.acquire.status==='success')this.status='已退出二维码 · 保亮已释放';
      };
      finish();
    });
  },
  startWireless(){this.startExportScreen('wireless',()=>this.beginWirelessExport());},
  beginWirelessExport(){`);
 ux=one(ux,'  openQrExport(){',"  openQrExport(){this.startExportScreen('qr',()=>this.beginQrExport());},\n  beginQrExport(){const exportOperation=this._exportScreen;");
 ux=one(ux,'this._store.inventory(item.id).then(inv=>{this._inventory=inv;',
  'this._store.inventory(item.id).then(inv=>{if(!this.exportScreenCurrent(exportOperation))return;this._inventory=inv;');
 ux=one(ux,"this.status='二维码传输较慢，请拍齐每段';this.loadPart();}).catch(e=>this.reportError(e));",
  "this.status='二维码传输较慢，请拍齐每段';this.loadPart();}).catch(e=>{if(this.exportScreenCurrent(exportOperation))this.reportError(e);});");
 ux=one(ux,'  loadPart(){','  loadPart(){const exportOperation=this._exportScreen;');
 ux=one(ux,'promise.then(text=>{this._frames=','promise.then(text=>{if(!this.exportScreenCurrent(exportOperation))return;this._frames=');
 ux=one(ux,'}).catch(e=>{this.loading=false;this.exportMode=false;this.reportError(e);});',
  '}).catch(e=>{if(!this.exportScreenCurrent(exportOperation))return;this.loading=false;this.exportMode=false;this.reportError(e);});');
 ux=one(ux,'  clearTransferTimer(){',"  clearTransferTimer(){if(!this.transferring)this.finishExportScreen();");
 ux=one(ux,'  cancelWireless(){','  cancelWireless(){this.finishExportScreen();');
 ux=one(ux,'closeExport(){if(this.loading)return;','closeExport(){if(this.loading)return;this.finishExportScreen();');
 ux=one(ux,'  reportError(error){','  reportError(error){this.finishExportScreen();');
 ux=one(ux,'  onHide(){','  onHide(){this.finishExportScreen();');
 ux=one(ux,'  onDestroy(){','  onDestroy(){this.finishExportScreen();');
 ux=one(ux,'传输期间保持此页，原记录保留','传输自动保亮，原记录保留');
 return ux;
}
module.exports={page:page};
