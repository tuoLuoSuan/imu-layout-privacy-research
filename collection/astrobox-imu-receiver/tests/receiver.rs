use imus5_receiver::receiver::{accept, crc32, export_text};
use serde_json::{Value, json};
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};
static NEXT: AtomicU64 = AtomicU64::new(0);
fn root() -> PathBuf {
    let p = std::env::temp_dir().join(format!(
        "imus5-rx-test-{}-{}",
        std::process::id(),
        NEXT.fetch_add(1, Ordering::Relaxed)
    ));
    assert!(!p.exists());
    fs::create_dir(&p).unwrap();
    p
}
fn clean(p: &PathBuf) {
    assert_eq!(p.parent().unwrap(), std::env::temp_dir());
    assert!(
        p.file_name()
            .unwrap()
            .to_str()
            .unwrap()
            .starts_with("imus5-rx-test-")
    );
    fs::remove_dir_all(p).unwrap();
}
fn packet(body: &str, offset: usize, data: &str) -> Value {
    json!({"p":"S5TX1","t":"0123456789abcdef","s":"1000_abcdef","m":"legacy1","i":0,"n":1,"o":offset,"l":body.len(),"c":crc32(body.as_bytes()),"d":data})
}
fn legacy() -> String {
    json!({"schema_version":1,"session_id":"1000_abcdef","rows":[[0,1.234567890123,2,3,"visible"]]})
        .to_string()
}
#[test]
fn duplicate_chunks_and_restart_resume_exactly() {
    let p = root();
    let text = legacy();
    let middle = text.len() / 2;
    let a = packet(&text, 0, &text[..middle]);
    assert_eq!(accept(&p, &a.to_string()).unwrap().offset, middle);
    assert_eq!(accept(&p, &a.to_string()).unwrap().offset, middle);
    let b = packet(&text, middle, &text[middle..]);
    assert_eq!(accept(&p, &b.to_string()).unwrap().state, "part_complete");
    assert_eq!(accept(&p, &a.to_string()).unwrap().offset, text.len());
    let mut out = Vec::new();
    export_text(&p, "0123456789abcdef", &mut out).unwrap();
    let wire = String::from_utf8(out).unwrap();
    assert!(wire.starts_with("IMU9P|1|1000_abcdef|"));
    clean(&p);
}
#[test]
fn conflicting_retry_and_traversal_never_replace_persisted_bytes() {
    let p = root();
    let text = legacy();
    let a = packet(&text, 0, &text[..20]);
    accept(&p, &a.to_string()).unwrap();
    let mut wrong = a.clone();
    wrong["d"] = json!("XXXXXXXXXXXXXXXXXXXX");
    assert!(accept(&p, &wrong.to_string()).is_err());
    wrong = a.clone();
    wrong["t"] = json!("../../secret");
    assert!(accept(&p, &wrong.to_string()).is_err());
    wrong = a.clone();
    wrong["o"] = json!(99);
    assert!(accept(&p, &wrong.to_string()).is_err());
    assert_eq!(accept(&p, &a.to_string()).unwrap().offset, 20);
    clean(&p);
}
#[test]
fn checksum_failure_is_not_acknowledged_and_export_requires_all_parts() {
    let p = root();
    let text = legacy();
    let mut a = packet(&text, 0, &text);
    a["c"] = json!("00000000");
    assert!(accept(&p, &a.to_string()).is_err());
    assert!(export_text(&p, "0123456789abcdef", &mut Vec::new()).is_err());
    clean(&p);
}
#[test]
fn v2_manifest_identity_and_part_count_are_enforced() {
    let p = root();
    let text=json!({"kind":"manifest","schema_version":2,"session_id":"1000_abcdef","files":["../../evil"]}).to_string();
    let mut a = packet(&text, 0, &text);
    a["m"] = json!("v2");
    a["n"] = json!(2);
    assert!(accept(&p, &a.to_string()).is_err());
    clean(&p);
}
#[test]
fn crc_standard_vector() {
    assert_eq!(crc32(b"123456789"), "cbf43926");
}
