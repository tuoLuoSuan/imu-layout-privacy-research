# S5 前台自动保亮执行计划

> 仅主智能体按任务执行；用户禁止子代理。采用既有授权的独立profile，不改历史实现。

**目标：** 不需触屏保亮即可做前台采集，开始前确认普通接口成功，结束时记录释放结果。

**架构：** screen-guard.js封装一次保亮/释放与超时；screen-overlay.cjs改实际页面与录制core；build_foreground_recorder_source.cjs在0.4.2暂存树上生成0.4.3；新分析器只增加screen字段核验。

**约束：** code12；同签名/源格式/圆标；普通sensor/file/interconnect/brightness；不改旧profile/源原件，不伪造心跳或硬件时间。

## 任务1：回归测试与保亮边界

- [ ] 新增tests/foreground-recorder.test.cjs：先使用旧profile触发“保亮前不写文件、不订阅”失败，保存红测日志。
- [ ] 新增variants/foreground-recorder/src/common/screen-guard.js，接口create({load,now,setTimeout,clearTimeout})→acquire():Promise、release():Promise、state():副本。请求/释放各3秒超时，释放可重复调用但原生关闭不重复；开启晚到成功须再关闭。
- [ ] 用受控异步亮度回调/文件回调验证成功、fail、异常、超时、取消、双击；保证失败未发生sensor.subscribe。

## 任务2：实际页面和封口

- [ ] 新增screen-overlay.cjs：原startRecording改为beginSessionRecording，外层startRecording先acquire；等待/失败状态中文可见。会话建立后写screen_keep_awake事件和screen_observation。
- [ ] 在updateSession检测首次非recording状态，先holdAcquisition，再release亮度，将结果写入观察后releaseAcquisition；释放失败保留screen_release_unconfirmed。
- [ ] onHide/onDestroy取消等待、停止前台会话并释放；不自动重开。修改首页文本说明录制保持亮屏。
- [ ] 新增build_foreground_recorder_source.cjs调用既有prepareStage，更新0.4.3/code12、增加brightness声明、复制新模块、套用overlay；输出必须全新目录。
- [ ] 新增分析器与归档测试，核head/tail屏幕字段、schema、释放结果和错误分支，旧分析器不改。

## 任务3：构建与分段真机门

- [ ] 跑全部watch Node/Python检查；保存红绿与最终日志。仅运行必要检查，不重建Rust/Android缓存。
- [ ] 构建源格式RPK，核包/内容摘要/同证书/圆标/四能力/版本与源输入，并核277保护输入、所有原件和旧包保持；固定SHA的新名复制Download。
- [ ] 白名单扫描、完整index扫描后仅提交允许源码/文档到现有私有分支；原件/日志/诊断只在本机。取回比较；CI状态据实际结果记录。
- [ ] 用户先只保留数据覆盖更新、确认首页/退出；收到反馈再逐条10秒→60秒不触屏→5分钟，原件核验后再延长。不将本机构建当S5支持。
