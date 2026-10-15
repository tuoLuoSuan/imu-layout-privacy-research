//! Portable receiver. Host delivery != persisted ACK; scientific checks remain independent.
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{
    fs::{self, OpenOptions},
    io::{Read, Seek, SeekFrom, Write},
    path::{Path, PathBuf},
};

#[derive(Clone, Deserialize, Serialize, PartialEq, Debug)]
#[serde(deny_unknown_fields)]
pub struct Packet {
    pub p: String,
    pub t: String,
    pub s: String,
    pub m: String,
    pub i: usize,
    pub n: usize,
    pub o: usize,
    pub l: usize,
    pub c: String,
    pub d: String,
}
#[derive(Clone, Deserialize, Serialize, PartialEq, Debug)]
struct Transfer {
    token: String,
    session: String,
    format: String,
    parts: usize,
}
#[derive(Clone, Deserialize, Serialize, PartialEq, Debug)]
struct Part {
    index: usize,
    length: usize,
    crc: String,
}
#[derive(Serialize, Debug)]
pub struct Ack {
    #[serde(rename = "p")]
    pub protocol: String,
    #[serde(rename = "t")]
    pub token: String,
    #[serde(rename = "s")]
    pub session: String,
    #[serde(rename = "i")]
    pub part: usize,
    #[serde(rename = "o")]
    pub offset: usize,
    #[serde(rename = "c")]
    pub crc: String,
    pub state: String,
}
type Result<T> = std::result::Result<T, String>;
fn err<E: std::fmt::Display>(e: E) -> String {
    e.to_string()
}
fn hex(value: &str, length: usize) -> bool {
    value.len() == length
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn token(value: &str) -> Result<()> {
    if !hex(value, 16) {
        return Err("无效传输标识".into());
    }
    Ok(())
}
fn session(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 80
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
}
fn no_link(path: &Path) -> Result<()> {
    if let Ok(m) = fs::symlink_metadata(path) {
        if m.file_type().is_symlink() {
            return Err("拒绝符号链接".into());
        }
    }
    Ok(())
}
fn read(path: &Path) -> Result<Vec<u8>> {
    no_link(path)?;
    let len = fs::metadata(path).map_err(err)?.len();
    if len > 65536 {
        return Err("分段文件过大".into());
    }
    fs::read(path).map_err(err)
}
fn dir(root: &Path, id: &str) -> Result<PathBuf> {
    token(id)?;
    no_link(root)?;
    let p = root.join(id);
    no_link(&p)?;
    Ok(p)
}
fn json_existing<T: serde::de::DeserializeOwned>(path: &Path) -> Result<T> {
    serde_json::from_slice(&read(path)?).map_err(err)
}
fn immutable_json<T: serde::de::DeserializeOwned + Serialize + PartialEq>(
    path: &Path,
    value: &T,
) -> Result<()> {
    no_link(path)?;
    if path.exists() {
        if json_existing::<T>(path)? != *value {
            return Err("传输元数据冲突，原文件保留".into());
        }
        return Ok(());
    }
    let bytes = serde_json::to_vec(value).map_err(err)?;
    let mut f = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)
        .map_err(err)?;
    f.write_all(&bytes).map_err(err)?;
    f.sync_all().map_err(err)
}
pub fn crc32(bytes: &[u8]) -> String {
    let mut crc = !0u32;
    for b in bytes {
        crc ^= *b as u32;
        for _ in 0..8 {
            crc = (crc >> 1) ^ if crc & 1 != 0 { 0xedb88320 } else { 0 };
        }
    }
    format!("{:08x}", !crc)
}
fn part_path(d: &Path, index: usize, suffix: &str) -> PathBuf {
    d.join(format!("part_{index:04}.{suffix}"))
}
fn verify_body(d: &Path, index: usize) -> Result<Vec<u8>> {
    let meta: Part = json_existing(&part_path(d, index, "json"))?;
    let bytes = read(&part_path(d, index, "data"))?;
    if meta.index != index || bytes.len() != meta.length || crc32(&bytes) != meta.crc {
        return Err("接收段缺失或CRC不符".into());
    }
    Ok(bytes)
}
fn validate_manifest(t: &Transfer, body: &[u8]) -> Result<()> {
    let v: Value = serde_json::from_slice(body).map_err(err)?;
    if v.get("session_id").and_then(Value::as_str) != Some(&t.session) {
        return Err("会话身份冲突".into());
    }
    if t.format == "legacy1" {
        if v.get("schema_version").and_then(Value::as_u64) != Some(1)
            || v.get("rows")
                .and_then(Value::as_array)
                .is_none_or(|r| r.len() > 2000)
        {
            return Err("旧记录格式错误".into());
        }
    } else {
        if v.get("kind").and_then(Value::as_str) != Some("manifest")
            || v.get("schema_version").and_then(Value::as_u64) != Some(2)
        {
            return Err("清单格式错误".into());
        }
        let names = v
            .get("files")
            .and_then(Value::as_array)
            .ok_or("缺少文件清单")?;
        if names.len() + 1 != t.parts || names.is_empty() {
            return Err("清单段数错误".into());
        }
        let prefix = format!("s5r_{}_", t.session);
        if names[0].as_str() != Some(format!("{prefix}head.json").as_str()) {
            return Err("清单缺少起始头文件".into());
        }
        let tail =
            names.last().and_then(Value::as_str) == Some(format!("{prefix}tail.json").as_str());
        let blocks = names.len() - 1 - usize::from(tail);
        for (i, name) in names.iter().enumerate() {
            let expected = if i == 0 {
                format!("{prefix}head.json")
            } else if tail && i == names.len() - 1 {
                format!("{prefix}tail.json")
            } else {
                format!("{prefix}b{:04}.json", i - 1)
            };
            if name.as_str() != Some(expected.as_str()) || blocks > 400 {
                return Err("清单路径或块顺序无效".into());
            }
        }
    }
    Ok(())
}
pub fn is_complete(root: &Path, key: &str) -> Result<bool> {
    let d = dir(root, key)?;
    let t: Transfer = json_existing(&d.join("transfer.json"))?;
    if t.token != key || !session(&t.session) || t.parts == 0 || t.parts > 403 {
        return Err("接收索引损坏".into());
    }
    for index in 0..t.parts {
        let bytes = verify_body(&d, index)?;
        if index == 0 {
            validate_manifest(&t, &bytes)?;
        }
    }
    Ok(true)
}
pub fn accept(root: &Path, text: &str) -> Result<Ack> {
    if text.len() > 4096 {
        return Err("消息长度超限".into());
    }
    let p: Packet = serde_json::from_str(text).map_err(err)?;
    if p.p != "S5TX1"
        || !session(&p.s)
        || !hex(&p.c, 8)
        || p.n == 0
        || p.n > 403
        || p.i >= p.n
        || p.l == 0
        || p.l > 65536
        || p.d.is_empty()
        || p.d.len() > 1024
        || !p.d.is_ascii()
        || p.o.checked_add(p.d.len()).is_none_or(|end| end > p.l)
        || !(p.m == "v2" || (p.m == "legacy1" && p.n == 1 && p.i == 0))
    {
        return Err("消息字段或边界无效".into());
    }
    let d = dir(root, &p.t)?;
    fs::create_dir_all(root).map_err(err)?;
    if !d.exists() {
        if fs::read_dir(root)
            .map_err(err)?
            .filter_map(|e| e.ok())
            .filter(|e| e.path().is_dir())
            .count()
            >= 32
        {
            return Err("接收区已达32条，请先导出整理".into());
        }
        fs::create_dir(&d).map_err(err)?;
    }
    let t = Transfer {
        token: p.t.clone(),
        session: p.s.clone(),
        format: p.m.clone(),
        parts: p.n,
    };
    immutable_json(&d.join("transfer.json"), &t)?;
    let meta = Part {
        index: p.i,
        length: p.l,
        crc: p.c.clone(),
    };
    let mp = part_path(&d, p.i, "json");
    if !mp.exists() {
        let total: u64 = fs::read_dir(&d)
            .map_err(err)?
            .filter_map(|e| e.ok())
            .filter_map(|e| e.metadata().ok())
            .map(|m| m.len())
            .sum();
        if total + p.l as u64 > 16 * 1024 * 1024 {
            return Err("单条接收超过16MiB限制".into());
        }
    }
    immutable_json(&mp, &meta)?;
    let data = part_path(&d, p.i, "data");
    no_link(&data)?;
    let mut f = OpenOptions::new()
        .create(true)
        .truncate(false)
        .read(true)
        .write(true)
        .open(&data)
        .map_err(err)?;
    let len = f.metadata().map_err(err)?.len() as usize;
    if len > p.l || p.o > len {
        return Err("字节偏移不连续".into());
    }
    let overlap = (len - p.o).min(p.d.len());
    if overlap > 0 {
        let mut existing = vec![0; overlap];
        f.seek(SeekFrom::Start(p.o as u64)).map_err(err)?;
        f.read_exact(&mut existing).map_err(err)?;
        if existing != p.d.as_bytes()[..overlap] {
            return Err("重发内容冲突，原字节保留".into());
        }
    }
    if overlap < p.d.len() {
        f.seek(SeekFrom::End(0)).map_err(err)?;
        f.write_all(&p.d.as_bytes()[overlap..]).map_err(err)?;
    }
    f.sync_data().map_err(err)?;
    let length = f.metadata().map_err(err)?.len() as usize;
    drop(f);
    if length == p.l {
        let bytes = read(&data)?;
        if crc32(&bytes) != p.c || (p.i == 0 && validate_manifest(&t, &bytes).is_err()) {
            let bad = part_path(&d, p.i, "corrupt");
            if !bad.exists() {
                fs::rename(&data, &bad).map_err(err)?;
            }
            return Err("整段CRC/清单未通过，坏段保留，请重新传输".into());
        }
        if p.i + 1 == p.n {
            is_complete(root, &p.t)?;
        }
    }
    Ok(Ack {
        protocol: "S5ACK1".into(),
        token: p.t,
        session: p.s,
        part: p.i,
        offset: length,
        crc: p.c,
        state: if length == p.l {
            "part_complete"
        } else {
            "stored"
        }
        .into(),
    })
}
pub fn completed(root: &Path) -> Vec<String> {
    let mut keys = Vec::new();
    if let Ok(entries) = fs::read_dir(root) {
        for e in entries.flatten() {
            if let Some(key) = e.file_name().to_str() {
                if hex(key, 16) && is_complete(root, key).is_ok() {
                    keys.push(key.into());
                }
            }
        }
    }
    keys.sort();
    keys
}
pub fn export_text<W: Write>(root: &Path, key: &str, output: &mut W) -> Result<()> {
    is_complete(root, key)?;
    let d = dir(root, key)?;
    let t: Transfer = json_existing(&d.join("transfer.json"))?;
    for index in 0..t.parts {
        let data = verify_body(&d, index)?;
        let text = std::str::from_utf8(&data).map_err(err)?;
        let crc = crc32(&data);
        let total = data.len().div_ceil(300);
        for (page, chunk) in text.as_bytes().chunks(300).enumerate() {
            let header = if t.format == "legacy1" {
                format!("IMU9P|1|{}|{}|{}|{}|", t.session, page + 1, total, crc)
            } else {
                format!(
                    "IMUS5|2|{}|{}|{}|{}|{}|",
                    t.session,
                    index,
                    page + 1,
                    total,
                    crc
                )
            };
            output.write_all(header.as_bytes()).map_err(err)?;
            output.write_all(chunk).map_err(err)?;
            output.write_all(b"\n").map_err(err)?;
        }
    }
    Ok(())
}
