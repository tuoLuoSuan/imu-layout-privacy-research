use std::{env,fs,path::PathBuf};
fn once(source:String,from:&str,to:&str)->String{assert_eq!(source.matches(from).count(),1,"preserved source marker changed: {from}");source.replacen(from,to,1)}
fn main(){
 let root=PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());let parent=root.join("../api4/src/host.rs");
 println!("cargo:rerun-if-changed={}",parent.display());println!("cargo:rerun-if-changed=src/receive.rs");
 let source=fs::read_to_string(parent).unwrap();
 let mut source=once(source,"//! Ordinary AstroBox API level 4 adapter. No firmware/transport/network or raw file extraction.","// Ordinary API4 receiver with bounded stage observations; generated from preserved 0.2.0.");
 source=once(source,"v0.2.0 · 普通消息 · 本地保存","v0.2.1 · 接收阶段诊断 · 本地保存");
 source=once(source,"        .child(text(&s.feedback))","        .child(text(&crate::telemetry::snapshot().lines()[0]))\n        .child(text(&crate::telemetry::snapshot().lines()[1]))\n        .child(text(&crate::telemetry::snapshot().lines()[2]))\n        .child(text(\"计数含重发；回复提交不等于手表收到\"))\n        .child(text(&s.feedback))");
 let a=source.find("async fn receive(payload: String) {").unwrap();let b=source[a..].find("async fn save() {").unwrap()+a;
 source.replace_range(a..b,&(fs::read_to_string(root.join("src/receive.rs")).unwrap()+"\n"));
 let out=PathBuf::from(env::var("OUT_DIR").unwrap()).join("host.rs");fs::write(out,source).unwrap();
}
