// Presentation-only profile on the validated 0.4.6 controller.
function once(source, from, to) {
  if (source.split(from).length !== 2) throw Error('Clean UI marker mismatch: '+from.slice(0,80));
  return source.replace(from, to);
}
function page(source) {
  let ux=once(source,'v0.4.6','v0.4.7');
  ux=once(ux,'采集设置 {{settingIndex + 1}} / 7','采集设置 {{settingIndex + 1}} / 6');
  const begin=ux.indexOf('      <div if="{{inputMode}}"');
  const end=ux.indexOf('      <div if="{{exportChoice}}"',begin);
  if(begin<0||end<begin)throw Error('Diagnostic template boundary missing');
  ux=ux.slice(0,begin)+ux.slice(end);
  ux=once(ux,'<div class="diagnostic-actions"><div class="diagnostic-link" onclick="retrySave"><text class="diagnostic-link-text">{{retryable ? \'重试保存\' : \'录制期间保持亮屏\'}}</text></div><div class="diagnostic-link" onclick="openInput"><text class="diagnostic-link-text">输入检查</text></div></div>',
    '<div if="{{retryable}}" class="retry" onclick="retrySave"><text class="parameter-text">保存未完成 · 重试保存</text></div>');
  ux=once(ux,'<div class="diagnostic-actions"><div class="diagnostic-link" onclick="extraAction"><text class="diagnostic-link-text">{{trashMode ? \'永久删除…\' : \'恢复旧版（只读）\'}}</text></div><div class="diagnostic-link" onclick="inspectStorage"><text class="diagnostic-link-text">文件检查（只读）</text></div></div>',
    '<div class="retry" onclick="extraAction"><text class="parameter-text">{{trashMode ? \'永久删除…\' : \'恢复旧版记录\'}}</text></div>');
  ux=once(ux,"status:'准备就绪 · 先做2秒短试'","status:'准备就绪'");
  ux=once(ux,"interval:'high',durationSeconds:2","interval:'high',durationSeconds:60");
  ux=once(ux,"settingValue:'2秒',settingHint:'分钟档尚待真机验收'","settingValue:'60秒',settingHint:'采集结束后自动保存'");
  ux=once(ux,'this._values=[0,0,0,0,0,0,0];','this._values=[3,0,0,0,0,0,0];');
  ux=once(ux,'(this.settingIndex+1)%7','(this.settingIndex+1)%6');
  ux=once(ux,"this.settingHint=['分钟档尚待真机验收','请求档位不等于实测频率','动作指令不等于动作标注','默认未记录，按实际选择','仅用研究编号，不填姓名','仅用研究编号，不填地址','通用入口保留小数，原入口供对照'][i];",
    "this.settingHint=['采集结束后自动保存','选择请求档位','记录本次动作指令','选择实际佩戴腕侧','只填写参与者编号','只填写房间编号'][i];");
  ux=once(ux,'接收完成后保存文件，再交电脑核验','完成后在手机保存文件');
  return ux;
}
module.exports={page};
