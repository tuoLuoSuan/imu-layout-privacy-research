# 发布边界与可复现构建

本页约束源码发布。现有远端仓库仍是私有，未授权更改可见性。`dist/`、原始记录、审计证据、签名材料和任何 `data/` 内容不随源码推送。

## 当前状态（2026-10-23）

- 当前日常候选是手机0.2.4、插件0.2.4、手表0.2.19/code21；只更新手表。用户已报告0.2.18删除成功；0.2.19本地构建完成；用户已确认当前无阻断，未独立回读设备安装版本。
- 0.2.19只保留采集与管理入口，支持勾选/全选和一次最终删除确认。包内已无真实历史会话路径，设备小索引/缓存仍保留；不保证扫描未登记孤儿。
- 本轮用户已确认并授权同步既有私有GitHub；同步使用精确源码清单。具体提交/自动检查以实际Git记录为准，不改变仓库可见性，也不是公开开源授权。
- 日常源码为 `maintenance/daily-0.2.19/`。本次在隔离发布工作区把精确新文件合并到既有repository-policy，核完整暂存区；不把历史维护目录整体推送。
- `storage-rescue-*` 含私有身份或审计输入，全部留在本地；dist、日志、真实视频/ZIP、签名、研究交接不进入软件同步候选。

### 历史状态（2026-10-20；不作当前安装建议）

- 已安装反馈及两条短实录对应旧组合：手机0.2.4/code7、手表0.2.4/code6、插件0.2.3；这是本机交付，不是GitHub发布。
- DS109后候选已构建：手机仍用原0.2.4；手表0.2.5/code7、插件0.2.4/API4/WASI3，包在 `dist/recovery-watch025-bridge024-ready/`。新包的源码输入和SHA见其中build-report.json，旧包不覆盖。
- 当前候选新检查为Android JVM68通过/1跳过、Node44、Python15、Rust20；APK未重建，RPK及WASM/ABP已构建，并以新WASM跑过8项模拟宿主场景。未安装候选、未新采、未真机故障验证，不能宣称零缺陷或设备销毁后保证后台回传。
- 本次生产改动来自手表上传中销毁/generation保护、mkdir独立失败阶段和插件计数交叉检查；手机生产源码保持。新手表的mkdir阶段要求新插件配套，不得单换新手表继续搭旧0.2.3插件。

## GitHub 推送白名单

下列是候选目录范围；正式逐文件准入以推送提交中的 `repository-policy.json.allowed_files` 为准。研究主目录的旧根策略尚未纳入本套件；发布工作区已有历史套件条目，本轮在其基础上合并。不把历史文档中的“114件”视为本轮推送证明。内层build/target/node_modules/签名/本机配置同样排除；正式同步前需合并本轮精确清单：

```text
collection/imu-capture-suite/{README.md,BUILDING.md,CHANGELOG.md,PROTOCOL.md,PUBLICATION.md}
collection/imu-capture-suite/{native,plugin,watch,tests,tools,assets,preview,runtime-tests}/
```

不要加入：

```text
collection/imu-capture-suite/dist/
collection/imu-capture-suite/docs/                 # 本地审计/交接材料
data/  output/  docs/reviews/evidence/  docs/local-notes/
*.jks *.keystore *.p12 *.pem *.key  secrets/
```

根仓库还有与本套件无关的修改和未跟踪文件（`.github/`、`PROJECT_STATE.md`、`README.md`、`showcase/` 等）。不要用 `git add -A`，不要为获得干净status清除这些工作。从既有远端提交的独立工作树更新，保留原有白名单条目，逐文件检查候选和完整暂存区。推送是否成功及远端CI状态以实际提交和Actions回执为准，本文件不是推送证明。

## 构建前置

- Node.js 20+，运行 `node --test tests/*.cjs`。
- Python 3.11+，运行 `python -m unittest discover -s tests -p "test_*.py"`。
- Android：JDK 21、Android SDK 37、Gradle 9.6.1；在 `native/` 执行 Gradle 单元测试和 APK 构建。
- Rust/WASI：`cargo test --locked --manifest-path plugin/Cargo.toml`，再按 BUILDING.md 构建 WASM component/ABP。
- Vela/S5：`node tools/build_watch.cjs dist/NEW_DIRECTORY` 要求全新输出目录；使用仓库中既有aiot-toolkit及本地签名材料。当前输入记录是 `dist/watch-recovery-0.2.5/watch-build.json`，不存在通用 `dist/watch-build.json`。

本机缓存工具链本轮已实际使用：JDK21、Android SDK37/Gradle9.6.1、Cargo/WASI及Vela构建器可用。Cargo直接从未配置的shell启动会因RUSTUP_HOME/CARGO_HOME未设置而失败；这不等于本机没有工具链。当前构建的绝对路径和环境见本地证据目录2026-10-20-ds109-disposition/run.py，不能把此前某个会话未检出PATH写成当前缺失，也不要求用户换电脑。公开源码所需的可移植构建/打包入口仍需整理；本机构建成功不等于外部clone已复现。

## 发布前检查

1. 检查精确候选和完整暂存区只包含本次获准文件；工作树可保留无关修改。
2. 各组件版本/code与各自manifest/Gradle/Cargo一致；不同组件不必同号。当前源码与新候选输入核对，不把新修复说成旧包已有。
3. `node --test` 与 Python 测试全过；Rust/Android 测试在具备工具链的机器上重跑。
4. 新包用原安装身份和本地签名构建；不提交私钥。
5. 不把旧 0.2.2/0.2.3 包、原始实验包、视频、照片、点云或私有审计证据放进公开仓库。

## 许可

**尚未选择开源许可证，不默认套用MIT。** 现有仓库是私有；保留私有并备份自有源码不要求先作开源授权决定。若用户明确要求公开开源，再由项目所有者选择许可证并检查第三方许可与权利，不能依据本文件自动公开仓库。研究数据、证据和第三方材料不随代码公开。
