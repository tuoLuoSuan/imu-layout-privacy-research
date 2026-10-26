use crate::{bindings,protocol::{self,Server,PACKAGE,PORT}};
use bindings::exports::astrobox::psys_plugin_v4::{event::{self,EventType},lifecycle,http};
use bindings::astrobox::psys_host_v4::{device,dialog,interconnect,register,ui,http_server};
use std::{io::Write,path::Path,sync::{Mutex,OnceLock},time::{SystemTime,UNIX_EPOCH}};
use serde_json::{Value,json};
const DIR:&str="joint_records";
const VERSION:&str="0.2.5";
struct State{root:Option<String>,addr:Option<String>,generation:u64,preparing:bool,working:bool,server_id:Option<u32>,storage_failed:bool,status:String,core:Server,keys:Vec<String>,selected:usize}
static STATE:OnceLock<Mutex<State>>=OnceLock::new();
fn state()->&'static Mutex<State>{STATE.get_or_init(||Mutex::new(State{root:None,addr:None,generation:0,preparing:false,working:false,server_id:None,storage_failed:false,status:"先点准备，再打开手机联机采集".into(),core:Server::default(),keys:vec![],selected:0}))}
fn stamp()->Option<u64>{SystemTime::now().duration_since(UNIX_EPOCH).ok()?.as_micros().try_into().ok()}
fn change(f:impl FnOnce(&mut State)){if let Ok(mut s)=state().lock(){f(&mut s)}}
fn refresh(){let mut keys:Vec<String>=std::fs::read_dir(DIR).into_iter().flatten().filter_map(Result::ok).filter_map(|e|e.file_name().to_str().map(str::to_owned)).filter_map(|n|n.strip_suffix(".jsonl").filter(|s|protocol::valid_sid(s)).map(str::to_owned)).collect();keys.sort();change(|s|{s.keys=keys;s.selected=s.selected.min(s.keys.len().saturating_sub(1));});}
fn text(t:&str)->ui::Element{ui::Element::new(ui::ElementType::P,Some(t)).without_default_styles().size(17).text_color("#53677B")}
fn button(t:&str,id:&str)->ui::Element{ui::Element::new(ui::ElementType::Button,Some(t)).without_default_styles().on(ui::Event::Click,id).bg("#176B6D").text_color("#FFFFFF").size(18).padding(13).radius(14)}
fn render(){
 let Ok(s)=state().lock()else{return};let Some(id)=s.root.clone()else{return};
 let label=if s.keys.is_empty(){"还没有采集记录".into()}else{let key=&s.keys[s.selected];format!("记录 {} / {} · {}",s.selected+1,s.keys.len(),&key[..key.len().min(8)])};
 let prepare_label=if s.core.failed(){"结束连接后准备"}else if s.core.complete(){"准备下一轮"}else{"准备采集"};
 let card=ui::Element::new(ui::ElementType::Div,None).without_default_styles().bg("#FFFFFF").padding(22).radius(24).flex().flex_direction(ui::FlexDirection::Column).gap(14)
  .child(text("手机六轴  ↔  S5 三轴")).child(text(&s.status)).child(button(prepare_label,"prepare"));
 let version_text=format!("连接器 · {}",VERSION);
 let el=ui::Element::new(ui::ElementType::Div,None).without_default_styles().bg("#F2F5F4").flex().flex_direction(ui::FlexDirection::Column).width_full().min_height(620).padding(22).gap(16)
  .child(ui::Element::new(ui::ElementType::P,Some("IMU 联合采集")).without_default_styles().size(28).text_color("#18363D"))
  .child(text(&version_text)).child(card)
  .child(text("准备后打开手机开始采集，再在表上开始。AstroBox保持后台运行。"))
  .child(button("结束连接 · 保留记录","cancel"))
  .child(text(&label)).child(button("查看下一条记录","next")).child(button("单独保存手表日志","save"))
  .child(text("日常在手机点“导出整包”即可；此处保留单独保存入口。"));
 drop(s);ui::render(&id,el);
}
fn journal(sid:&str,fresh:bool,value:&Value)->Result<(),String>{std::fs::create_dir_all(DIR).map_err(|e|e.to_string())?;let p=Path::new(DIR).join(format!("{sid}.jsonl"));let mut options=std::fs::OpenOptions::new();options.write(true);if fresh{options.create_new(true);}else{options.append(true);}let mut file=options.open(p).map_err(|e|e.to_string())?;if fresh{writeln!(file,"{}",json!({"kind":"header","schema_version":1,"format":"imu_joint_bridge_v1","native_sid":sid,"watch_package":PACKAGE,"plugin_clock":"WASI SystemTime UNIX_EPOCH microseconds","native_clock":"elapsedRealtimeNanos","watch_clock":"Date.now callback milliseconds","physical_clock_accepted":false})).map_err(|e|e.to_string())?;}writeln!(file,"{value}").map_err(|e|e.to_string())?;file.flush().and_then(|_|file.sync_all()).map_err(|e|e.to_string())}
async fn prepare(g:u64){
 let devices=device::get_connected_device_list().await;
 if !state().lock().is_ok_and(|s|s.generation==g){return;}
 let mut candidates:Vec<_>=devices.iter().filter(|d|d.name.to_ascii_lowercase().contains("s5")).collect();if candidates.is_empty()&&devices.len()==1{candidates.push(&devices[0]);}
 if candidates.len()!=1{change(|s|{s.preparing=false;s.status="请只连接目标S5后再准备".into();});render();return;}
 let addr=candidates[0].addr.clone();
 if let Err(e)=register::register_interconnect_recv(addr.clone(),PACKAGE.into()).await{change(|s|{if s.generation==g{s.preparing=false;s.status=format!("普通连接未准备：{e}");}});render();return;}
 if !state().lock().is_ok_and(|s|s.generation==g){return;}
 let result=http_server::start(http_server::ServerOptions{port:PORT,bind_all_interfaces:false}).await;
 match result{
  Ok(info)=>{
   let accept=state().lock().is_ok_and(|s|s.generation==g);
   if !accept{let _=http_server::stop(info.id).await;return;}
   if info.host!="127.0.0.1"||info.port!=PORT{let _=http_server::stop(info.id).await;change(|s|{s.preparing=false;s.status="本机连接地址不符，已停止".into();});}
   else{change(|s|{s.addr=Some(addr);s.server_id=Some(info.id);s.preparing=false;s.status="已准备 · 打开手机开始，再在表上开始".into();});}
  },Err(e)=>change(|s|{if s.generation==g{s.preparing=false;s.status=format!("本机连接未启动：{e}");}})
 };render();
}
fn response(status:u16,body:Value)->http_server::Response{http_server::Response{status,headers:vec![http_server::Header{name:"content-type".into(),value:"application/json; charset=utf-8".into()},http_server::Header{name:"cache-control".into(),value:"no-store".into()}],body:body.to_string().into_bytes()}}
fn export_record(server_id:u32,v:Value)->http_server::Response{
 let(sid,nonce)=match protocol::archive_request(&v){Ok(x)=>x,Err(e)=>return response(400,json!({"error":e}))};
 let Ok(s)=state().lock()else{return response(503,json!({"error":"state unavailable"}));};
 if s.server_id!=Some(server_id){return response(503,json!({"error":"not prepared"}));}
 let path=Path::new(DIR).join(format!("{sid}.jsonl"));
 let Ok(meta)=std::fs::metadata(&path)else{return response(404,json!({"error":"session journal not found"}));};
 if meta.len()>4_194_304{return response(413,json!({"error":"session journal exceeds export limit"}));}
 let Ok(raw)=std::fs::read(path)else{return response(500,json!({"error":"journal read failed"}));};
 if raw.len()>4_194_304{return response(413,json!({"error":"journal grew beyond limit"}));}
 let header=std::str::from_utf8(&raw).ok().and_then(|t|t.lines().next()).and_then(|t|protocol::parse_json(t).ok());
 if !header.is_some_and(|h|h["kind"]=="header"&&h["native_sid"]==sid){return response(409,json!({"error":"journal identity mismatch"}));}
 http_server::Response{status:200,headers:vec![http_server::Header{name:"content-type".into(),value:"application/x-ndjson; charset=utf-8".into()},http_server::Header{name:"cache-control".into(),value:"no-store".into()},http_server::Header{name:"x-imu-session".into(),value:sid},http_server::Header{name:"x-imu-nonce".into(),value:nonce},http_server::Header{name:"x-imu-crc32".into(),value:protocol::crc32(&raw)}],body:raw}
}
pub struct Plugin;
impl lifecycle::Guest for Plugin{async fn on_load(){refresh();}}
impl http::Guest for Plugin{
 async fn handle(server_id:u32,request:http_server::Request)->http_server::Response{
  let p2=stamp();
  if request.method!="POST"||!["/bridge","/export"].contains(&request.path.as_str())||!request.query.is_empty()||request.body.len()>4096{return response(400,json!({"error":"unexpected local request"}));}
  let Ok(body)=std::str::from_utf8(&request.body)else{return response(400,json!({"error":"invalid UTF-8"}));};
  let Ok(v)=protocol::parse_json(body)else{return response(400,json!({"error":"invalid JSON"}));};
  if request.path=="/export"{return export_record(server_id,v);}
  let result={let Ok(mut s)=state().lock()else{return response(503,json!({"error":"state unavailable"}));};
   if s.server_id!=Some(server_id)||s.addr.is_none()||s.storage_failed{return response(503,json!({"error":"not prepared"}));}
   let (Some(p2),Some(p3))=(p2,stamp())else{return response(503,json!({"error":"clock unavailable"}));};
   match s.core.native(v,p2,p3){Ok(a)=>{let sid=s.core.sid().unwrap().to_string();match journal(&sid,a.fresh,&a.journal){Ok(())=>{s.status=if s.core.failed(){format!("腕部失败（{}），部分日志保留；结束连接后导出",s.core.failure_stage().unwrap_or("unknown"))}else{format!("手机已连，腕部已保存 {} 条{}",s.core.rows(),if s.core.complete(){"，可保存日志"}else{""})};response(200,a.reply)},Err(e)=>{s.storage_failed=true;s.status=format!("日志保存失败，部分保留：{e}");response(500,json!({"error":"journal write failed"}))}}},Err(e)=>response(409,json!({"error":e}))}
  };refresh();render();result
 }
}
async fn receive(payload:String,p2:Option<u64>){
 let Some(v)=protocol::unwrap(&payload)else{return;};
 let action={let Ok(mut s)=state().lock()else{return;};let Some(addr)=s.addr.clone()else{return;};if s.storage_failed{return;}
  let identity=(v.get("sid").cloned(),v.get("native_sid").cloned());let (Some(p2),Some(p3))=(p2,stamp())else{return;};
  match s.core.watch(v,p2,p3){Ok(a)=>{let sid=s.core.sid().unwrap().to_string();if let Err(e)=journal(&sid,false,&a.journal){s.storage_failed=true;s.status=format!("日志保存失败，部分保留：{e}");None}else{s.status=if s.core.failed(){format!("腕部失败（{}），部分日志保留；结束连接后导出",s.core.failure_stage().unwrap_or("unknown"))}else{format!("腕部已保存 {} 条{}",s.core.rows(),if s.core.complete(){"，等待手机收尾"}else{""})};Some((addr,s.generation,a.reply))}},Err(e)=>{s.status=format!("消息未接受：{e}");Some((addr,s.generation,json!({"p":"J_ERR1","sid":identity.0,"native_sid":identity.1,"error":e})))}}
 };
 if let Some((addr,g,reply))=action{if state().lock().is_ok_and(|s|s.generation==g&&s.addr.is_some()){if interconnect::send_qaic_message(addr,PACKAGE.into(),reply.to_string()).await.is_err(){change(|s|s.status="回复未送出，部分日志和表端文件保留".into());}}}
 refresh();render();
}
async fn save(){
 let sid=state().lock().ok().and_then(|s|s.keys.get(s.selected).cloned());
 let result=async{let sid=sid.ok_or("尚无日志")?;let bytes=std::fs::read(Path::new(DIR).join(format!("{sid}.jsonl"))).map_err(|e|e.to_string())?;if bytes.len()>4_194_304{return Err("日志超出本次导出上限，原件保留".into());}
 let filter=dialog::FilterConfig{multiple:false,extensions:vec!["jsonl".into()],default_directory:String::new(),default_file_name:format!("imu_joint_bridge_{sid}.jsonl")};let target=dialog::save_file_start(filter).await.map_err(|_|"保存已取消".to_string())?;
 let written=async{for c in bytes.chunks(8192){dialog::save_file_write_chunk(target.session_id,c.to_vec()).await.map_err(|_|"写文件失败".to_string())?;}dialog::save_file_finish(target.session_id).await.map_err(|_|"结束保存失败".to_string())}.await;
 if written.is_err(){dialog::save_file_abort(target.session_id).await;}written}.await;
 change(|s|{s.working=false;s.status=match result{Ok(())=>"日志已导出，原件保留；交电脑核验".into(),Err(e)=>e};});render();
}
impl event::Guest for Plugin{
 async fn on_event(kind:EventType,payload:String)->String{let p2=stamp();if matches!(kind,EventType::InterconnectMessage){receive(payload,p2).await;}String::new()}
 async fn on_ui_event(id:String,event:ui::Event,_payload:String)->String{
  if !matches!(event,ui::Event::Click){return String::new();}
  let mut stop_id=None;
  let run={let Ok(mut s)=state().lock()else{return String::new()};match id.as_str(){
   "cancel"=>{s.generation+=1;s.addr=None;s.preparing=false;stop_id=s.server_id.take();s.status="连接已停止，部分日志保留，可导出".into();false},
   "prepare" if !s.preparing&&!s.working=>{if s.server_id.is_some(){if s.core.complete(){s.generation+=1;s.core=Server::default();s.storage_failed=false;s.status="已准备新一轮 · 请在手机开始".into();}else{s.status=if s.core.failed(){"上一轮腕部失败；先结束连接，再开始新记录".into()}else if s.core.sid().is_some(){"本轮尚未结束；需要重来时先点结束连接，记录会保留".into()}else{"已准备 · 请在手机开始".into()};}false}else{s.generation+=1;s.preparing=true;s.storage_failed=false;s.core=Server::default();s.status="正在连接S5与手机".into();true}},
   "next"=>{if !s.keys.is_empty(){s.selected=(s.selected+1)%s.keys.len();}false},
   "save" if !s.working=>{if s.addr.is_some()&&!s.core.complete(){s.status="请先停止连接，再导出部分日志".into();false}else{s.working=true;true}},_=>false}};
  render();if let Some(sid)=stop_id{let _=http_server::stop(sid).await;}
  if run{if id=="prepare"{let g=state().lock().unwrap().generation;prepare(g).await;}else if id=="save"{save().await;}}
  String::new()
 }
 async fn on_ui_render(id:String){change(|s|s.root=Some(id));refresh();render();}
 async fn on_card_render(_id:String){}
}
bindings::export!(Plugin with_types_in bindings);
