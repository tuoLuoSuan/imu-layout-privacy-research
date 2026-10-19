use imu_joint_bridge::protocol::{Server,crc32};
use serde_json::json;
#[test]fn long_session_exceeds_old_clock_and_row_limits_but_keeps_crc_and_end_counts(){
 let mut s=Server::default();let base=1_792_300_000_000u64;
 for seq in 0..1100 {s.native(json!({"kind":"native_clock_req","sid":"long-native","seq":seq,"nonce":format!("n-{seq}"),"n1_ns":10_000_000_000u64+seq*1_000_000_000}),base*1000+seq*1_000_000,base*1000+seq*1_000_000+100).unwrap();}
 let hello=s.watch(json!({"p":"J_HELLO1","sid":"long-watch","w1_ms":base,"duration_ms":600000}),base*1000,base*1000+100).unwrap();assert_eq!(hello.reply["duration_ms"],600000);
 for seq in 0..300 {let w=base+seq*2000;let r=s.watch(json!({"p":"J_CLK_REQ1","sid":"long-watch","native_sid":"long-native","seq":seq,"w1_ms":w}),w*1000,w*1000+100).unwrap().reply;s.watch(json!({"p":"J_CLK_OBS1","sid":"long-watch","native_sid":"long-native","seq":seq,"w1_ms":w,"w4_ms":w+1,"p2_us":r["p2_us"],"p3_us":r["p3_us"]}),w*1000+1000,w*1000+1100).unwrap();}
 for block in 0..1250 {let rows:Vec<_>=(0..8).map(|j|{let n=block*8+j;json!([n,base+n*60,1.23456789012345,2.5,9.81])}).collect();let payload=serde_json::to_string(&rows).unwrap();s.watch(json!({"p":"J_DATA1","sid":"long-watch","native_sid":"long-native","index":block,"crc32":crc32(payload.as_bytes()),"payload":payload}),base*1000,base*1000+100).unwrap();}
 let end=s.watch(json!({"p":"J_END1","sid":"long-watch","native_sid":"long-native","count":10000,"blocks":1250,"start_ms":base,"stop_ms":base+600000,"stop_reason":"duration","clock_observations":300,"acquisition":{"accepted_rows":10000}}),base*1000+600000000,base*1000+600000100).unwrap();assert_eq!(end.reply["saved"],true);assert!(s.complete());
}
