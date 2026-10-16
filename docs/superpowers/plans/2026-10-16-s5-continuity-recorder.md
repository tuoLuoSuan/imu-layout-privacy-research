# S5 Continuity Recorder Implementation Plan

> 按用户授权由主智能体在本会话逐项实施，不启用子代理；旧variant作为隔离基准。

**Goal:** 修复duration边界的静默漏标，增加可复算的JS连续性证据。

**Architecture:** 新continuity-recorder继承precise-recorder的暂存构建，新增独立观察模块。保留旧生产代码与分析器，新分析器在既有正式记录检查后验证新证据。

**Tech Stack:** Vela源格式JS、Node内置测试、Python标准库核验、现有签名工具链。

## Global Constraints

- 不改七原件、旧包、手机66/r2、旧collection文件；不加权限/配对/固件操作。
- 不自动连接设备、采集或发送DS；源码仅精确白名单私有备份。
- 1000ms心跳、1500ms延后提示、3000ms静默工程门；不推硬件或外部冻结因果。

### Task 1: 审查与红测

- [x] 将DS原文私有归档，标准库逐文件核字节/CRC/行数/p95；读取实际0.4.1暂存核心与getRecentData参考实现。
- [x] 新建tests/continuity-recorder.test.cjs，在新构建器缺失时使用旧构建器，重现late tick→duration无警告、缺sensor_path和心跳。
- [x] 运行`node --test collection/watch-s5-probe/tests/continuity-recorder.test.cjs`并保留红测。

### Task 2: 独立录制修复

文件：variants/continuity-recorder/src/common/continuity-observer.js、tools/build_continuity_recorder_source.cjs。

接口：观察模块`create(started,emit)`返回`accepted(t,count)`、`tick(t,count)`、`snapshot(stopped,count)`；`policy()`返回固定策略副本。

- [x] 实现仅观测实际tick/接纳的有界摘要和心跳；每次tick至多一条，不补时钟。
- [x] 构建期注入head.sensor_path/策略、接纳通知、tick观察、stop末尾判定、tail摘要和中断中文提示；0.4.2/code11，源格式/圆图标/同签名/三功能不变。
- [x] 通过新红测，加正常/零样本/延后/原生同步失败用例；跑旧Node套件确认未改旧行为。

### Task 3: 导出核验与合成

文件：tools/analyze_continuity_export.py、tests/test_continuity_source_archive.py。

- [x] 先写摘要/头尾入口篡改与缺心跳的失败测试。
- [x] 新分析器调用analyze_precise_export.analyze，再检查新字段与实际行/事件、边缘静默及告警；任何新摘要不一致返回错误。
- [x] 用60秒合成录制经现有运输帧→新分析器复算，保留raw字节一致；不标真机通过。

### Task 4: 构建与交付

- [x] 运行83旧Node加新用例、Python归档/导出套件；构建全新dist目录，核RSA/摘要/证书/普通三功能/无JSC/圆标与277保护输入。
- [x] 新包按SHA前缀放Download；写审查答复、字典、新版10秒→原件分级协议和当前状态。
- [ ] 逐文件白名单扫描、完整index扫描后提交私有分支，取回核字节并等CI真实结果；失败日志保留。
- [ ] 最后才请用户保留数据覆盖更新、只确认首页。未收到启动反馈不安排录制。

最终软件92 Node、33 Python与60秒合成往返已通过；另以每次读取前进1ms的时钟红测证明首候选心跳时间不一致，修为事件/摘要共用一次读数。首候选c84156e2未分发并保留，最终包19d457b8；备份/CI为提交前待办快照，实际结果以本轮私有execution-closeout为准，设备仍未安装。
