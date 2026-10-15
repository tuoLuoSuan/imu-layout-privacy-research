# S5采集版源码格式兼容修订 Implementation Plan

> 由主智能体在当前聊天执行，不使用子代理。沿用已要求的S5普通三轴入口/2秒短试范围，不增加采集能力或修改手机App。使用writing-plans整理步骤，按test-driven-development先核构建输入/产物约束。

**Goal:** 把既有S5采集版用已成功显示/点击/退出的源码格式打包为独立保留的0.1.1/code2候选，先核验，再由用户逐步检查页面和2秒记录。

**Architecture:** 原0.1.0源文件与失败RPK不变；专用脚本在新临时区复制来源，只改变manifest版本和导出元数据app_version、将临时quickapp配置与显式编译参数同时置false。保留原图标、minAPI2、designWidth466、system.sensor/system.file声明、原采集/保存/导出逻辑。输出到dist/source-format，拒绝覆盖。

**Tech Stack:** 既有aiot-toolkit2.0.5、Node内置测试与Python标准库检查；复用已有公开证书验证外层签名/内容摘要，不安装依赖、不连设备。

## Global Constraints

- 最小启动0.0.2的D2→D3/点击1/正常退出为用户报告，非自动遥测或崩溃根因证明。
- 不把它继承为采集版运行通过。0.1.1安装/页面/2秒记录各自观察，任何整表卡住立即停，不连续试变体。
- 不改旧src、旧RPK、签名材料、手机66冻结/r2、雷达、原始数据，不训练/提权/改固件。
- 元数据版本必须与新包一致；单位/硬件时间仍未知，game是请求档位，不冒充Hz。

## 1. 冻结输入与构建准备测试

- [x] 保存最小包安装/点击/退出的用户反馈，标明本机文件哈希未从表回读。
- [x] 新增`tests/acquisition-source.test.cjs`：在临时目录执行实际准备逻辑，读取新manifest及实际核心生成的元数据；验证两配置false、原核心/manifest不变，已有src目录拒绝覆盖。
- [x] 先运行确认缺少专用实现导致失败；不调用旧两个构建脚本。

## 2. 最小兼容构建

- [x] 新增`tools/build_acquisition_source.cjs`，导出无工具链动作的prepareStage，main才复制签名/建依赖链接/编译；检查ASCII临时路径与清理边界。
- [x] 测试通过后实际构建一次0.1.1/code2；保留source/transform哈希，输出拒绝覆盖。
- [x] 新增`tools/check_acquisition_source.py`及合成正/负测试：确认identity、原两capability、JS而非jsc/bin、正确元数据版本、CRC、无私钥条目；检查实际RPK。签名/内容摘要另外调用既有外层验证器。

## 3. 收尾和真机分段

- [x] 运行本模块Node测试与两个源码归档Python测试，检查66冻结、原4包哈希、旧源文件哈希。
- [x] 新文件人工复核并纳入源码白名单，179文件完整暂存扫描通过；私有源码备份由同轮收尾执行，提交号见本机审查证据source-sync.json。不推RPK/用户反馈/设备证据。
- [x] 生成本机便取副本；用户分段确认安装成功、首页正常、2秒自动停止显示已保存。具体条数未知，未收原件，不当数据通过。
- [x] 真机新观察另存，不覆盖DS021离线核验和历史失败；CI加入不依赖工具链的21Node+6Python检查。
- [ ] 取得完整二维码原件并核验；仅用户反馈不替代原始序列验收。
