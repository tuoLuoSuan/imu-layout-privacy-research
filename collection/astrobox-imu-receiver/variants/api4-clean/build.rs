use std::{env, fs, path::PathBuf};
fn once(source: String, from: &str, to: &str) -> String {
    assert_eq!(source.matches(from).count(), 1, "preserved source marker changed: {from}");
    source.replacen(from, to, 1)
}
fn main() {
    let root = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let parent = root.join("../api4/src/host.rs");
    let receive = root.join("../api4-envelope-adapter/src/receive.rs");
    println!("cargo:rerun-if-changed={}", parent.display());
    println!("cargo:rerun-if-changed={}", receive.display());
    let source = fs::read_to_string(parent).unwrap();
    let mut source = once(source,
        "//! Ordinary AstroBox API level 4 adapter. No firmware/transport/network or raw file extraction.",
        "// Ordinary API4 daily receiver; generated from preserved host and 0.2.3 receive path.");
    source = once(source, "v0.2.0 · 普通消息 · 本地保存", "v0.2.4 · 本地接收");
    source = once(source, "        .child(text(&s.feedback))\n", "");
    source = once(source, "        .child(button(\"界面检查（无需手表）\", \"probe\"))\n", "");
    source = once(source, ".child(text(&s.status))",
        ".child(text(if s.status == \"先点界面检查，再准备接收\" { \"准备接收手表记录\" } else { &s.status }))");
    source = once(source, "接收已准备（单设备）", "接收已准备");
    source = once(source, "切换已接收记录", "下一条记录");
    source = once(source, "保存完整会话到文件…", "保存文件…");
    source = once(source, "手表：记录 → 导出 → 蓝牙传输。传完后在此保存TXT，再交电脑核验。",
        "手表选择蓝牙传输，接收完成后保存文件。");
    source = once(source, "接收完成不等于采集质量通过。文件和原记录保留；首次只传既有短记录。",
        "保存到手机后，可复制文件到电脑。");
    let a = source.find("async fn receive(payload: String) {").unwrap();
    let b = source[a..].find("async fn save() {").unwrap() + a;
    source.replace_range(a..b, &(fs::read_to_string(receive).unwrap() + "\n"));
    fs::write(PathBuf::from(env::var("OUT_DIR").unwrap()).join("host.rs"), source).unwrap();
}
