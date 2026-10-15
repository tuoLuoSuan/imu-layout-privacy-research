# S5 科研记录器实施计划

主智能体在当前聊天执行。设计：同日 s5-research-recorder-design.md。用户已委托具体决定，无须再次审批常规范围。

1. 先写 `collection/watch-s5-probe/tests/research-recorder.test.cjs`：实际核心注入异步文件替身，验证 15,000 行跨 5 分钟、512 行内存边界、缺尾恢复、慢写/失败、回收/撤销和越界拒绝；运行确认缺实现失败。
2. 在新 `variants/research-recorder/src/common/research.js` 实现存储、采集状态机和按文件 QR 协议。保留原 src 和 research-ui。用延迟 I/O 与时钟突变用例验证错误路径，再接入页面。
3. 新 UX 沿用已批准图标与浅色，增加档位/时长/匿名标签、会话选择、回收区、明显失败态、分段二维码。页面测试检查忙时锁定、失败重试、退出事件。
4. `tools/decode_research_export.py` 输出 CSV/JSON 并严格核验；独立 Python 用例拒绝冲突页、缺块/缺尾、序号和行数篡改；合成端到端从实际 JS 生成 QR 再由 Python 解码。
5. `tools/build_research_source.cjs` 将独立 profile 暂存为 0.3.0/code4，同签名源码格式构建。核 RPK 配置、内容、签名、图标；所有旧包/原 src/手机66哈希不变。
6. 从新 UX 生成浏览器布局预览，实际查看采集/设置/记录/回收确认/QR 与错误状态；只称布局预览。整理使用手册、证据报告、PROJECT_STATE 与 AGENTS。
7. 精确扩展源码白名单、扫描、只暂存本版源码文档，运行相应检查并提交到已有私有源码备份；不上传 RPK/截图/真实记录/密钥。结束于取回旧原件和真机短试这一必要人工步骤。
