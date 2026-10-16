# S5 Precise Recorder Implementation Plan

> 主智能体按executing-plans顺序执行；用户禁用子代理，并已授权自行决定实现。

**Goal:** 把S5原件验证过的小数加速度普通入口接入实际分块录制。

**Architecture:** 独立0.4.1构建继承0.4.0，驱动区分generic与legacy，schema2/原接收器不改；观察摘要写新增tail字段。

**Tech Stack:** 源JS/UX、Node测试、Python核验、既有aiot-toolkit与同签名。

## Global Constraints

- 旧profiles/包/手机66/r2/四条真实原件保留；无子代理/自动DS/固件/配对/设置修改。
- 只读加速度；generic high/mid/low与legacy game/ui/normal互斥。不同时订阅、自动回退或伪造时间/频率。
- 源JS、JSC/Protobuf关闭、同包同签名圆标、sensor/file/interconnect三功能。

### Task 1：驱动

Create `variants/precise-recorder/src/common/sensor-capture.js`及`tests/precise-capture.test.cjs`。

- [x] 测试先失败，再实现`create(sensor,{now,onValue,onFail,onChange})`，返回start/stop/state；独立测试句柄、形状/小数、失败及单次清理。
- [x] 存首末原始快照/回调入口时间、有效/小数计数及真实错误；不承诺单位或硬件时间。

### Task 2：构建/页面/封口

Create `tools/build_precise_recorder_source.cjs`、`variants/precise-recorder/page-overlay.cjs`、`tests/precise-recorder.test.cjs`。

- [x] 测试先失败，再prepareStage继承0.4.0；版本0.4.1/code10，元数据真实api和档位，原profile不写。
- [x] 测试新增第七项入口、默认通用high/重置档位、busy门、普通采集驱动和订阅封口屏障。
- [x] 合成10秒多块保存/列表/运输；独立核行、尾部观察、旧记录不改。

### Task 3：核验与交付

Create `tools/analyze_precise_export.py`、`tests/test_precise_source_archive.py`，更新状态/字典/协议白名单。

- [x] 先红后绿核对观察计数与原始行、小数、首末快照及api/档位互斥；旧分析器不修改。
- [x] 全套Node/相关Python，真实构建/签名/包内容/三功能/圆标核验，原件和旧源包哈希保持。
- [x] 白名单扫描、既有私有源码备份与取回核字节；真实记录和诊断日志不上git。
- [x] 包放Download；下一次确实需要用户操作时再请求保留数据更新/一次10秒试验。不先安排分钟或新采。

执行说明：原件取回和0.4.0探测事实已核，新正式版设备结果仍待用户。源码备份/CI按最终execution-closeout另记，不预报成功。
