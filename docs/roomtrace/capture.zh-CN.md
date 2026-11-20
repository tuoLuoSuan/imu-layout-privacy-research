# 用手机和手表采集 IMU

**简体中文** · [English](capture.md) · [返回首页](../../README.zh-CN.md)

下面三个安装包用于录制新数据。只想在电脑上复算论文主表的话，直接看[复现命令](../../README.zh-CN.md#复算论文主表)。

| 组件 | 版本和要求 | 下载 | 源码 |
|---|---|---|---|
| 手机采集器 | 0.2.4，内部版本号 7，需要 Android 14 或更新版本（API 34+） | [APK](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/download/joint-watch-v0.2.23/IMU-Capture-0.2.4.apk) | [Android](../../collection/imu-capture-suite/native/) |
| 手表采集器 | 0.2.23，内部版本号 25，小米 Watch S5（Vela） | [RPK](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/download/joint-watch-v0.2.23/org.imuresearch.s5joint.release.0.2.23.rpk) | [Watch S5](../../collection/imu-capture-suite/maintenance/daily-0.2.23/) |
| 手机与手表桥接插件 | 0.2.5，需要 AstroBox NG 插件 API 4 和 WASI 3 | [ABP](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/download/joint-watch-v0.2.23/IMU-Bridge-0.2.5-clock-discard.abp) | [桥接插件](../../collection/imu-capture-suite/maintenance/bridge-0.2.5/) |

[采集套件版本页](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/tag/joint-watch-v0.2.23) · [AstroBox NG 上游](https://github.com/AstralSightStudios/AstroBox-NG)

## 安装和录制

1. 在手机端安装 APK。用 AstroBox NG 连接 S5，导入 ABP 插件，再把 RPK 安装到手表。两端采集应用都叫 **IMU 联合采集**，插件叫 **IMU 联合时间桥**。
2. 在桥接插件点 **准备采集**，再在手机点 **开始采集**。手机显示已连接后，在手表上开始录制。手机采加速度和角速度，手表采三轴加速度。
3. 停止录制，等两端保存和传输结束。在手机应用的 **记录** 里选中这次采集，把联合 ZIP 导出到电脑能读的位置。完整 ZIP 含 `phone.zip`、`watch.jsonl` 和 `bundle-manifest.json`。

S5 0.2.20–0.2.22 和当前安装包使用同一签名身份。0.2.19 及更早的版本使用另一签名。迁移旧版或更换桥接插件前，先导出并检查需要保留的记录和插件日志。

## 检查导出，再跑动作分类

在仓库根目录运行下面的命令。输出文件请用新路径。

```bash
python collection/imu-capture-suite/maintenance/bridge-0.2.5/analyze.py CAPTURE.zip --output capture-check.json
```

校验器检查归档完整性、两端会话 ID 和数据行数。报告会单独标出只有手机数据的导出，并保留时钟诊断。设备的物理时钟对齐和房间配准需要另行标定。

如果要生成手机的动作时间线，解开联合 ZIP，再把 `phone.zip` 解到 `SESSION/phone/`，使该目录包含 `accelerometer.csv` 和 `gyroscope.csv`。按[首页](../../README.zh-CN.md#复算论文主表)安装 Python 依赖后运行：

```bash
python -m roomtrace actions --session SESSION --out output/activity-timeline.json
```

布局恢复读取一个 JSON，里面有房间轮廓、家具清单、配准后的走位点和带类别的接触。[合成输入](../../examples/) · [真实宿舍回放](../../examples/registered-dorm/)

## 安装包校验

SHA-256 清单在[版本页](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/tag/joint-watch-v0.2.23)。Windows 可以运行 `Get-FileHash FILENAME -Algorithm SHA256`，Linux 可以运行 `sha256sum FILENAME`，然后比对相同文件的值。
