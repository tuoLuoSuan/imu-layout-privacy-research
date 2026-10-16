# S5文件等待退出实施计划

依据同日export-file-wait-design；主智能体执行，用户暂停设备操作继续有效。

1. 保留DS028原文/原脚本与当前源码/原件哈希基线。准确计时模型对比原Promise.all与建议race，固定原屏障的必要性和50ms轮询/3秒上界的区别。已完成，证据ds028-codex-audit。
2. 先新增`tests/export-file-wait-page.test.cjs`：实际staged页面红测无线/QR的inventory、readPart永不返回；精确8秒、逐文件重置、长QR查看、取消/迟到/同步错误及现有13项页面兼容。为新0.4.6分析器白名单增加Python红测。日志保留，不改旧profile。
3. 新增`variants/export-file-wait/file-wait-overlay.cjs`、`tools/build_export_file_wait_source.cjs`，继承0.4.5/code15，仅新页面增加有界读取包装、清理和内存诊断。更新分析器支持0.4.6，未知版本仍拒绝。运行定向/完整相关Node与Python测试，不更改原传输/采集/屏幕guard核心。
4. 同签名源格式构建到新dist目录，核内容/签名/圆标/四能力/重新staged输入及真实999条离线原字节往返；保护基线复核。更新当前状态、源码白名单备份/取回与CI（若执行则只按真实终态报告），准备DS029完整稿。候选仅PC，不连手机/表/VM、不安装/录制/传输，不自动发送DS。

自查：无新增硬件请求/研究门；读等待失败和屏幕释放成功分开表述；测试里的超时钟必须同时进入页面/发送模块，不混用真实Date.now；历史失败与原始证据不覆盖。
