//! Bound transport and clocks. All acceptance flags are observations, not physical calibration.
use serde_json::{Value,json};
use serde::de::{self,Deserialize,Deserializer,Visitor,MapAccess,SeqAccess};
use std::collections::BTreeMap;
pub const PACKAGE:&str="org.imuresearch.s5joint";
pub const PORT:u16=38741;
struct Strict(Value);
impl<'de> Deserialize<'de> for Strict{
 fn deserialize<D:Deserializer<'de>>(d:D)->Result<Self,D::Error>{
  struct V;
  impl<'de> Visitor<'de> for V{type Value=Strict;
   fn expecting(&self,f:&mut std::fmt::Formatter)->std::fmt::Result{f.write_str("JSON without duplicate keys")}
   fn visit_bool<E:de::Error>(self,v:bool)->Result<Strict,E>{Ok(Strict(json!(v)))}
   fn visit_i64<E:de::Error>(self,v:i64)->Result<Strict,E>{Ok(Strict(json!(v)))}
   fn visit_u64<E:de::Error>(self,v:u64)->Result<Strict,E>{Ok(Strict(json!(v)))}
   fn visit_f64<E:de::Error>(self,v:f64)->Result<Strict,E>{if !v.is_finite(){return Err(E::custom("nonfinite value"));}Ok(Strict(json!(v)))}
   fn visit_str<E:de::Error>(self,v:&str)->Result<Strict,E>{Ok(Strict(json!(v)))}
   fn visit_string<E:de::Error>(self,v:String)->Result<Strict,E>{Ok(Strict(json!(v)))}
   fn visit_unit<E:de::Error>(self)->Result<Strict,E>{Ok(Strict(Value::Null))}
   fn visit_none<E:de::Error>(self)->Result<Strict,E>{Ok(Strict(Value::Null))}
   fn visit_seq<A:SeqAccess<'de>>(self,mut a:A)->Result<Strict,A::Error>{let mut v=Vec::new();while let Some(x)=a.next_element::<Strict>()?{v.push(x.0);}Ok(Strict(Value::Array(v)))}
   fn visit_map<A:MapAccess<'de>>(self,mut a:A)->Result<Strict,A::Error>{let mut v=serde_json::Map::new();while let Some((k,x))=a.next_entry::<String,Strict>()?{if v.contains_key(&k){return Err(de::Error::custom("duplicate JSON key"));}v.insert(k,x.0);}Ok(Strict(Value::Object(v)))}
  }
  d.deserialize_any(V)
 }
}
pub fn parse_json(s:&str)->Result<Value,serde_json::Error>{let mut d=serde_json::Deserializer::from_str(s);let v=Strict::deserialize(&mut d)?;d.end()?;Ok(v.0)}
pub fn valid_sid(s:&str)->bool{!s.is_empty()&&s.len()<=64&&s.bytes().all(|b|b.is_ascii_alphanumeric()||b==b'_'||b==b'-')}
pub fn crc32(bytes:&[u8])->String{let mut c=0xffff_ffffu32;for b in bytes{c^=*b as u32;for _ in 0..8{c=(c>>1)^if c&1==1{0xedb88320}else{0};}}format!("{:08x}",!c)}
pub fn archive_request(v:&Value)->Result<(String,String),String>{keys(v,&["kind","sid","nonce"])?;if string(v,"kind")?!="export_session"{return Err("invalid export request".into());}Ok((identity(v,"sid")?,identity(v,"nonce")?))}
fn keys(v:&Value,want:&[&str])->Result<(),String>{let o=v.as_object().ok_or("object required")?;if o.len()!=want.len()||!want.iter().all(|k|o.contains_key(*k)){return Err("unexpected fields".into());}Ok(())}
fn u(v:&Value,k:&str)->Result<u64,String>{v[k].as_u64().ok_or_else(||format!("invalid integer {k}"))}
fn string<'a>(v:&'a Value,k:&str)->Result<&'a str,String>{v[k].as_str().ok_or_else(||format!("invalid string {k}"))}
fn identity(v:&Value,k:&str)->Result<String,String>{let s=string(v,k)?;if !valid_sid(s){return Err("invalid identity".into());}Ok(s.into())}
pub fn unwrap(payload:&str)->Option<Value>{
 if payload.len()>16000{return None;}let v:Value=parse_json(payload).ok()?;
 if v.get("p").is_some(){return Some(v);}
 if let Some(s)=v.as_str(){return unwrap(s);}
 if let Some(s)=v.get("data").and_then(Value::as_str){return unwrap(s);}
 if let Some(o)=v.as_object(){if o.get("pkgName").and_then(Value::as_str)!=Some(PACKAGE){return None;}let c:Vec<Value>=o.values().filter_map(Value::as_str).filter(|s|s.starts_with('{')).filter_map(unwrap).collect();if c.len()==1{return c.into_iter().next();}}
 None
}
pub struct Action{pub reply:Value,pub journal:Value,pub fresh:bool}
#[derive(Default)]
pub struct Server{
 native_sid:Option<String>,native_next:u64,watch_sid:Option<String>,data:BTreeMap<u64,(String,String)>,rows:u64,first_time:u64,last_time:u64,
 clock_next:u64,pending:Option<Value>,clock_count:u64,end:Option<Value>,failure:Option<Value>,
}
impl Server{
 pub fn sid(&self)->Option<&str>{self.native_sid.as_deref()}
 pub fn rows(&self)->u64{self.rows}
 pub fn complete(&self)->bool{self.end.is_some()}
 pub fn failed(&self)->bool{self.failure.is_some()}
 pub fn failure_stage(&self)->Option<&str>{self.failure.as_ref().and_then(|f|f.get("stage")).and_then(Value::as_str)}
 pub fn native(&mut self,v:Value,p2:u64,p3:u64)->Result<Action,String>{
  keys(&v,&["kind","sid","seq","nonce","n1_ns"])?;
  if string(&v,"kind")?!="native_clock_req"{return Err("invalid native kind".into());}
  let sid=identity(&v,"sid")?;let seq=u(&v,"seq")?;let nonce=identity(&v,"nonce")?;let n1=u(&v,"n1_ns")?;
  if seq>=2048||n1==0||p2<1_000_000_000_000_000||p3<p2||p3-p2>5_000_000{return Err("native clock bounds invalid".into());}
  if self.native_sid.as_ref().is_some_and(|s|s!=&sid)||seq!=self.native_next{return Err("native session/sequence mismatch".into());}
  let fresh=self.native_sid.is_none();self.native_sid=Some(sid.clone());self.native_next+=1;
  let reply=json!({"kind":"native_clock_reply","sid":sid,"seq":seq,"nonce":nonce,"n1_ns":n1,"p2_us":p2,"p3_us":p3,"watch_sid":self.watch_sid,"watch_rows":self.rows,"watch_clock_observations":self.clock_count,"watch_finished":self.complete()||self.failure.is_some(),"watch_failed":self.failure.is_some(),"watch_failure_stage":self.failure_stage(),"watch_stop_reason":self.end.as_ref().map(|e|e["stop_reason"].clone()).or_else(||if self.failure.is_some(){Some(json!("failure"))}else{None}),"physical_clock_accepted":false});
  Ok(Action{reply:reply.clone(),journal:json!({"kind":"native_request","request":v,"reply":reply}),fresh})
 }
 pub fn watch(&mut self,v:Value,p2:u64,p3:u64)->Result<Action,String>{
  let p=string(&v,"p")?;let sid=identity(&v,"sid")?;let native=self.native_sid.clone().ok_or("start native phone recorder first")?;
  if self.failure.is_some()&&p!="J_FAIL1"{return Err("watch session failed; end this session and start a new one".into());}
  if p=="J_HELLO1"{
   let duration=if v.get("duration_ms").is_some(){keys(&v,&["p","sid","w1_ms","duration_ms"])?;u(&v,"duration_ms")?}else{keys(&v,&["p","sid","w1_ms"])?;20000};
   if ![20000,60000,120000,300000,600000].contains(&duration){return Err("unsupported watch duration".into());}
   if u(&v,"w1_ms")?<1_000_000_000_000{return Err("watch wall clock invalid".into());}
   if self.watch_sid.as_ref().is_some_and(|old|old!=&sid){return Err("another watch session active".into());}
   if self.complete()||self.failure.is_some(){return Err("session is already sealed".into());}self.watch_sid=Some(sid.clone());
   let reply=json!({"p":"J_HELLO_ACK1","sid":sid,"native_sid":native,"duration_ms":duration});
   return Ok(Action{reply:reply.clone(),journal:json!({"kind":"watch_hello","request":v,"reply":reply}),fresh:false});
  }
  if self.watch_sid.as_ref()!=Some(&sid)||string(&v,"native_sid")?!=native{return Err("watch session not bound".into());}
  match p{
   "J_FAIL1"=>{
    keys(&v,&["p","sid","native_sid","stage","error","count","blocks","start_ms","stop_ms","stop_reason"])?;
    if self.end.is_some(){return Err("session already sealed".into());}
    if let Some(old)=&self.failure{
     if old==&v{return Ok(Action{reply:json!({"p":"J_FAIL_ACK1","sid":sid,"native_sid":native,"saved":true}),journal:json!({"kind":"watch_failure_duplicate","packet":v}),fresh:false});}
     return Err("conflicting watch failure".into());
    }
    let stage=string(&v,"stage")?;
    if !["unknown","cancel","hello","mkdir","list","head","block","tail","sensor","transport","clock","tick"].contains(&stage){return Err("watch failure stage invalid".into());}
    let message=string(&v,"error")?;if message.is_empty()||message.len()>240{return Err("watch failure message invalid".into());}
    if string(&v,"stop_reason")?!="failure"{return Err("watch failure reason invalid".into());}
    let count=u(&v,"count")?;let blocks=u(&v,"blocks")?;let start=u(&v,"start_ms")?;let stop=u(&v,"stop_ms")?;
    if count>20000||blocks>20000||stop<start||stop-start>900000{return Err("watch failure bounds invalid".into());}
    if count<self.rows||blocks<self.data.len() as u64{return Err("watch failure counts behind received data".into());}
    self.failure=Some(v.clone());
    Ok(Action{reply:json!({"p":"J_FAIL_ACK1","sid":sid,"native_sid":native,"saved":true}),journal:json!({"kind":"watch_failure","packet":v}),fresh:false})
   },
   "J_CLK_REQ1"=>{
    keys(&v,&["p","sid","native_sid","seq","w1_ms"])?;let seq=u(&v,"seq")?;let w1=u(&v,"w1_ms")?;
    if self.complete()||self.pending.is_some()||seq!=self.clock_next||seq>=512||w1<1_000_000_000_000||p2<1_000_000_000_000_000||p3<p2{return Err("watch clock request rejected".into());}
    let reply=json!({"p":"J_CLK_REP1","sid":sid,"native_sid":native,"seq":seq,"w1_ms":w1,"p2_us":p2,"p3_us":p3});self.pending=Some(reply.clone());
    Ok(Action{reply:reply.clone(),journal:json!({"kind":"watch_clock_request","request":v,"reply":reply}),fresh:false})
   },
   "J_CLK_OBS1"=>{
    keys(&v,&["p","sid","native_sid","seq","w1_ms","w4_ms","p2_us","p3_us"])?;let pending=self.pending.as_ref().ok_or("no pending clock request")?;
    for key in ["seq","w1_ms","p2_us","p3_us"]{if v[key]!=pending[key]{return Err("clock echo mismatch".into());}}
    let w1=u(&v,"w1_ms")?;let w4=u(&v,"w4_ms")?;let q2=u(&v,"p2_us")?;let q3=u(&v,"p3_us")?;
    if w4<w1||w4-w1>5000||q3<q2||q3-q2>(w4-w1)*1000+2000{return Err("watch clock regression/timeout/path".into());}
    self.pending=None;self.clock_next+=1;self.clock_count+=1;
    Ok(Action{reply:json!({"p":"J_CLK_ACK1","sid":sid,"native_sid":native,"seq":v["seq"],"saved":true}),journal:json!({"kind":"watch_clock_observation","observation":v}),fresh:false})
   },
   "J_DATA1"=>{
    keys(&v,&["p","sid","native_sid","index","payload","crc32"])?;let i=u(&v,"index")?;let payload=string(&v,"payload")?;let crc=string(&v,"crc32")?;
    if payload.len()>12000||crc32(payload.as_bytes())!=crc{return Err("payload CRC mismatch/size".into());}
    let duplicate=if let Some((old,oldcrc))=self.data.get(&i){if old!=payload||oldcrc!=crc{return Err("conflicting data replay".into());}true}else{
     if self.complete()||i!=self.data.len()as u64{return Err("data block out of order".into());}
     let rows:Vec<Value>=serde_json::from_str(payload).map_err(|_|"payload JSON invalid")?;
     if rows.is_empty()||rows.len()>32||self.rows+rows.len()as u64>20000{return Err("sample bound exceeded".into());}
     let mut next=self.rows;let mut last=self.last_time;
     for row in &rows{let a=row.as_array().ok_or("row required")?;if a.len()!=5||a[0].as_u64()!=Some(next){return Err("sample sequence mismatch".into());}
      let t=a[1].as_u64().ok_or("sample time required")?;if t<1_000_000_000_000||t<=last{return Err("sample clock repeated/reversed".into());}
      if !a[2..].iter().all(|x|x.is_number()&&x.as_f64().is_some_and(f64::is_finite)){return Err("invalid XYZ".into());}
      next+=1;last=t;
     }
     if self.rows==0{self.first_time=rows[0][1].as_u64().unwrap();}self.rows=next;self.last_time=last;self.data.insert(i,(payload.to_string(),crc.to_string()));false
    };
    Ok(Action{reply:json!({"p":"J_DATA_ACK1","sid":sid,"native_sid":native,"index":i,"crc32":crc,"saved":true,"duplicate":duplicate}),journal:json!({"kind":if duplicate{"watch_data_duplicate"}else{"watch_data"},"packet":v}),fresh:false})
   },
   "J_END1"=>{
    keys(&v,&["p","sid","native_sid","count","blocks","start_ms","stop_ms","stop_reason","clock_observations","acquisition"])?;
    if let Some(old)=&self.end{if old!=&v{return Err("conflicting end replay".into());}}
    if u(&v,"count")?!=self.rows||u(&v,"blocks")?!=self.data.len()as u64||u(&v,"clock_observations")?!=self.clock_count{return Err("end count mismatch".into());}
    let start=u(&v,"start_ms")?;let stop=u(&v,"stop_ms")?;
    if start<1_000_000_000_000||stop<start||stop-start>900000||self.last_time>stop||(self.rows>0&&self.first_time<start)||self.pending.is_some(){return Err("end time/pending request mismatch".into());}
    if !["duration","user","hidden","failure"].contains(&string(&v,"stop_reason")?)||!v["acquisition"].is_object(){return Err("end reason/observation invalid".into());}
    self.end=Some(v.clone());
    Ok(Action{reply:json!({"p":"J_END_ACK1","sid":sid,"native_sid":native,"saved":true,"count":self.rows}),journal:json!({"kind":"watch_end","packet":v}),fresh:false})
   },_=>Err("unrelated watch protocol".into())
  }
 }
}
