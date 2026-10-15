# 外部接口与依赖来源

本模块实现项目自己的传输协议和接收逻辑，调用普通 AstroBox 插件API。

- `astrobox-ng-wit = 0.3.1`：AstralSightStudios / Searchstars 提供的WIT Rust绑定；源与许可信息以Cargo包为准，WIT仓库为 https://github.com/AstralSightStudios/AstroBox-Plugin-WIT （MIT）。
- 官方Rust模板 https://github.com/AstralSightStudios/AstroBox-NG-Plugin-Template-Rust （MIT）用于确认WASI目标、组件生命周期和ABP ZIP结构；未把模板整包复制进研究源码。
- 插件宿主公开实现 https://github.com/AstralSightStudios/AstroBox-NG-Module-PluginSystem （AGPL-3.0及其附加署名条款）仅用于只读核对接口行为；本模块不包含或链接该宿主源码，不重新分发它的实现。
- serde、serde_json及绑定工具的版本/来源/校验值均见Cargo.lock；最终公开制品发布前需随二进制整理对应第三方许可证。当前为项目内部验收候选，未向插件市场或公网发布。

API事实核对包括：按指定设备和包名注册接收、原始消息载荷不含设备地址包装、文件系统限制在插件私有目录、系统保存文件分块接口、权限按操作名分别声明。接口核对与本机编译不证明任何用户设备上的实际可用性。
