# AstroBox 联合时间桥 0.2.5

本目录是实际0.2.5包对应源码，与历史 plugin/ 的0.2.4并列保留。API4 / WASI3；配套手表0.2.23与手机0.2.4。
对时作废与手表失败路径保留显式journal，不能把JS往返或回显当物理精度。
固定包SHA及同代签名说明见 ../../releases/watch-0.2.23.json。
编译组件曾在真实WASM模拟宿主下执行九类场景；模拟宿主不能证明蓝牙或新设备固件已验收。
源码测试：cargo test --locked --manifest-path Cargo.toml。
