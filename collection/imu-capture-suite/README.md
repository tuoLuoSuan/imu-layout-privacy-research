# IMU 联合采集：当前组合 2026-10-26

**手机0.2.4＋AstroBox插件0.2.5＋S5手表0.2.23/code25**。

- 当前手表源码：[daily-0.2.23](maintenance/daily-0.2.23/README.md)。
- 当前插件源码：[bridge-0.2.5](maintenance/bridge-0.2.5/README.md)。
- 安装包：[私有Release](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/tag/joint-watch-v0.2.23)。
- 摘要与更新身份：[版本清单](releases/watch-0.2.23.json)。

同代0.2.20～0.2.22可保留数据覆盖。0.2.19及更早旧签名不能直接覆盖；必须先导出并核验需保留记录，不能直接卸载或清数据。
本轮同步既有源码和包，没有重新签名、连接设备或重录。包内成功与科研时钟/参考/布局验收分开。

---

以下是历史0.2.19说明，保留追溯，版本和操作入口以上面的当前组合为准。

# IMU 联合采集

当前本地日常候选：**手机 0.2.4＋AstroBox 插件 0.2.4＋S5 手表 0.2.19/code21**。本次仅替换手表；手机、插件保持。0.2.18 已收到用户“记录都删了”的成功反馈，用户已确认当前无阻断并授权源码同步；设备安装版本未独立回读。步骤见[日常使用](日常使用.md)。

| 位置 | 日常入口 | 版本 | 用途 |
|---|---|---|---|
| 手机 | IMU 联合采集 | 0.2.4 / code7 | 六轴、同次记录、一次导出整包；原圆角方形图标 |
| AstroBox | IMU 联合时间桥 | 0.2.4 / API4 / WASI3 | 连接手机与 S5，保存日志，转发腕部失败 |
| S5 | IMU 联合采集 | 0.2.19 / code21 | 三轴；采集与可勾选批量删除；浅色界面、圆形图标 |

当前手表源码入口为 [`maintenance/daily-0.2.19`](maintenance/daily-0.2.19/README.md)，历史 `watch/src` 是 0.2.5，保留作旧采集链基线；不得用默认旧构建入口冒充新日常包。历史救援版留在本机，不全量上传维护目录。

本次检查：77 项日常维护、44 项原采集检查通过；同身份、同证书摘要构建 RPK，并回放编译代码。采集/删除引擎保持。设备保亮、堆内存与新包真机验收未由电脑测试证明，不写“零缺陷”。

安装包、签名和构建收据仅在本地 `dist/`，不随源码推送。入口与身份沿用：手机 `org.imulayout.jointprobe`，手表 `org.imuresearch.s5joint`，插件 `IMU 联合时间桥`。更新前先导出需要保留的记录及插件日志，不卸载、不清数据。

整包包含 `phone.zip`、`watch.jsonl` 和 `bundle-manifest.json`。插件不可用时允许手机部分导出，并披露原因；部分包不称联合完整。读取器也兼容分开的两个旧输入：

```text
python collection/imu-capture-suite/tools/analyze.py IMU_SESSION.zip --output NEW_RESULT.json
python collection/imu-capture-suite/tools/analyze.py PHONE.zip WATCH.jsonl --output NEW_RESULT.json
```

[构建与测试](BUILDING.md) · [变更记录](CHANGELOG.md) · [消息协议](PROTOCOL.md) · [发布边界](PUBLICATION.md) · [旧入口处理](旧入口处理清单.md)。`preview/` 是桌面界面模型，非真机截图。

软件保存成功与研究验收分开。物理时钟、动作/区域参考、真实 oracle、活动模型、腕部空间增益和布局均未因这次修复获得验收；手机单端仅作联合研究的基线/消融。旧冻结采集器与原始记录保留。
