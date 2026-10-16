// Build-time integration only; no new system module is imported by the watch.
function one(source,from,to){if(source.split(from).length!==2)throw Error('Input page marker mismatch: '+from.slice(0,80));return source.replace(from,to);}
function decorate(ux){
 ux=one(ux,"import sensor from '@system.sensor'","import sensor from '@system.sensor'\nimport inputProbe from '../common/input-probe.js'");
 ux=one(ux,'    diagnosticMode:false,',"    inputMode:false,inputBusy:false,inputAttempted:false,inputEligible:false,inputTitle:'输入检查',inputDetail:'',inputStatus:'',\n    diagnosticMode:false,");
 ux=one(ux,'  onInit(){','  onInit(){\n    this._inputRun=null;this._inputTimer=null;this._inputDeclaration=null;');
 ux=one(ux,'  onHide(){',"  onHide(){if(this._inputRun)this._inputRun.stop('page_hide');");
 ux=one(ux,'  onDestroy(){',"  onDestroy(){if(this._inputRun)this._inputRun.stop('page_destroy');this.clearInputTimer();");
 ux=one(ux,"if(this._sender&&this._sender.state().status!=='complete')this._sender.cancel();","if(this._sender&&['loading','sending'].indexOf(this._sender.state().status)>=0)this._sender.cancel();");
 ux=one(ux,'if(this._sender)this._sender.cancel();this.clearTransferTimer();this._destroyed',"if(this._sender&&['loading','sending'].indexOf(this._sender.state().status)>=0)this._sender.cancel();this.clearTransferTimer();this._destroyed");
 ux=one(ux,'return this.recording||this.saving||this.loading||this.transferring||this.diagnosticRunning;', 'return this.recording||this.saving||this.loading||this.transferring||this.diagnosticRunning||this.inputBusy;');
 ux=one(ux,'  openSettings(){',`  openInput(){
    if(this.busy())return;
    this.inputMode=true;this._inputDeclaration=inputProbe.inspect(sensor);this.inputEligible=this._inputDeclaration.eligible;
    this.inputTitle=this.inputEligible?'普通加速度入口已声明':'普通入口未完整声明';
    this.inputDetail='subscribe: '+this._inputDeclaration.method_types.subscribe+' / unsubscribe: '+this._inputDeclaration.method_types.unsubscribe+' / ACCEL: '+String(this._inputDeclaration.accelerometer_type);
    this.inputStatus=this.inputAttempted?'本次已检查，请导出核验':'只读检查完成 · 尚未订阅';
  },
  startInput(){
    if(this.busy()||this.inputAttempted||!this.inputMode)return;
    this.inputAttempted=true;this.inputBusy=true;
    const mono=typeof performance!=='undefined'&&typeof performance.now==='function'?()=>performance.now():null;
    this._inputRun=inputProbe.create({sensor:sensor,store:this._store,declaration:this._inputDeclaration,monotonic:mono,pageState:()=>this._pageState,onState:s=>this.updateInput(s)});
    this._inputTimer=setInterval(()=>this._inputRun.tick(),50);
    this._inputRun.start().catch(e=>{this.inputBusy=false;this.inputStatus='保存检查失败：'+String(e.message||e);this.clearInputTimer();});
  },
  updateInput(s){
    this.inputBusy=['preparing','running','saving'].indexOf(s.phase)>=0;
    this.inputTitle=s.phase==='running'?'两秒输入检查':s.phase==='saving'?'正在保存检查':s.phase==='complete'?'输入检查已保存':s.phase==='storage_failed'?'保存异常，请保留原件':'准备检查';
    this.inputStatus='回调 '+s.callbacks+' 次 · '+s.result;
    if(s.error)this.inputDetail=String(s.error.message);
    if(!this.inputBusy)this.clearInputTimer();
  },
  clearInputTimer(){if(this._inputTimer!==null)clearInterval(this._inputTimer);this._inputTimer=null;},
  closeInput(){if(this.busy())return;this.inputMode=false;this.status=this.inputAttempted?'请在记录页导出最新输入检查':'准备就绪';},
  openSettings(){`);
 ux=one(ux,'!transferMode &amp;&amp; !diagnosticMode','!transferMode &amp;&amp; !diagnosticMode &amp;&amp; !inputMode');
 ux=one(ux,`<div class="retry" onclick="retrySave"><text class="parameter-text">{{retryable ? '保存失败 · 点此重试' : '三轴加速度 · 单位与轴向待验'}}</text></div>`,
 `<div class="diagnostic-actions"><div class="diagnostic-link" onclick="retrySave"><text class="diagnostic-link-text">{{retryable ? '重试保存' : '三轴 · 单位待验'}}</text></div><div class="diagnostic-link" onclick="openInput"><text class="diagnostic-link-text">输入检查</text></div></div>`);
 ux=one(ux,'      <div if="{{diagnosticMode}}"',`      <div if="{{inputMode}}" class="body">
        <div class="card diagnostic-card"><text class="diagnostic-heading">{{inputTitle}}</text><text class="diagnostic-detail">{{inputDetail}}</text><text class="caption">{{inputStatus}}</text></div>
        <div class="row"><div class="button secondary" onclick="closeInput"><text class="button-text">返回</text></div><div class="button primary" onclick="startInput"><text class="button-text light">{{inputAttempted ? '本次已检查' : inputEligible ? '试采2秒' : '保存检查结果'}}</text></div></div>
        <text class="note">一次检查 · 保持此页 · 原始结果可导出</text>
      </div>
      <div if="{{diagnosticMode}}"`);
 ux=one(ux,"this.recordTitle=item?'会话 '+item.id.slice(-6):'尚无记录';", "this.recordTitle=item?(item.head&&item.head.metadata.record_purpose==='input_probe'?'输入检查 ':'会话 ')+item.id.slice(-6):'尚无记录';");
 return ux;
}
module.exports={decorate};
