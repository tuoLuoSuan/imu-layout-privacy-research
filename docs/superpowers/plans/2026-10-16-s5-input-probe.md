# S5 Input Probe Implementation Plan

> 由主智能体在本会话执行；用户禁止子代理。使用executing-plans顺序实施，按既有授权自行决定，不再追加设计审批。

**Goal:** 交付可用普通入口查明S5小数精度与时间字段的独立0.4.0候选。

**Architecture:** 继承0.3.4到新暂存目录，用独立input-probe模块管理一次有界试采；在暂存研究核心增加诊断尾字段，原profiles不写。现有传输与手机接收器保持字节协议。

**Tech Stack:** Vela源JS/UX、Node内置测试、Python标准库核验、既有aiot-toolkit2.0.5与本地同签名。

## Global Constraints

- 保留手机66/r2、全部旧collection源、包、三原件及初始证据。
- 普通system.sensor/file/interconnect三功能，不增加权限、配对、固件、root或其它设备操作。
- 不自动DS，不上传真实数据，无子代理。
- 固定两秒/128回调/单次2KiB/总24KiB；只订阅实际ACCELEROMETER/high。
- generic可用性、物理息屏、单位/轴、硬件时间、同步均必须有单独实测证据。

### 1. 审查与回归输入

- [x] 只读运行DS原脚本到新的私有目录；复核p95实际用round而非ceil、hidden两口径和早期快照误读，保存追记而不改原稿。
- [x] 将同批绿色日志逐字节另存配对，记录来源哈希。

### 2. 一次有界探测与原件

Create: `collection/watch-s5-probe/variants/input-probe/src/common/input-probe.js`。
Create: `collection/watch-s5-probe/tests/input-probe.test.cjs`。

- [x] 先测试不存在模块时红，再实现`inspect(sensor)`和`create({sensor,store,now,monotonic,onState,pageState})`。
- [x] 使用注入时钟/定时器测试一次订阅、原小数/字段保留、返回句柄清理、同步fail、静默、超限和onHide终止；失败保存零样本会话。
- [x] 测试`store.start({inputProbe:true})`元数据和`session.setInputProbe(report)`尾字段、`push(value,page,receivedAt)`到达时间一致；不放宽普通入口设置。

### 3. 独立构建与界面

Create: `tools/build_input_probe_source.cjs`，`variants/input-probe/page-overlay.cjs`，`tests/input-probe-page.test.cjs`。

- [x] `prepareStage()`继承0.3.4，只在暂存写0.4.0/code9及所需hook，复制新模块；校验替换标记唯一。
- [x] 先红后绿验证：首页不调用新入口、主动检查只读、单次启动、busy门、隐藏停止、旧failed错误不被覆盖；旧记录导出不重写。
- [x] 真构建禁JSC/Protobuf，同包同签名三功能，输出目录拒覆盖。

### 4. 分析与交付

Create: `tools/analyze_input_export.py`、`tests/test_input_probe_source_archive.py`。

- [x] 先红后绿验证probe原始/派生字段、原始JSON/行映射、raw上限、单调读数只是运行时读数、不宣称硬件Hz；旧原件重跑到新目录。
- [x] Node全套、相关Python、实际RPK签名/内容/manifest/图标校验；记录所有证据。
- [x] 更新PROJECT_STATE/协议和精准白名单；扫描、显式提交及既有私有源码备份，不提交真实记录/日志/密钥。
- [x] 将已核包复制Download，给用户一次安装与查看声明面的指令；真机短试待用户反馈，不预报兼容成功。

执行说明：无设备调用；包已放Download并请求用户只查看声明页。私有源码备份/CI以执行收尾证据为准，不预报结果。
