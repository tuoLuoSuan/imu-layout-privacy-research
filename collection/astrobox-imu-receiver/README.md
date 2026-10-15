# IMU 腕部接收 0.1.1

普通 AstroBox V2 插件，接收 `org.imuresearch.s5probe` 手表 App **主动发送的已保存记录**。先复用已连接 S5 的手机 AstroBox；系统保存一份 TXT 后，再用 USB 复制到电脑。不需要安装新的手机采集 APK、改配对、root 或修改固件。

当前状态：用户报告0.1.0可以导入和打开，但准备接收点击后状态完全不变、无权限提示。0.1.1保留API3/普通权限/缓存与协议，改为显式浅色画布、同步点击次数反馈、无需设备的界面检查、明确等待阶段；本机测试/构建不代替手机事件派发或异步任务执行验证，**尚未确认无响应根因已修复，真实蓝牙传输未验收**。同包可作为电脑 AstroBox 直接接收候选，但尚未安装桌面软件或连接 S5。

## 使用顺序

1. 将核验过的 `.abp` 复制到手机，用 AstroBox 的本地插件/本地资源入口安装。本插件装在 AstroBox 宿主里，和推送到手表的 `.rpk` 不同。若 AstroBox 要求重启，只重启该应用。实际菜单/Android宿主兼容性仍以用户操作结果为准。
2. 先点一次“界面检查（无需手表）”，确认显示“界面响应正常”和次数；若也无反应，停止传输测试并保留宿主诊断。通过后保持 AstroBox 已连接 S5，点“准备接收”，按本次实际提示允许设备列表、项目包消息接收和发送确认权限。每个等待阶段会显示状态，忙时重复点不会启动第二次请求。插件不申请固件、原生高权限模块、网络上传或自动安装功能。
3. 在手表 0.3.1 选记录 → 导出 → 蓝牙传输，保持传输页面。旧0.1.x那条可先“恢复旧版最近一条（只读）”。先只试既有2秒记录，不开长采。
4. 手表显示送达、插件显示已接收后，在插件点“保存完整会话到文件…”，保存到手机 Download。系统保存取消/失败可以重试，插件缓存和手表原记录均保留。
5. 将 `imu_s5_*.txt` 复制到电脑，由已有独立检查器复算。新schema2用 `watch-s5-probe/tools/decode_research_export.py`，旧schema1用 `watch-s5-probe/tools/decode_export.py`。接收成功只证明文件保存/传输分项，不是采集质量、硬件率或科研通过。

接收注册一轮只选择一个目标设备（优先名字中有S5，或唯一连接设备）。不跨设备自动切换，避免宿主回调不带地址时误归属。改目标需要重新加载插件。按“准备接收”会发一条无采集指令的 `S5HELLO1` 来提前检查普通发送权限，不启动/停止/删除手表记录。

## 实现与限制

- `src/receiver.rs` 是可本机测试的纯文件/协议核心，`src/host.rs` 是普通 AstroBox 适配；原生 `receiver_sim` 只是离线合成测试，不打开蓝牙/网络。
- 最多1024 ASCII字符一包，一包在途，接收端同步保存后才应用层ACK。重复包逐字节核对，偏移缺口或不同内容拒绝；完整段校验CRC。断开、取消、时钟回退和超时明确失败，可重新传输复用已存部分。
- 最多32条接收、每条16MiB、每段64KiB；满额明确拒绝，不自动清理。坏段留作诊断。原始文件/样本不改值、不插补。
- 持久化在插件私有目录；导出通过宿主系统文件保存入口。Android存储入口可用性尚需真实宿主验收。不要卸载插件来“刷新”，可能丢掉它的私有接收缓存。
- CRC用于发现传输错误，不提供加密或来源认证；确定性传输ID用于恢复，不是密码学身份。普通消息通道、用户授权和手动导出不构成攻击者自动取数能力的证明。
- 新版手表仍是三轴、回调墙钟和未知单位/轴向。手机0.2.2冻结、旧手表包/原记录不改。

## 构建与复现

依赖固定在 Cargo.lock。新环境需 Rust（本轮实用1.99.0）、Python、Node，以及 `wasm32-wasip2` 标准库；第一次先执行 `cargo fetch --locked --manifest-path collection/astrobox-imu-receiver/Cargo.toml`。工具链不随仓库上传。

```text
python collection/astrobox-imu-receiver/tools/build_local.py --test --package
```

当前电脑检测到 `.cache/s5-transfer-research` 任务工具链时，脚本使用本地GNU Rust及Rust自带链接器，避免要求管理员安装MSVC；不修改全局PATH。其他机器使用已有cargo。输出目录拒绝覆盖，可用 `--output-dir` 指定模块dist内的新候选目录。

本机端到端（Windows）示例，二进制由上一条命令构建：

```text
node collection/astrobox-imu-receiver/tools/test_roundtrip.cjs .cache/s5-transfer-research/receiver-target/x86_64-pc-windows-gnu/debug/receiver_sim.exe
```

Linux的二进制位于 `.cache/s5-transfer-research/receiver-target/debug/receiver_sim`。实际JS采集核心生成5分钟15,000行合成输入→实际发送模块→实际Rust接收核心落盘→兼容TXT→独立Python核验，120原始文件字节一致。本轮593消息/本机用时只属于本机管道/文件系统，不是实测蓝牙吞吐或S5频率。

[协议](../../docs/data/watch-transfer-v1.md) · [首次真机步骤](../../docs/protocols/2026-10-15-s5-transfer-first-run.md) · [公开依赖来源](NOTICE.md)
