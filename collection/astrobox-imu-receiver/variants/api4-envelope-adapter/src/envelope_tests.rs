use crate::envelope::unwrap;
use serde_json::{Value,json};
const PACKAGE:&str="org.imuresearch.s5probe";
fn packet()->String{json!({"p":"S5TX1","d":"synthetic-not-device-data"}).to_string()}
fn wrapper(raw:&str)->Value {
    // Field names are synthetic; only their observed types/count and pkgName matter.
    json!({"syntheticA":"synthetic-address","syntheticB":"synthetic-label","syntheticC":raw,"pkgName":PACKAGE})
}
#[test]
fn observed_four_string_shape_delivers_the_unique_inner_packet_byte_exact(){
    let raw=packet();assert_eq!(unwrap(&wrapper(&raw).to_string(),PACKAGE),Some(raw));
}
#[test]
fn prior_direct_string_and_data_text_forms_remain_accepted(){
    let raw=packet();
    for payload in [raw.clone(),json!(raw).to_string(),json!({"data":raw}).to_string()]{
        assert_eq!(unwrap(&payload,PACKAGE),Some(raw.clone()));
    }
}
#[test]
fn mismatched_package_and_ambiguous_packets_are_rejected(){
    let raw=packet();let mut value=wrapper(&raw);
    value["pkgName"]=json!("unrelated-package");assert_eq!(unwrap(&value.to_string(),PACKAGE),None);
    let mut value=wrapper(&raw);value["syntheticA"]=json!(raw);assert_eq!(unwrap(&value.to_string(),PACKAGE),None);
}
#[test]
fn changed_count_nontext_and_deeply_wrapped_content_are_rejected(){
    let raw=packet();let mut value=wrapper(&raw);value.as_object_mut().unwrap().remove("syntheticA");
    assert_eq!(unwrap(&value.to_string(),PACKAGE),None);
    let mut value=wrapper(&raw);value["extra"]=json!("text");assert_eq!(unwrap(&value.to_string(),PACKAGE),None);
    let mut value=wrapper(&raw);value["syntheticA"]=json!(42);assert_eq!(unwrap(&value.to_string(),PACKAGE),None);
    let value=wrapper(&json!({"nested":raw}).to_string());assert_eq!(unwrap(&value.to_string(),PACKAGE),None);
}
#[test]
fn data_object_other_protocol_invalid_and_oversize_are_rejected(){
    for payload in [json!({"data":{"p":"S5TX1"}}).to_string(),wrapper("{\"p\":\"other\"}").to_string(),"bad".into(),"x".repeat(8193)]{
        assert_eq!(unwrap(&payload,PACKAGE),None);
    }
    let raw=json!({"p":"S5TX1","d":"x".repeat(4096)}).to_string();
    assert_eq!(unwrap(&wrapper(&raw).to_string(),PACKAGE),None);
}
