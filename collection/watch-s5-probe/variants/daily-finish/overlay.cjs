// Presentation-only daily finish. Preserve every controller method and core safety mechanism.
function one(s,a,b){if(s.split(a).length!==2)throw Error('Daily finish marker mismatch: '+a.slice(0,100));return s.replace(a,b);}
function core(s){return one(s,"app_version:'0.4.14'","app_version:'0.4.15'");}
function page(s){
 s=one(s,'v0.4.14','v0.4.15');
 s=one(s,'已记录 {{samples}} 条 · 已保存 {{persisted}}','已保存 {{persisted}} / {{samples}} 条');
 s=one(s,'回调到达 {{measured}} 次/秒','{{measured}} 条/秒');
 s=one(s,"{{trashMode ? '回收' : '记录'}} {{recordPosition}} · {{recordTitle}}","{{trashMode ? '回收区' : '记录'}} {{recordPosition}}");
 s=one(s,'onclick="recordAction"><text class="button-text">{{trashMode ? \'恢复记录\' : \'移到回收区\'}}</text>',
  'onclick="openBatch"><text class="button-text">{{trashMode ? \'整理回收\' : \'整理记录\'}}</text>');
 s=one(s,'          <div class="diagnostic-actions"><div class="diagnostic-link" onclick="openBatch"><text class="diagnostic-link-text">批量整理…</text></div><div class="diagnostic-link" onclick="extraAction"><text class="diagnostic-link-text">{{trashMode ? \'永久删除…\' : \'恢复旧版记录\'}}</text></div></div>',
  '          <div if="{{!trashMode}}" class="retry" onclick="extraAction"><text class="parameter-text">找回早期记录</text></div>');
 s=one(s,'已封口 · 尚待外部核验','已保存 · 可导出');
 s=one(s,'正在检查high启动节奏（约5秒）','正在采集 · 正在保存数据');
 return s;
}
module.exports={core,page};
