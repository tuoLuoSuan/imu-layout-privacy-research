# IMU联合采集：以后只用这一套

| 位置 | 唯一日常入口 | 版本 | 用途 |
|---|---|---|---|
| 手机 | IMU 联合采集 | 0.2.2 | 手机六轴、同次记录、一次导出整包；恢复原圆角方形图标 |
| AstroBox插件 | IMU 联合时间桥 | 0.2.2 | 连接手机与S5、保存腕部日志 |
| S5手表 | IMU 联合采集 | 0.2.2 | 三轴采集，20秒/1/2/5/10分钟 |

手机和表均为浅色界面、青绿按钮。手机沿用原圆角方形图标，手表使用圆形图标。软件入口固定，后续改进沿用同一个安装身份覆盖更新。

当前统一套件为0.2.2，最终目录 `dist/imu-suite-0.2.2-ready/`。手机、手表、插件均同身份覆盖；长档需要三端一起更新。旧包只作历史留档。首页小图仍需本机目视确认，十分钟联合实机持续性未验。

安装/使用：[安装与使用.md](安装与使用.md)。旧入口：[旧入口处理清单.md](旧入口处理清单.md)。桌面预览明确标注非真机截图，不操作设备。当前研究快照见[联合套件说明](../../docs/reproducibility/joint-suite-2026-10-19.md)。

沿用身份：手机 `org.imulayout.jointprobe`，表 `org.imuresearch.s5joint`，插件manifest.name仍是 `IMU 联合时间桥`。不覆盖冻结022/0415/025源码、原件或旧包。旧App有不同私有目录，不能自动合并旧记录或自动卸载。

导出整包为 `phone.zip`（原封口手机包）＋`watch.jsonl`（原插件日志快照）＋`bundle-manifest.json`。插件不可用时只导出手机部分并显式披露原因；不把部分包称为联合完整。新读取器可读整包，也兼容两个旧输入文件：

```text
python collection/imu-capture-suite/tools/analyze.py IMU_SESSION.zip --output NEW_RESULT.json
python collection/imu-capture-suite/tools/analyze.py PHONE.zip WATCH.jsonl --output NEW_RESULT.json
```

应用完成保存与科研验收分开，物理时钟、活动参考、oracle、腕部增益/布局均不因界面整合而放行。原数据格式、传感器驱动、精度、CRC与失败留证规则复用。
