# S5 目录URI兼容修正计划

按用户自主排错授权，由主智能体执行，不开子代理。

- [x] 新增tests/directory-uri.test.cjs：真实观察的双斜杠格式注入旧核心，复现已封口99条仍列表0条；修正入口未实现时断言失败。含混合URI、越界路径、容量和回收／恢复／删除边界。
- [x] 新增variants/directory-uri-fix/src/common/directory-entries.js，normalize(fileList)返回去重后的安全本目录文件URI。不是磁盘操作，不改原文件。
- [x] 新增tools/build_directory_uri_fix_source.cjs：继承0.3.3独立暂存，修改版本0.3.4/code8，仅在directory()边界调用normalize；保留原始诊断／UI／传输逻辑与旧文件。
- [x] 运行新增与全部Node回归、构建新dist/directory-uri-fix-0.3.4，核实际包签名、旧源／旧包、原始20项照片证据与合成测试区分。
- [ ] 更新协议／状态与私有追记，白名单私有源码备份。用户只查看原记录，取得原件后继续链路与功能门。
