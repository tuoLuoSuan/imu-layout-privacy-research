// Build-time overlay on the already preserved source-only 0.4.0 profile.
function one(s,a,b){if(s.split(a).length!==2)throw Error('Precise UI marker mismatch: '+a.slice(0,100));return s.replace(a,b);}
function decorate(ux){
 ux=one(ux,"import sensor from '@system.sensor'","import sensor from '@system.sensor'\nimport sensorCapture from '../common/sensor-capture.js'");
 ux=one(ux,'  onInit(){','  onInit(){\n    this._sensorDriver=null;');
 ux=one(ux,"measured:'--',interval:'game'","measured:'--',interval:'high'");
 ux=one(ux,'this._values=[0,0,0,0,0,0];','this._values=[0,0,0,0,0,0,0];');
 ux=one(ux,"['game','ui','normal']","['high','mid','low']");ux=one(ux,"'R19','R20']];","'R19','R20'],['generic','legacy']];");
 ux=one(ux,'采集设置 {{settingIndex + 1}} / 6','采集设置 {{settingIndex + 1}} / 7');
 ux=one(ux,"'匿名参与者','匿名房间'][i]","'匿名参与者','匿名房间','数据入口'][i]");
 ux=one(ux,'this.settingValue=i===0?',"this.settingValue=i===6?(value==='generic'?'通用入口':'原入口'):i===0?");
 ux=one(ux,"this.settingHint=['分钟档尚待真机验收','game ≈20ms · ui ≈60ms · normal ≈200ms','动作指令不等于动作标注','默认未记录，按实际选择','仅用研究编号，不填姓名','仅用研究编号，不填地址'][i];", "this.settingHint=['分钟档尚待真机验收','请求档位不等于实测频率','动作指令不等于动作标注','默认未记录，按实际选择','仅用研究编号，不填姓名','仅用研究编号，不填地址','通用入口保留小数，原入口供对照'][i];");
 ux=one(ux,'(this.settingIndex+1)%6','(this.settingIndex+1)%7');
 ux=one(ux,'this._values[i]=(this._values[i]+delta+this._lists[i].length)%this._lists[i].length;this.renderSetting();',"this._values[i]=(this._values[i]+delta+this._lists[i].length)%this._lists[i].length;if(i===6){this._lists[1]=this._lists[6][this._values[6]]==='generic'?['high','mid','low']:['game','ui','normal'];this._values[1]=0;}this.renderSetting();");
 ux=one(ux,'const options={durationSeconds:this.durationSeconds,interval:this.interval,label:',"const options={sensorPath:this._lists[6][this._values[6]],durationSeconds:this.durationSeconds,interval:this.interval,label:");
 ux=one(ux,`      try{sensor.subscribeAccelerometer({interval:this.interval,callback:ret=>{s.push(ret,this._pageState);},fail:(msg,code)=>{s.event('sensor_fail',String(code));s.stop('sensor_fail');}});}
      catch(e){s.event('sensor_exception',String(e));s.stop('sensor_fail');}`,`      this._sensorDriver=sensorCapture.create(sensor,{now:Date.now,onValue:(value,at)=>s.push(value,this._pageState,at),
        beforeCallback:()=>s.holdAcquisition(),afterCallback:()=>s.releaseAcquisition(),
        onChange:report=>{if(s.state().status!=='sealed')s.setAcquisitionObservation(report);},
        onFail:error=>{s.event('sensor_fail',String(error.code)+' '+error.message);s.stop('sensor_fail');}});
      s.holdAcquisition();
      try{this._sensorDriver.start({sensorPath:options.sensorPath,interval:options.interval});}
      catch(e){s.event('sensor_exception',String(e));s.stop('sensor_fail');}
      finally{s.releaseAcquisition();}`);
 ux=one(ux,'unsubscribe(){try{sensor.unsubscribeAccelerometer();}catch(e){}},','unsubscribe(){if(this._sensorDriver)this._sensorDriver.stop();},');
 ux=one(ux,'实测回调 {{measured}} Hz','回调到达 {{measured}} 次/秒');
 return ux;
}
module.exports={decorate};
