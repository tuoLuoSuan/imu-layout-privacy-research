# 0.4.2 连续性观察录制候选

独立继承0.4.1，旧profiles、安装包与原件不改。保持同包/同签名/源格式/圆图标，仅system.sensor/file/interconnect；默认通用high，现有设置、三轴、普通传输和回收区保持。

修正结束边界：已有3秒静默保护，但旧tick先检查duration、stop未核末尾空窗。新版在停止时重算已接纳样本的末尾空窗；duration且>3000ms则记sensor_silence，手动停止保留manual并显式告警。界面沿用现有告警区显示“采集已中断 · 已保存，请导出核验”。

复用250ms定时器，每至少1000ms记录一次实际执行的capture_heartbeat，不补造未执行心跳。头部写sensor_path与策略，尾部保存首末样本、起始/末尾/最大空窗及tick/心跳摘要。共享事件循环的心跳不能自证系统冻结、物理屏态、硬件时间或batch完整。

```powershell
node --test collection/watch-s5-probe/tests/*.test.cjs
python -m unittest discover -s collection/watch-s5-probe/tests -p test_continuity_source_archive.py -v
node collection/watch-s5-probe/tools/build_continuity_recorder_source.cjs
python collection/watch-s5-probe/tools/analyze_continuity_export.py INPUT.txt --output NEW_PRIVATE_DIRECTORY
```

已完成本机红绿回归及60秒1000行/60心跳合成导出、33个运输part原JSON字节相同。随后真实0.4.2的10秒166行、60秒998行原件已分别完成项目与独立标准库核验，见[真机分项结果](../../../../docs/data/watch-s5-continuity-native-trials.md)。一分钟的亮屏/触屏条件及手机源哈希仍待补，不将内部校验相符提升为完整前台验收；息屏、单位/轴向及正式联采仍另验。
