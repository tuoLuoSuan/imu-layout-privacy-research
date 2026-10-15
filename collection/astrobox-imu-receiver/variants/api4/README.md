# IMU腕部接收0.2.0：API4独立候选

解决0.1.2真实运行失败的独立适配。最低AstroBox2.2.0（官方API表），`wasi_version=3`／`api_level=4`；固定SDK0.4.0，按官方宿主示例用wasm32-wasip2构建Rust标准库。事件为原生async函数，直接await并返回，不再自行拼装返回future或spawn。

复用父模块未改动的接收核心／同步UI状态机；插件名称、缓存`received`、普通三权限、协议和手表包名保持。根目录0.1.2及三个旧包保留。未安装到手机、未验证真实蓝牙／权限／系统保存，不因本机运行通过就称修复。夜间只本机，次日先无设备界面运行自检，成功后再接旧两秒记录。

依据与边界见`docs/superpowers/specs/2026-10-16-s5-receiver-api4-design.md`和本机当日诊断报告。此目录不新增手机采集APK或手表采集功能。

本机软件门已过：共享5协议＋4UI状态测试、38.0.4旧断言复现、48.0.2实际组件三场景（每场景64轮渲染／自检、两次准备和恢复自检）；成功、注册拒绝、查询等待时重复点击均到达验收断言。宿主替身不打开蓝牙，普通授权／真文件保存／S5原件仍未验。

```text
python collection/astrobox-imu-receiver/variants/api4/tools/build_local.py --test --package --reproduce-api3
```

打包必须经过实际WASM运行门；输出目录拒绝覆盖，另一次候选需`--output-dir`指定本variant的dist新目录。更详细的测试边界见[runtime-tests](runtime-tests/README.md)。最终本机候选125862字节，SHA256 `0753b47ba66473e2e143d3c16e9323415a1c23ac8c7ce6320712c16088f8a792`，随包保留SDK0.4.0对应MIT许可；初版离线候选因误用了旧SDK版权文本未分发、已被最终候选取代。
