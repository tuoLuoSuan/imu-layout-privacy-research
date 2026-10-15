//! Synchronous UI boundary. No device, filesystem, or executor calls here.
#[derive(Debug, PartialEq, Eq)]
pub enum Action {
    None,
    Prepare,
    Save,
    Refresh,
}

pub struct State {
    pub root_id: Option<String>,
    pub addr: Option<String>,
    pub status: String,
    pub feedback: String,
    pub clicks: u64,
    pub keys: Vec<String>,
    pub selected: usize,
    pub working: bool,
}
impl Default for State {
    fn default() -> Self {
        Self::new()
    }
}
impl State {
    pub fn new() -> Self {
        Self {
            root_id: None,
            addr: None,
            status: "先点界面检查，再准备接收".into(),
            feedback: "尚未点击 · 界面检查无需连接手表".into(),
            clicks: 0,
            keys: Vec::new(),
            selected: 0,
            working: false,
        }
    }
    pub fn click(&mut self, id: &str) -> Action {
        self.clicks = self.clicks.saturating_add(1);
        let label = match id {
            "probe" => "界面检查",
            "prepare" => "准备接收",
            "save" => "保存文件",
            "refresh" => "刷新记录",
            "next" => "切换记录",
            _ => "未知操作",
        };
        self.feedback = format!("已响应 {} 次 · {}", self.clicks, label);
        if id == "probe" {
            self.feedback = format!("界面响应正常 · 已响应 {} 次", self.clicks);
            return Action::None;
        }
        if self.working {
            self.feedback.push_str(" · 上一操作仍在等待，请看上方状态");
            return Action::None;
        }
        match id {
            "prepare" => {
                self.working = true;
                self.status = if self.addr.is_some() {
                    "正在确认普通消息连接…"
                } else {
                    "正在查询AstroBox已连接设备…"
                }
                .into();
                Action::Prepare
            }
            "save" if !self.keys.is_empty() => {
                self.working = true;
                self.status = "正在准备保存文件…".into();
                Action::Save
            }
            "save" => {
                self.status = "尚无完整接收记录，暂不能保存".into();
                Action::None
            }
            "refresh" => Action::Refresh,
            "next" => {
                if !self.keys.is_empty() {
                    self.selected = (self.selected + 1) % self.keys.len();
                }
                Action::None
            }
            _ => Action::None,
        }
    }
}
