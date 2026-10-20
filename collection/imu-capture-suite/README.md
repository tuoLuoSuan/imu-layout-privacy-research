# IMU 联合采集

当前安装组合：**手机 0.2.4＋AstroBox 插件 0.2.4＋S5 手表 0.2.5**。先覆盖插件，再覆盖手表；手机保持原 0.2.4。新手表的 `mkdir` 失败阶段需要新插件，不能与旧插件 0.2.3 混装。步骤见[安装与使用](安装与使用.md)。

| 位置 | 日常入口 | 版本 | 用途 |
|---|---|---|---|
| 手机 | IMU 联合采集 | 0.2.4 / code7 | 六轴、同次记录、一次导出整包；原圆角方形图标 |
| AstroBox | IMU 联合时间桥 | 0.2.4 / API4 / WASI3 | 连接手机与 S5，保存日志，转发腕部失败 |
| S5 | IMU 联合采集 | 0.2.5 / code7 | 三轴；20秒、1/2/5/10分钟；浅色界面、圆形图标 |

该组合是已构建候选，尚未完成候选真机安装、停止重连和故障验证。此前两条20秒连续实录使用手机0.2.4＋插件0.2.3＋手表0.2.4，期间未清手机后台；它们不覆盖新候选、长时间稳定性或所有故障。

候选构建检查记录：Android JVM 68通过/1项Windows权限跳过、Node 44通过、Python 15通过、Rust 20通过；另有新WASM模拟宿主8场景。离线检查不证明蓝牙连接最终回收、物理杀进程后继续上传或存储满后的行为。手表记录持续保留，目前没有清理界面，不自动删除。

安装包、签名和构建收据仅在本地 `dist/`，不随源码推送。入口与身份沿用：手机 `org.imulayout.jointprobe`，手表 `org.imuresearch.s5joint`，插件 `IMU 联合时间桥`。更新前先导出需要保留的记录及插件日志，不卸载、不清数据。

整包包含 `phone.zip`、`watch.jsonl` 和 `bundle-manifest.json`。插件不可用时允许手机部分导出，并披露原因；部分包不称联合完整。读取器也兼容分开的两个旧输入：

```text
python collection/imu-capture-suite/tools/analyze.py IMU_SESSION.zip --output NEW_RESULT.json
python collection/imu-capture-suite/tools/analyze.py PHONE.zip WATCH.jsonl --output NEW_RESULT.json
```

[构建与测试](BUILDING.md) · [变更记录](CHANGELOG.md) · [消息协议](PROTOCOL.md) · [发布边界](PUBLICATION.md) · [旧入口处理](旧入口处理清单.md)。`preview/` 是桌面界面模型，非真机截图。

软件保存成功与研究验收分开。物理时钟、动作/区域参考、真实 oracle、活动模型、腕部空间增益和布局均未因这次修复获得验收；手机单端仅作联合研究的基线/消融。旧冻结采集器与原始记录保留。
