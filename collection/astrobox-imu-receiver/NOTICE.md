# 外部接口与依赖来源

本模块实现项目自己的传输协议和接收逻辑，调用普通 AstroBox 插件API。

`variants/api4`的0.2.0独立候选改用`astrobox-ng-wit = 0.4.0`（MIT，Copyright 2026 AstralSight Studios）；其实际Cargo包LICENSE逐字节保存于variant的`SDK_LICENSE.txt`并随ABP附带。该文本与旧0.3.1接口的2025版权文本不同，不互相替用。实际组件运行回归使用标准Wasmtime38.0.4／48.0.2 crate和项目自写合成宿主，不包含／链接AstroBox的AGPL宿主实现；依赖及摘要在各Cargo.lock。当前候选未公开发布，未来二进制公开前仍需整理全部传递依赖许可证。

- `astrobox-ng-wit = 0.3.1`：AstralSightStudios / Searchstars 提供的WIT Rust绑定；源与许可信息以Cargo包为准，WIT仓库为 https://github.com/AstralSightStudios/AstroBox-Plugin-WIT （MIT）。
- 0.1.2的`wit/`保留上述Cargo0.3.1包对应的MIT接口描述及LICENSE；两个deps文件逐字节保留。main.wit删除非功能编辑器注释，将所用world局部命名为receiver-async-v3以避免同名组件元数据连接冲突；接口/方法/类型/包名不变。`src/bindings.rs`仅显式异步生成四个插件事件回调，所有宿主导入类型复用SDK，wit-bindgen固定0.57.1、与SDK同版。ABP附带该MIT许可文本。未复制宿主实现或改权限规则。
- 官方Rust模板 https://github.com/AstralSightStudios/AstroBox-NG-Plugin-Template-Rust （MIT）用于确认WASI目标、组件生命周期和ABP ZIP结构；未把模板整包复制进研究源码。
- 插件宿主公开实现 https://github.com/AstralSightStudios/AstroBox-NG-Module-PluginSystem （AGPL-3.0及其附加署名条款）仅用于只读核对接口行为；本模块不包含或链接该宿主源码，不重新分发它的实现。
- serde、serde_json及绑定工具的版本/来源/校验值均见Cargo.lock；最终公开制品发布前需随二进制整理对应第三方许可证。当前为项目内部验收候选，未向插件市场或公网发布。

API事实核对包括：按指定设备和包名注册接收、原始消息载荷不含设备地址包装、文件系统限制在插件私有目录、系统保存文件分块接口、权限按操作名分别声明。接口核对与本机编译不证明任何用户设备上的实际可用性。
