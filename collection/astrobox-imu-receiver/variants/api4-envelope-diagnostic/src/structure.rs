//! A bounded type-only view. This never supplies data to the receiver parser.
use serde_json::Value;

fn label(key: &str) -> &str {
    match key {
        "p" | "data" | "payload" | "message" | "content" | "value" | "body"
        | "event" | "type" | "text" | "buffer" | "bytes" | "msg" | "raw"
        | "source" | "device" | "device_addr" | "deviceAddr" | "pkg_name"
        | "pkgName" | "packageName" | "package_name" | "package" | "dataType"
        | "data_type" | "_data" | "_type" | "d" => key,
        _ => "other",
    }
}

fn view(value: &Value, depth: usize) -> String {
    match value {
        Value::Object(fields) if depth < 2 => {
            let mut entries = Vec::new();
            for (key, value) in fields.iter().take(12) {
                let kind = if key == "p" && value.as_str() == Some("S5TX1") {
                    "S5TX1".into()
                } else {
                    view(value, depth + 1)
                };
                entries.push(format!("{}={kind}", label(key)));
            }
            if fields.len() > 12 { entries.push("more-fields".into()); }
            format!("object{{{}}}", entries.join(","))
        }
        Value::Object(_) => "object".into(),
        Value::Array(values) => format!("array(len={})", values.len()),
        Value::String(text) if depth < 2 && text.len() <= 4096 => {
            match serde_json::from_str::<Value>(text) {
                Ok(inner @ (Value::Object(_) | Value::Array(_))) => {
                    format!("text-json({})", view(&inner, depth))
                }
                _ => "text".into(),
            }
        }
        Value::String(_) => "text".into(),
        Value::Number(_) => "number".into(),
        Value::Bool(_) => "boolean".into(),
        Value::Null => "null".into(),
    }
}

pub fn describe(payload: &str) -> String {
    if payload.len() > 8192 { return "oversize".into(); }
    let summary = match serde_json::from_str::<Value>(payload) {
        Ok(value) => view(&value, 0),
        Err(_) => "invalid-json".into(),
    };
    // Only fixed ASCII field names, types, counts and the S5TX1 literal occur here.
    summary.chars().take(640).collect()
}
