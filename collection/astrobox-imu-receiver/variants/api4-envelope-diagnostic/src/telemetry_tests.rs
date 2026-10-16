use crate::telemetry::Observation;

#[test]
fn event_delivery_is_distinct_from_parse_persist_and_reply_submission(){
 let mut s=Observation::default();s.event(r#"{"p":"S5TX1","d":"private-xyz"}"#);
 assert_eq!((s.events,s.packets,s.stored,s.replies),(1,0,0,0));
 s.step("packet");s.step("stored");s.step("reply_queued");
 assert_eq!((s.events,s.packets,s.stored,s.replies),(1,1,1,1));
 assert!(s.lines()[1].contains("回复提交 1"));
}
#[test]
fn ignored_and_rejected_events_never_count_as_saved_or_replied(){
 let mut s=Observation::default();s.event("not json");s.step("ignored");s.step("rejected");s.step("reply_error");
 assert_eq!((s.ignored,s.rejected,s.reply_errors),(1,1,1));assert_eq!((s.stored,s.replies),(0,0));
}
#[test]
fn payload_shape_reports_only_structural_categories_without_values(){
 for (payload,label) in [(r#"{"data":{"secret":"no-print"}}"#,"data为对象"),(r#"{"data":"no-print"}"#,"data为文本"),("bad", "JSON无效"),("[]","JSON数组")]{
  let mut s=Observation::default();s.event(payload);assert!(s.stage.contains(label),"{}",s.stage);
  assert!(!s.log_line().contains("no-print"));assert!(!s.lines().join(" ").contains("no-print"));
 }
}
#[test]
fn oversized_payload_is_not_parsed_and_diagnostic_remains_bounded(){
 let mut s=Observation::default();s.event(&"secret".repeat(10000));
 assert_eq!(s.bytes,60000);assert!(s.stage.contains("过大"));assert!(s.log_line().len()<500);assert!(!s.log_line().contains("secret"));
}

#[test]
fn ignored_event_keeps_controlled_envelope_structure_without_message_values(){
 let mut s=Observation::default();
 s.event(r#"{"payload":"{\"p\":\"S5TX1\",\"d\":\"private-xyz\"}","device_addr":"private-device","pkg_name":"private-package"}"#);
 s.step("ignored");
 let line=s.log_line();
 assert!(line.contains("payload=text-json(object{d=text,p=S5TX1})"),"{line}");
 assert!(line.contains("device_addr=text"));
 assert!(!line.contains("private-"));
 assert_eq!((s.events,s.packets,s.stored,s.replies),(1,0,0,0));
}
#[test]
fn structural_observation_hides_unknown_keys_and_limits_nesting(){
 let mut s=Observation::default();
 s.event(r#"{"private-key-as-field":{"payload":{"payload":{"p":"S5TX1","d":"private-xyz"}}}}"#);
 s.step("ignored");let line=s.log_line();
 assert!(line.contains("other=object"));assert!(!line.contains("private-"));assert!(line.len()<1600);
}

#[test]
fn wide_structures_and_nested_json_strings_keep_a_fixed_summary_bound(){
 let fields:serde_json::Map<String,serde_json::Value>=(0..100).map(|i|(format!("private-{i}"),serde_json::json!({"payload":{"content":"private-xyz"}}))).collect();
 let payload=serde_json::Value::Object(fields).to_string();
 let mut s=Observation::default();s.event(&payload);s.step("ignored");
 assert!(s.structure.len()<=640);assert!(!s.log_line().contains("private-"));
 assert_eq!((s.packets,s.stored,s.replies),(0,0,0));
}
