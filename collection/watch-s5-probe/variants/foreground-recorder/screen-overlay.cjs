function one(s,a,b){if(s.split(a).length!==2)throw Error('Foreground marker mismatch: '+a.slice(0,100));return s.replace(a,b);}
function core(c){
 c=one(c,"app_version:'0.4.2'","app_version:'0.4.3'");
 c=one(c,"record_purpose:options.inputProbe===true?'input_probe':'recording',sensor_path:","record_purpose:options.inputProbe===true?'input_probe':'recording',screen_policy:options.inputProbe===true?null:{schema_version:1,mode:'foreground_keep_awake',api:'@system.brightness.setKeepScreenOn',physical_screen_verified:false},sensor_path:");
 c=one(c,'let inputReport=null,acquisitionReport=null,acquisitionHolds=0;','let inputReport=null,acquisitionReport=null,acquisitionHolds=0,screenObservation=null;');
 c=one(c,'      if(acquisitionReport!==null)tail.acquisition_observation=acquisitionReport;','      if(acquisitionReport!==null)tail.acquisition_observation=acquisitionReport;\n      if(screenObservation!==null)tail.screen_observation=screenObservation;');
 c=one(c,'    holdAcquisition:function(){',`    setScreenObservation:function(value){
      if(status==='sealed'||!value||value.schema_version!==1||value.mode!=='foreground_keep_awake'||ascii(value).length>4096)throw Error('screen observation boundary');
      screenObservation=clone(value);
      if(value.release&&['failed','timeout','exception','unavailable'].indexOf(value.release.status)>=0)warn('screen_release_unconfirmed');
    },
    holdAcquisition:function(){`);
 return c;
}
function page(ux){
 ux=one(ux,'v0.4.2','v0.4.3');
 ux=one(ux,"import sensor from '@system.sensor'","import sensor from '@system.sensor'\nimport screenGuard from '../common/screen-guard.js'");
 ux=one(ux,'  onInit(){','  onInit(){\n    this._screenGuard=null;this._screenReleaseStarted=false;this._screenReleasePending=false;this._recordGeneration=0;');
 ux=one(ux,'  startRecording(){',`  startRecording(){
    if(this.busy()||this._screenReleasePending)return;
    if(this._session&&this._session.state().status!=='sealed'){this.status='请先保存上一条记录';this.alert=true;return;}
    const generation=++this._recordGeneration;
    this.loading=true;this.alert=false;this.status='正在请求录制保亮…';this._screenReleaseStarted=false;
    this._screenGuard=screenGuard.create({load:()=>require('@system.brightness'),now:Date.now,setTimeout:setTimeout,clearTimeout:clearTimeout});
    this._screenGuard.acquire().then(()=>{
      if(generation!==this._recordGeneration||this._destroyed||this._pageState!=='visible')throw Error('保亮已取消，未开始录制');
      this.loading=false;this.beginSessionRecording();
    }).catch(e=>this.reportError(e));
  },
  cancelForegroundStart(){
    this._recordGeneration++;
    if(this._screenGuard){this._screenReleasePending=true;this._screenGuard.release().then(()=>{this._screenReleasePending=false;});}
  },
  finishScreenPolicy(s){
    if(s.status==='recording'||!this._session||!this._screenGuard||this._screenReleaseStarted)return;
    this._screenReleaseStarted=true;this._screenReleasePending=true;
    const session=this._session;session.holdAcquisition();
    this._screenGuard.release().then(report=>{
      try{session.setScreenObservation(report);}finally{this._screenReleasePending=false;session.releaseAcquisition();}
    });
  },
  beginSessionRecording(){`);
 ux=one(ux,'      this.loading=false;this._session=s;','      this.loading=false;this._session=s;s.setScreenObservation(this._screenGuard.state());s.event(\'screen_keep_awake\',\'acquired\');');
 ux=one(ux,"      if(this._destroyed){s.stop('page_destroy');return;}","      if(this._destroyed||this._pageState!=='visible'||this._screenGuard.state().release.status!=='not_requested'){s.stop(this._destroyed?'page_destroy':'page_hide');return;}");
 ux=one(ux,'    if(!this.recording)this.unsubscribe();','    if(!this.recording){this.unsubscribe();this.finishScreenPolicy(s);}');
 ux=one(ux,'  onHide(){',"  onHide(){this.cancelForegroundStart();if(this._session&&this._session.state().status==='recording')this._session.stop('page_hide');");
 ux=one(ux,'  onDestroy(){','  onDestroy(){this.cancelForegroundStart();');
 ux=one(ux,'  reportError(error){this.alert=true;','  reportError(error){if(this._screenGuard){this._screenReleasePending=true;this._screenGuard.release().then(()=>{this._screenReleasePending=false;});}this.alert=true;');
 ux=one(ux,'三轴 · 单位待验','录制期间保持亮屏');
 ux=one(ux,'采集中 · 分块保存','采集中 · 保亮分块保存');
 return ux;
}
module.exports={core:core,page:page};
