# S5 文件列表只读诊断实施计划

由主智能体按用户自主决断授权执行，不开子代理。设计见同日 record-list-diagnostic-design.md。

**目标：** 取得99条已保存而列表0/0时的实际目录接口返回，不猜测改动记录查找。

**架构：** 独立 variants/storage-diagnostic 模块与0.3.3/code7构建覆盖层，继承保留的0.3.2暂存输入。旧核心、旧包、手机66文件／r2及私有证据均不改。

- [x] 新建 tests/storage-diagnostic.test.cjs：注入 file.list/get；验证异常返回可见、read-only操作、超时及晚回调、旧数据字节不变。先运行确认缺少诊断接口而失败。
- [x] 新建 variants/storage-diagnostic/src/common/storage-diagnostic.js：inspect(file, options) 顺序探测两个固定目录接口，输出有界 probes/pages，无写操作。
- [x] 新建 tests/storage-diagnostic-page.test.cjs：实际构建暂存页面在vm中运行；模拟原核心因非标准URI列出0条、诊断显示实际URI；采集中不运行诊断、重复点击不重复调用、退出后晚结果不覆盖。
- [x] 新建 tools/build_storage_diagnostic_source.cjs：只在独立临时副本升级0.3.3/code7并添加诊断模块／入口；旧采集和传输实现保留。记录页增加一个小入口，页高由圆屏布局复核。
- [x] 新测试及现有Node回归，实际RPK构建、同证书和内容签名核验；核受保护源／旧包。源码和构建验证不当真机修复。
- [ ] 更新协议／PROJECT_STATE／AGENTS当前门，新增私有追记，不覆盖初始快照。源码白名单扫描通过后私有备份；用户保留数据覆盖升级，仅点击文件检查，不新录／删除。
