//! Adapt only the directly observed one-layer event shape; no recursive search.
use serde_json::Value;

pub fn unwrap(payload:&str, package:&str)->Option<String>{
    if payload.len()>8192{return None;}
    let value:Value=serde_json::from_str(payload).ok()?;
    let raw=match &value {
        v if v.get("p").is_some()=>Some(payload.to_string()),
        Value::String(s)=>Some(s.clone()),
        Value::Object(fields) if fields.get("data").and_then(Value::as_str).is_some()=>{
            fields["data"].as_str().map(str::to_string)
        }
        Value::Object(fields) if fields.len()==4
            && fields.get("pkgName").and_then(Value::as_str)==Some(package)
            && fields.values().all(|v|v.is_string())=>{
                let mut candidate=None;
                for text in fields.values().filter_map(Value::as_str) {
                    if text.len()>4096{continue;}
                    if let Ok(Value::Object(inner))=serde_json::from_str::<Value>(text) {
                        if inner.get("p").and_then(Value::as_str)==Some("S5TX1") {
                            if candidate.is_some(){return None;}
                            candidate=Some(text.to_string());
                        }
                    }
                }
                candidate
            }
        _=>None,
    };
    raw.filter(|s|s.len()<=4096)
}
