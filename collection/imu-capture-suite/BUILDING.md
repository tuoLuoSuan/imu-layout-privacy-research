# 构建与测试

当前候选：手机0.2.4/code7、手表0.2.5/code7、插件0.2.4/API4/WASI3。三个组件不必同号，不运行历史脚本把版本强制改成一致。当前手机APK沿用已构建0.2.4；手表RPK与插件WASM/ABP已重新构建，尚未进行候选真机验收。

## 通用检查入口

从仓库根目录运行，需要 Node.js20+、Python3.11+、Rust stable：

```text
node --test collection/imu-capture-suite/tests/*.test.cjs
python -m unittest discover -s collection/imu-capture-suite/tests -p "test_*.py" -v
cargo test --locked --manifest-path collection/imu-capture-suite/plugin/Cargo.toml
```

Android 需要 JDK21、Android SDK37/build-tools37.0.0、Gradle9.6.1。设置 `JAVA_HOME`、`ANDROID_HOME` 后运行：

```text
gradle -p collection/imu-capture-suite/native testDebugUnitTest
gradle -p collection/imu-capture-suite/native assembleDebug
```

Debug构建不等于可覆盖用户安装的已签名交付。继续沿用原安装身份必须使用原本地签名；私钥、keystore和本机配置不提交。

插件组件构建需安装 `wasm32-wasip2` 目标：

```text
cargo build --locked --manifest-path collection/imu-capture-suite/plugin/Cargo.toml --target wasm32-wasip2 --features astrobox --release
```

WASM编译完成不等于ABP已正确打包；ABP还需匹配 `plugin/manifest.json`、图标与依赖许可文本。实际发布应记录包字节、SHA、源码提交与输入摘要，不以旧包替代新源码。

## 本机缓存辅助入口与未完成项

`tools/run.py`、`tools/runtime_check.py` 绑定既有实验机缓存与日志目录，是历史本机构建辅助；通用检查使用上面的入口。不要让这些辅助脚本覆盖旧收据。`runtime-tests/` 是模拟AstroBox宿主，不是手机、BLE或原生文件系统。

`tools/build_watch.cjs` 使用既有 `collection/watch-s5-probe/` 或 `collection/band9pro-probe/` 下的 `aiot-toolkit` 与本地签名目录。输出要求是本套件 `dist/` 下不存在的新目录：

```text
node collection/imu-capture-suite/tools/build_watch.cjs collection/imu-capture-suite/dist/NEW_DIRECTORY
```

干净clone不含上述Node依赖和签名材料，不能直接运行手表出包。完整可移植三端打包、固定Vela工具链安装与干净clone复现尚未完成；本次GitHub备份不称完整可复现发布。历史一次性改源码/打包脚本不纳入当前发布清单。

## 已有构建证据的范围

候选构建时Android JVM68通过/1项Windows符号链接权限跳过、Node44、Python15、Rust20；新WASM另跑8个模拟场景。这些是特定构建检查记录，不是任意时间运行都固定相同的测试数，也不证明真机停止重连、物理杀进程、断电、满存储或十分钟稳定性。

安装组合见[README](README.md)，推送范围见[PUBLICATION](PUBLICATION.md)。原始数据、包、签名和私有审计证据不随源码推送。
