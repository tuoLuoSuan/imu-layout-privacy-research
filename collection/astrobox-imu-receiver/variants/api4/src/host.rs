//! Ordinary AstroBox API level 4 adapter. No firmware/transport/network or raw file extraction.
use astrobox_ng_wit::exports::astrobox::psys_plugin_v4::{
    event::{self, EventType},
    lifecycle,
};
use crate::receiver;
use crate::ui_state::{Action, State};
use astrobox_ng_wit::{
    astrobox::psys_host_v4::{device, dialog, interconnect, register, ui},
};
use std::{
    io::{Read, Write},
    path::Path,
    sync::{Mutex, OnceLock},
};
const PACKAGE: &str = "org.imuresearch.s5probe";
const ROOT: &str = "received";
static STATE: OnceLock<Mutex<State>> = OnceLock::new();
fn state() -> &'static Mutex<State> {
    STATE.get_or_init(|| Mutex::new(State::new()))
}
fn mutate(f: impl FnOnce(&mut State)) {
    if let Ok(mut s) = state().lock() {
        f(&mut s);
    }
}
fn refresh_keys() {
    let keys = receiver::completed(Path::new(ROOT));
    mutate(|s| {
        s.keys = keys;
        s.selected = s.selected.min(s.keys.len().saturating_sub(1));
    });
}
fn text(value: &str) -> ui::Element {
    ui::Element::new(ui::ElementType::P, Some(value))
        .without_default_styles()
        .size(16)
        .text_color("#52677C")
}
fn button(label: &str, id: &str) -> ui::Element {
    ui::Element::new(ui::ElementType::Button, Some(label))
        .without_default_styles()
        .on(ui::Event::Click, id)
        .bg("#176B6D")
        .text_color("#FFFFFF")
        .size(16)
        .padding(14)
        .radius(14)
}
fn render() {
    let Ok(s) = state().lock() else {
        return;
    };
    let Some(id) = s.root_id.clone() else {
        return;
    };
    let selected = if s.keys.is_empty() {
        "尚无完整接收".into()
    } else {
        format!(
            "接收记录 {} / {} · {}",
            s.selected + 1,
            s.keys.len(),
            &s.keys[s.selected][..8]
        )
    };
    let mut root = ui::Element::new(ui::ElementType::Div, None)
        .without_default_styles()
        .bg("#F3F6FA")
        .text_color("#102A43")
        .flex()
        .flex_direction(ui::FlexDirection::Column)
        .width_full()
        .min_height(560)
        .padding(18)
        .gap(12)
        .child(
            ui::Element::new(ui::ElementType::P, Some("IMU 腕部接收"))
                .without_default_styles()
                .size(26)
                .text_color("#102A43"),
        )
        .child(text("v0.2.0 · 普通消息 · 本地保存"))
        .child(
            ui::Element::new(ui::ElementType::Div, None)
                .without_default_styles()
                .bg("#FFFFFF")
                .border(1, "#DCE6EF")
                .radius(16)
                .padding(16)
                .child(text(&s.status)),
        )
        .child(text(&s.feedback))
        .child(button("界面检查（无需手表）", "probe"))
        .child(button(
            if s.addr.is_some() {
                "接收已准备（单设备）"
            } else {
                "准备接收"
            },
            "prepare",
        ))
        .child(text(&selected));
    if !s.keys.is_empty() {
        root = root
            .child(button("切换已接收记录", "next"))
            .child(button("保存完整会话到文件…", "save"));
    }
    root = root
        .child(text(
            "手表：记录 → 导出 → 蓝牙传输。传完后在此保存TXT，再交电脑核验。",
        ))
        .child(button("刷新已接收记录", "refresh"))
        .child(text(
            "接收完成不等于采集质量通过。文件和原记录保留；首次只传既有短记录。",
        ));
    drop(s);
    ui::render(&id, root);
}
async fn prepare() {
    // The click boundary already reserved this operation and rendered its first stage.
    let existing = state().lock().ok().and_then(|s| s.addr.clone());
    if let Some(addr) = existing {
        let ok = interconnect::send_qaic_message(addr, PACKAGE.into(), "{\"p\":\"S5HELLO1\"}".into())
            .await
            .is_ok();
        mutate(|s| {
            s.working = false;
            s.status = if ok {
                "已准备接收，请在手表选择蓝牙传输".into()
            } else {
                "确认消息暂未送出，请保持S5连接，允许普通消息权限后重试".into()
            }
        });
        render();
        return;
    }
    mutate(|s| s.status = "查询任务已启动，正在等待设备列表／授权…".into());
    render();
    let devices = device::get_connected_device_list().await;
    let mut candidates: Vec<_> = devices
        .iter()
        .filter(|d| d.name.to_ascii_lowercase().contains("s5"))
        .collect();
    if candidates.is_empty() && devices.len() == 1 {
        candidates.push(&devices[0]);
    }
    if candidates.len() != 1 {
        mutate(|s| {
            s.working = false;
            s.status = "请先在AstroBox连接S5，确保本轮只连接一块目标手表，再重试".into();
        });
        render();
        return;
    }
    let addr = candidates[0].addr.clone();
    mutate(|s| s.status = "已找到目标设备，正在注册消息接收…".into());
    render();
    match register::register_interconnect_recv(addr.clone(), PACKAGE.into()).await {
        Ok(()) => mutate(|s| {
            s.addr = Some(addr);
            s.status = "接收已注册，正在确认普通消息发送…".into();
        }),
        Err(reason) => mutate(|s| {
            s.working = false;
            s.status = format!("接收注册未成功：{reason}");
        }),
    }
    let registered = state().lock().ok().and_then(|s| s.addr.clone());
    render();
    if let Some(addr) = registered {
        if interconnect::send_qaic_message(addr, PACKAGE.into(), "{\"p\":\"S5HELLO1\"}".into())
            .await
            .is_err()
        {
            mutate(|s| s.status = "接收已注册；确认消息未送出，请检查连接与普通消息权限".into());
        } else {
            mutate(|s| s.status = "已准备接收，请在手表选择蓝牙传输".into());
        }
    }
    mutate(|s| s.working = false);
    refresh_keys();
    render();
}
async fn receive(payload: String) {
    let addr = state().lock().ok().and_then(|s| s.addr.clone());
    let Some(addr) = addr else {
        return;
    };
    // Public dispatcher forwards the raw QAIC payload, without device/package envelope.
    if payload.len() > 8192 {
        return;
    }
    let raw = match serde_json::from_str::<serde_json::Value>(&payload) {
        Ok(v) if v.get("p").is_some() => payload,
        Ok(serde_json::Value::String(s)) => s,
        Ok(v) => v
            .get("data")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        Err(_) => String::new(),
    };
    if raw.len() > 4096 || !raw.contains("S5TX1") {
        return;
    }
    let v: serde_json::Value = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(_) => return,
    };
    let result = receiver::accept(Path::new(ROOT), &raw);
    let response = match result {
        Ok(ack) => {
            let complete = ack.part + 1 == v["n"].as_u64().unwrap_or(0) as usize
                && ack.state == "part_complete";
            mutate(|s| {
                s.status = if complete {
                    "已接收并保存，请点保存完整会话到文件；质量待电脑核验".into()
                } else {
                    format!("正在接收第 {} / {} 段", ack.part + 1, v["n"])
                }
            });
            if complete {
                refresh_keys();
                mutate(|s| {
                    if let Some(i) = s.keys.iter().position(|k| k == &ack.token) {
                        s.selected = i;
                    }
                });
            }
            serde_json::to_string(&ack).unwrap_or_default()
        }
        Err(e) => {
            mutate(|s| s.status = format!("接收未完成：{e}"));
            serde_json::json!({"p":"S5ERR1","t":v["t"],"s":v["s"],"error":e}).to_string()
        }
    };
    // ACK is sent only after receiver::accept has synchronised the fragment file.
    let _ = interconnect::send_qaic_message(addr, PACKAGE.into(), response).await;
    render();
}
async fn save() {
    let key = {
        let Ok(mut s) = state().lock() else {
            return;
        };
        let Some(key) = s.keys.get(s.selected).cloned() else {
            s.working = false;
            return;
        };
        key
    };
    mutate(|s| s.status = "请选择保存位置；取消后仍可重试".into());
    render();
    let result = async {
        let path = format!("export_{key}.txt");
        {
            let mut f = std::fs::File::create(&path).map_err(|e| e.to_string())?;
            receiver::export_text(Path::new(ROOT), &key, &mut f)?;
            f.flush().map_err(|e| e.to_string())?;
        }
        let filter = dialog::FilterConfig {
            multiple: false,
            extensions: vec!["txt".into()],
            default_directory: String::new(),
            default_file_name: format!("imu_s5_{key}.txt"),
        };
        let session = dialog::save_file_start(filter)
            .await
            .map_err(|_| "保存已取消或无法打开目标文件".to_string())?;
        let result = async {
            let mut f = std::fs::File::open(&path).map_err(|e| e.to_string())?;
            let mut buffer = [0u8; 8192];
            loop {
                let n = f.read(&mut buffer).map_err(|e| e.to_string())?;
                if n == 0 {
                    break;
                }
                dialog::save_file_write_chunk(session.session_id, buffer[..n].to_vec())
                    .await
                    .map_err(|_| "写入保存文件失败".to_string())?;
            }
            dialog::save_file_finish(session.session_id)
                .await
                .map_err(|_| "文件保存未完成".to_string())
        }
        .await;
        if result.is_err() {
            dialog::save_file_abort(session.session_id).await;
        }
        result
    }
    .await;
    mutate(|s| {
        s.working = false;
        s.status = match result {
            Ok(()) => "已保存TXT；复制到电脑后由独立工具核验。手表和接收缓存保留。".into(),
            Err(e) => e,
        };
    });
    render();
}
struct Plugin;
impl lifecycle::Guest for Plugin {
    async fn on_load() {
        refresh_keys();
    }
}
impl event::Guest for Plugin {
    async fn on_event(kind: EventType, payload: String) -> String {
        if matches!(kind, EventType::InterconnectMessage) {
            receive(payload).await;
        }
        String::new()
    }
    async fn on_ui_event(id: String, event: ui::Event, _payload: String) -> String {
        let action = if matches!(event, ui::Event::Click) {
            state().lock().map(|mut s| s.click(&id)).unwrap_or(Action::None)
        } else {
            Action::None
        };
        if action == Action::Refresh {
            refresh_keys();
            mutate(|s| s.status = format!("已刷新 · {} 条完整接收记录", s.keys.len()));
        }
        render();
        match action {
            Action::Check => {
                astrobox_ng_wit::yield_async().await;
                mutate(|s| {
                    s.working = false;
                    s.status = "运行检查通过 · 可以准备接收".into();
                });
                render();
            }
            Action::Prepare => prepare().await,
            Action::Save => save().await,
            _ => {}
        }
        String::new()
    }
    async fn on_ui_render(id: String) {
        mutate(|s| s.root_id = Some(id));
        render();
    }
    async fn on_card_render(_id: String) {}
}
astrobox_ng_wit::export!(Plugin);
