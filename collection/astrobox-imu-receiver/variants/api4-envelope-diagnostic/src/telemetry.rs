#[derive(Clone,Default,Debug)]
pub struct Observation {
 pub events:u64,pub packets:u64,pub stored:u64,pub replies:u64,pub ignored:u64,pub rejected:u64,pub reply_errors:u64,
 pub bytes:usize,pub stage:String,pub structure:String,
}
impl Observation {
 pub fn event(&mut self,payload:&str){
  self.events=self.events.saturating_add(1);self.bytes=payload.len();
  let shape=if payload.len()>8192 {"消息过大"}else{match serde_json::from_str::<serde_json::Value>(payload){
   Ok(serde_json::Value::Object(v))=>if v.contains_key("p"){"JSON对象含p"}else{match v.get("data"){
    Some(serde_json::Value::Object(_))=>"JSON对象，data为对象",Some(serde_json::Value::String(_))=>"JSON对象，data为文本",_=>"JSON对象，无已知包装"}},
   Ok(serde_json::Value::String(_))=>"JSON文本包装",Ok(serde_json::Value::Array(_))=>"JSON数组",Ok(_)=>"JSON其它类型",Err(_)=>"JSON无效"}};
  self.structure=crate::structure::describe(payload);
  self.stage=format!("消息已进入插件：{shape}；结构：{}",self.structure);
 }
 pub fn step(&mut self,stage:&str){
  if stage=="ignored" {
   self.ignored=self.ignored.saturating_add(1);
   self.stage=format!("收到消息但未识别为记录包；结构：{}",self.structure);
   return;
  }
  self.stage=match stage {
   "packet"=>{self.packets=self.packets.saturating_add(1);"正在验证并保存记录包"},
   "stored"=>{self.stored=self.stored.saturating_add(1);"保存通过，正在提交回复"},
   "reply_queued"=>{self.replies=self.replies.saturating_add(1);"回复已交给AstroBox，待手表推进"},
   "reply_error"=>{self.reply_errors=self.reply_errors.saturating_add(1);"回复提交失败，请保留诊断"},
   "rejected"=>{self.rejected=self.rejected.saturating_add(1);"记录包未通过，原接收文件保留"},
   "ignored"=>{self.ignored=self.ignored.saturating_add(1);"收到消息但未识别为记录包"},
   "unregistered"=>"收到消息时尚未准备接收",
   _=>"处理状态已更新",
  }.into();
 }
 pub fn lines(&self)->[String;3]{[
  format!("收到消息 {} · 识别记录包 {}",self.events,self.packets),
  format!("保存通过 {} · 回复提交 {}",self.stored,self.replies),
  if self.stage.is_empty(){"最近一步：尚未收到手表消息".into()}else{format!("最近一步：{}",self.stage)},
 ]}
 pub fn log_line(&self)->String{format!("[S5RX] events={} packets={} stored={} replies={} ignored={} rejected={} reply_errors={} bytes={} phase={}",self.events,self.packets,self.stored,self.replies,self.ignored,self.rejected,self.reply_errors,self.bytes,self.stage)}
}

use std::sync::{Mutex,OnceLock};
static OBSERVATION:OnceLock<Mutex<Observation>>=OnceLock::new();
pub fn snapshot()->Observation{OBSERVATION.get_or_init(||Mutex::new(Observation::default())).lock().map(|s|s.clone()).unwrap_or_default()}
pub fn update(f:impl FnOnce(&mut Observation)){
 let message={let Ok(mut s)=OBSERVATION.get_or_init(||Mutex::new(Observation::default())).lock()else{return;};f(&mut s);s.log_line()};
 println!("{message}");
}
