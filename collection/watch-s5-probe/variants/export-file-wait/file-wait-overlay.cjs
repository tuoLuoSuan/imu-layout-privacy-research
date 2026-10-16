// Bounded ordinary file waits only; viewing QR and the ACK protocol are unchanged.
function one(s,a,b){if(s.split(a).length!==2)throw Error('File wait marker mismatch: '+a.slice(0,90));return s.replace(a,b);}
function page(ux){
 ux=one(ux,'v0.4.5','v0.4.6');
 ux=one(ux,'  startExportScreen(kind,begin){',`  exportFileRead(operation,phase,read){
    if(!this.exportScreenCurrent(operation))return Promise.reject(Error('导出已结束'));
    const observation=operation.fileObservation||(operation.fileObservation={timeout_ms:8000,
      basis:'engineering_wait_limit_not_measured_latency',started:0,completed:0,timeouts:0,cancelled:0,last:null});
    const entry={phase:phase,status:'pending',requested_epoch_ms:Date.now()};observation.started++;observation.last=entry;
    const waits=operation.fileWaits||(operation.fileWaits=[]);
    return new Promise((resolve,reject)=>{
      let settled=false,timer=null;
      const finish=(status,value,error)=>{
        if(settled)return;settled=true;if(timer!==null)clearTimeout(timer);
        const index=waits.indexOf(wait);if(index>=0)waits.splice(index,1);
        entry.status=status;entry.completed_epoch_ms=Date.now();
        if(status==='cancelled')observation.cancelled++;else observation.completed++;
        if(status==='timeout')observation.timeouts++;
        if(status==='success'&&this.exportScreenCurrent(operation))resolve(value);
        else{if(status!=='cancelled'&&this.exportScreenCurrent(operation))this.alert=true;reject(error||Error('导出已结束'));}
      };
      const wait={cancel:()=>finish('cancelled',null,Error('导出已结束'))};waits.push(wait);
      timer=setTimeout(()=>finish('timeout',null,Error('导出读取文件超时；原记录保留')),8000);
      let pending;
      try{pending=read();}catch(error){finish('failed',null,error);return;}
      Promise.resolve(pending).then(value=>finish('success',value),error=>finish('failed',null,error));
    });
  },
  cancelExportFiles(operation){(operation.fileWaits||[]).slice().forEach(wait=>wait.cancel());},
  startExportScreen(kind,begin){`);
 ux=one(ux,'  beginWirelessExport(){','  beginWirelessExport(){const exportOperation=this._exportScreen;');
 ux=one(ux,'this._store.inventory(this._items[this._selection].id)',
  "this.exportFileRead(exportOperation,'inventory',()=>this._store.inventory(this._items[this._selection].id))");
 ux=one(ux,'this._store.inventory(item.id)',"this.exportFileRead(exportOperation,'inventory',()=>this._store.inventory(item.id))");
 ux=one(ux,'this._store.readPart(inv.id,inv.files[i-1])',
  "this.exportFileRead(exportOperation,'readPart',()=>this._store.readPart(inv.id,inv.files[i-1]))");
 ux=one(ux,'this._store.readPart(inv.id,inv.files[index-1])',
  "this.exportFileRead(exportOperation,'readPart',()=>this._store.readPart(inv.id,inv.files[index-1]))");
 ux=one(ux,'    const released=operation.guard.release();','    this.cancelExportFiles(operation);\n    const released=operation.guard.release();');
 ux=one(ux,'Object.assign({purpose:operation.kind},report)',
  'Object.assign({purpose:operation.kind,file_wait:operation.fileObservation?JSON.parse(JSON.stringify(operation.fileObservation)):null},report)');
 ux=one(ux,"if(uncertain){this.alert=true;this.status='导出保亮释放未确认，请检查屏幕状态';",
  "if(uncertain){const cause=this.alert?(operation.kind==='wireless'?this.transferStatus:this.status):'';this.alert=true;this.status=(cause?cause+' · ':'')+'导出保亮释放未确认，请检查屏幕状态';");
 ux=one(ux,"else if(operation.kind==='qr'&&report.acquire.status==='success')this.status='已退出二维码 · 保亮已释放';",
  "else if(operation.kind==='qr'&&report.acquire.status==='success')this.status=this.alert?this.status+' · 保亮已释放':'已退出二维码 · 保亮已释放';");
 return ux;
}
module.exports={page};
