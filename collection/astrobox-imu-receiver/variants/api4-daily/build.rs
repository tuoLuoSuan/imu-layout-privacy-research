use std::{env,fs,path::PathBuf};
mod baseline {
    include!("../api4-clean/build.rs");
    pub fn generate() { main(); }
}
fn main() {
    baseline::generate();
    let root=PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let ui=root.join("src/render_ui.rs");
    println!("cargo:rerun-if-changed={}",ui.display());
    println!("cargo:rerun-if-changed={}",root.join("../api4-clean/build.rs").display());
    let output=PathBuf::from(env::var("OUT_DIR").unwrap()).join("host.rs");
    let mut source=fs::read_to_string(&output).unwrap();
    let start=source.find("fn render() {").unwrap();
    let end=start+source[start..].find("async fn prepare() {").unwrap();
    source.replace_range(start..end,&(fs::read_to_string(ui).unwrap()+"\n"));
    fs::write(output,source).unwrap();
}
