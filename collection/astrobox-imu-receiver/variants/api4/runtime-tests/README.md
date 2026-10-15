# 接收器实际WASM运行回归

这里运行真实Wasmtime48.0.2及实际接收器组件，不只搜索导出名字。宿主替身提供合成UI、单个合成S5、普通注册／发送成功或拒绝，和空的合成WASI环境；其余导入均为失败桩，误用会使测试失败。不会打开蓝牙／网络或接触真实记录。

三场景各运行64次页面渲染＋自检、两次准备及恢复自检：成功、注册拒绝、查询等待时重复准备。检查实际渲染文字、异步查询／注册／发送次数及忙碌门恢复。输出是软件运行证据，不是AstroBox Android、真实授权、蓝牙／存储或采集验收。没有实现假传感器或生成“真机原件”。

`api3/`保留同版本38.0.4的最小旧接口复现：同步spawn的任务未执行；显式async返回future后出现资源异常，继续调用触发`state.guest_task.is_none()`断言，与手机日志相同。该复现是最小模型，不能证明手机首次资源异常的完整调用序列。阻塞变体只保留诊断研究源码，不安排设备测试。

从仓库根目录运行：

```text
python collection/astrobox-imu-receiver/variants/api4/tools/build_local.py --test --package --reproduce-api3
```

需要Python、Rust stable、wasm32-wasip2目标及宿主C编译环境。Linux CI使用系统编译器；本机Windows使用已校验的任务本地Zig0.14.1和独立代理，不改全局PATH。`windows/tool-proxy.c`仅转发C编译／归档／导入库工具并适配目标名，不改变Wasmtime源码。工具链不入源码仓库。

这是项目独立编写的最小宿主，不包含／链接AstroBox的AGPL宿主实现。版本与依赖摘要固定在各Cargo.lock；SDK的MIT接口由正常Cargo依赖提供。
