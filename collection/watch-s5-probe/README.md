# Watch S5 activity probe 0.1.0

后续兼容进展：源码格式最小启动0.0.2已由用户确认D2→D3/点击1/退出正常。采集版[0.1.1源码格式2秒协议](../../docs/protocols/2026-10-15-s5-acquisition-2s-source.md)已准备；专用`tools/build_acquisition_source.cjs`在临时副本升manifest/导出版本、关闭两格式，输出`dist/source-format`并拒绝覆盖。新RPK SHA `44c801da39a1e1da56e427268afdad3e4004756e5b34f2179cf52ee91decc8af`。21Node+6Python及实际签名/归档通过；用户报告0.1.1安装、首页与2秒自动保存正常，但具体条数和原始导出尚未取得。根因仍未确认，两个旧包继续停用。下段保留离线审查阶段口径，当前状态以本段和新协议为准。

历史失败与审查：0.1.0采集版和最小启动0.0.1均被用户报告整表短暂黑屏卡住。DS021由Codex复核后，四包包内证书/签名/内容摘要通过，无node_modules副本19Node+3Python通过，才按[最小启动协议](../../docs/protocols/2026-10-15-s5-source-startup-check.md)安排用户检查0.0.2。其SHA `ae37e804ede0c81a60de29c13fa3644e581808a75800b1d9baf6f4ade27ad4df`；后续反馈见上段。下文保留原采集版历史说明，不能据此恢复0.1.0试装/采集，任何整表再卡立即停止变体。

普通Vela三轴加速度入口短试，独立包名`org.imuresearch.s5probe`。当前设备配置为用户报告的Xiaomi Watch S5标准版、系统`3.102.036`；原始传感器导出尚未验收。不是六轴或长期记录器。

保留2/10/30秒、2000回调上限、game请求档位、JSON私有保存和CRC二维码分片。采集、设置、导出使用独立视图；466是逻辑设计宽度，不能当作已读取的屏幕分辨率。圆屏真机布局仍需检查。单位/硬件时钟/手机App版本/腕侧未核则保留unknown或not_recorded，Date.now仅为回调到达时钟。

记录的型号/固件来自用户报告，`metadata_source=user_report_not_device_query`；不能当运行时自动识别。程序不预填9Pro的型号/固件/运动健康版本。内部文件前缀imus5，应用私有目录与旧包隔离。导出沿用`IMU9P|1`旧协议标记以复用核验算法，该前缀不表明设备型号；新JSON才包含S5身份。只有完整分片、CRC和字段校验通过才导出，不插值补缺。

## 原采集版构建记录（停用路径，勿运行生成待试包）

```text
node --test tests/*.test.cjs
node tools/build_rpk.cjs
python tools/check_rpk.py
```

本次待试对象是上文协议固定的既有0.0.2 RPK，不需要重建。根quickapp配置和上述构建脚本仍生成旧JSC/Protobuf路径；不要裸跑aiot build或使用build_startup_probe.cjs替代候选。专用build_startup_source.cjs在临时配置和参数均关闭两格式，实际归档已核无jsc/bin。

依赖固定为aiot-toolkit2.0.5、jsc1.0.9。本机优先使用当前模块node_modules，缺少时复用相邻band9pro-probe/node_modules，不安装新依赖。新检出可用`npm ci --ignore-scripts --no-audit --no-fund`准备自己的依赖后构建。

签名优先取S5_SIGN_DIR指定目录，或当前模块sign，最后使用本机既有band9pro-probe/sign。缺签名时明确失败，不自动生成或覆盖身份；首次自行构建需要自备测试证书/私钥，不能保证与本机包同签名。私钥不纳入仓库，不出现在RPK；签名目录会被复制到受控临时构建区，构建结束按已解析绝对路径检查后清理。dist/build-report.json记录实际工具链/输入目录，dist/package-check.json记录签名和内容摘要检查。构建只证明软件产物存在，不证明型号兼容。

## 原0.1.0安装与短试记录（停用，当前使用上文0.1.1协议）

手机AstroBox连接S5后，选择本地`dist/org.imuresearch.s5probe.release.0.1.0.rpk`推送。手表应用名“S5 活动采集”。初次只在前台录2秒静止，确认保存，再导出二维码；拍全页后用本模块“导出CSV.cmd”解码。输出在本模块私有recordings目录，不与旧手环样例混用。每段成功导出后再录下一段，恢复最新只提供最近保存索引。

2秒原件验收后才逐步做10秒动作/熄屏/切出对照。页面隐藏会记录事件，不能因此保证后台仍有回调。正式普通通信、腕部陀螺仪、单位/轴向、长记录和跨端同步均未验收；二维码短试不代表攻击者自动出口。协议不依赖root、固件修改或提权插件。

完整中文指导见仓库`docs/tutorials/2026-10-15-S5安装与入口短试.md`。旧9Pro原型/原件和手机0.2.2/r2保持原样。
