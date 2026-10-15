# S5入口适配实施计划

执行：主智能体在本聊天内完成；用户禁止子代理。既有范围与设备信息已确认，不另开工作树/聊天或重复功能审批。

目标：提供独立、可核验的S5 RPK与安装短试指南；保留旧9Pro模块、手机冻结和原始材料。

架构：collection/watch-s5-probe独立源码、测试和构建入口；从旧模块复制受控源文件后只修改必要元数据/包身份/圆屏布局。现有Vela工具链与签名在本机复用，输入路径和哈希留档。解码按原CRC协议独立输出到S5目录。

- [ ] 保存旧模块源文件及66手机冻结哈希基线；独立模块复制旧核心/页面、测试、配置，不复制node_modules或私钥。
- [ ] 先添加S5身份、未知字段、设置互锁、独立存储前缀和跨语言导出测试，运行观察旧基线失败。
- [ ] 仅在新模块写S5元数据、采集/设置页和圆屏安全区；沿用错误/保存/分片逻辑，运行测试通过。
- [ ] 离线构建RPK，核验CRC/签名/内容摘要、权限仅sensor/file、JSC/protobuf存在、无私钥，记录真实返回码和产物哈希。
- [ ] 生成独立安装/2秒试验指导；复核旧模块/66冻结不变；真机安装/界面/数据保持待验。

关键命令：node --test collection/watch-s5-probe/tests/*.test.cjs；node collection/watch-s5-probe/tools/build_rpk.cjs；python collection/watch-s5-probe/tools/check_rpk.py。每条日志写environment/reports/2026-10-15-s5-probe-build新文件。新文件若进入源码备份，先人工审阅并扩精确白名单后扫描，不全量暂存工作区。
