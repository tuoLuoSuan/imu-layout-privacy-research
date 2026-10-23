const ROOT='internal://files/';
function safe(s){return typeof s==='string'&&/^[A-Za-z0-9_-]{1,64}$/.test(s);}
function owned(head,e){
 if(!head||head.kind!=='head'||head.schema_version!==1||!safe(head.sid)||!safe(head.native_sid)||head.sid!==e.sid||(e.native_sid!==null&&head.native_sid!==e.native_sid)||!Number.isSafeInteger(head.started_epoch_ms))return false;
 if(e.storage_layout==='legacy_flat'){
  const keys=['kind','schema_version','sid','native_sid','started_epoch_ms','requested_duration_ms','app_version','sensor_path','requested_interval','acceleration_unit','axis_convention','hardware_timestamp','wrist'];
  return e.dir===ROOT&&Object.keys(head).sort().join('|')===keys.sort().join('|')&&typeof head.app_version==='string'&&/^0\.2\.[0-9]+$/.test(head.app_version)&&[20000,60000,120000,300000,600000].indexOf(head.requested_duration_ms)>=0&&head.sensor_path==='generic'&&head.requested_interval==='high'&&head.acceleration_unit==='unknown'&&head.axis_convention==='unverified'&&head.hardware_timestamp===false&&head.wrist==='not_recorded';
 }
 return e.dir===ROOT+'s5joint_'+head.native_sid+'_'+head.sid+'/'&&head.storage_strategy==='isolated_session_directory'&&head.storage_root_uri===e.dir;
}
function location(t){
 if(!safe(t.native_sid)||!safe(t.sid))throw Error('记录身份无效');
 const kind=t.storage_layout||'isolated_session_directory';
 if(['legacy_flat','isolated_session_directory'].indexOf(kind)<0)throw Error('记录存储格式无效');
 return {native_sid:t.native_sid,sid:t.sid,storage_layout:kind,dir:kind==='legacy_flat'?ROOT:ROOT+'s5joint_'+t.native_sid+'_'+t.sid+'/'};
}
module.exports={owned:owned,location:location};
