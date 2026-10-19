//! Cross-language synthetic replay, no host or device calls.
use imu_joint_bridge::protocol::{Server,parse_json};
use serde_json::{Value,json};
use std::io::Write;
fn main()->Result<(),Box<dyn std::error::Error>>{
 let args:Vec<_>=std::env::args().collect();let input=std::fs::read_to_string(&args[1])?;let mut file=std::fs::OpenOptions::new().write(true).create_new(true).open(&args[2])?;
 let p0=1_792_300_000_000_000u64;let mut s=Server::default();
 writeln!(file,"{}",json!({"kind":"header","schema_version":1,"format":"imu_joint_bridge_v1","native_sid":"synthetic-native","watch_package":"org.imuresearch.s5joint","synthetic":true,"physical_clock_accepted":false}))?;
 let a=s.native(json!({"kind":"native_clock_req","sid":"synthetic-native","seq":0,"nonce":"synthetic-0","n1_ns":10000000000u64}),p0+1000,p0+1100)?;writeln!(file,"{}",a.journal)?;
 for line in input.lines(){let v:Value=parse_json(line)?;let p2=v.get("w1_ms").and_then(Value::as_u64).map(|w|w*1000+1000).unwrap_or(p0);let a=s.watch(v,p2,p2+100)?;writeln!(file,"{}",a.journal)?;file.flush()?;file.sync_all()?;}
 if !s.complete(){return Err("synthetic watch did not seal".into());}
 let a=s.native(json!({"kind":"native_clock_req","sid":"synthetic-native","seq":1,"nonce":"synthetic-1","n1_ns":40000000000u64}),p0+30001000,p0+30001100)?;writeln!(file,"{}",a.journal)?;file.flush()?;file.sync_all()?;
 println!("{}",json!({"synthetic":true,"actual_Rust_protocol_accepted_actual_JS_packets":true,"rows":s.rows(),"physical_clock_accepted":false}));Ok(())
}
