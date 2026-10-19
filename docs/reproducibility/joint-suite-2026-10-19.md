# 手机＋S5联合采集：2026-10-19源码与状态快照

研究目标仍是普通应用可读的手机六轴＋S5三轴，随活动覆盖范围、观察积累与交互量增长，能够泄露多少未知空间信息。雷达仅提供独立评价参考，不是攻击输入。

## 固定入口

| 位置 | 显示名 | 当前版本 | 身份 |
|---|---|---|---|
| 手机 | IMU联合采集 | 0.2.2/code5 | org.imulayout.jointprobe |
| AstroBox插件 | IMU联合时间桥 | 0.2.2/API4/WASI3 | 原manifest.name保持 |
| S5 | IMU联合采集 | 0.2.2/code4 | org.imuresearch.s5joint |

手机保留原圆角方形图标；表浅色、圆形应用图标。表首页曾在实机裁切，0.2.1仅改CSS仍失败；0.2.2改用独立32像素RGB小图，用户已报更新并导出，尚未单独确认图标完整显示。不能用桌面预览替代实机目视。

三端同身份覆盖，不新增应用。旧冻结022／0415／025源码、旧包与原件不覆盖。AstroBox更新会替换插件可写目录，需先保存历史日志；不同应用私有目录不自动迁移、卸载或清理。

## 真实短试

一条同次整包：手机两路3137／3138条，received=enqueued=written=confirmed，dropped=[0,0]；outside_gate_callbacks=1单列。表315条，20.015秒duration结束，最大到达间隔154ms，15处超过100ms全保留，无超过1秒；27次手机交换、10次表交换。外层SHA、内层原清单、CRC、同会话身份、序号与封口核对通过。手机摘要匹配交付源码，表/插件安装二进制未回读。

这只证明本次采集/接收/一次导出链路。原检查器completion/event/delivery/storage为pass，但baseline_stability仍unknown_or_fail、overall仍pending_external_review，不改为整机或物理同步通过。不追加录制凑基线。

## 时长和软件检查

菜单20秒检查、1／2／5／10分钟；默认1分钟。延长任务同时扩展了样本上限、表/手机交换数量、结束支持和手机等待回传的安全时限，保留单消息大小、CRC、先落盘后ACK和失败留存。手机安全时限含回传余量，不是手表30分钟采集档。

116项软件检查：Android65、腕部JS24、Rust16、整包读取11；另有实际WASM模拟宿主7场景。十分钟模拟9999条应接纳样本全留、末时刻回调单列；慢ACK回传不触发旧限额。新版十分钟实机持续性、电量与资源上限尚未验证；不能用旧独立记录器的十分钟实录替代。

## 复用和研究边界

RoNIN预训练手机速度分支已在本地执行；权重和上游模型源另行按许可取得，不随本仓库上传。因果前缀先截原始事件与回调，再预处理/推理；输入未来数据不应改变预算内结果。C4仅为有限旋转一致性控制，不是精度提升或EqNIO复现。

S5六条活动实录支持三轴活动线索角色；幅度范围有重叠，没有泛化分类器或空间增益。联合脚手架含常数、打乱、腕部错配和对称手机错配，参考只进入评价侧；没有真实参考覆盖时不生成完整oracle，不训练XGBoost。

雷达已有15秒静态候选、161帧，存在缺口和坐标/对象对应未知；收起后不能复用外参。下一步恢复连接、核驱动与静态几何，再用于独立区域/布局评价。无独立轨迹精度、真实联合布局或泄露阈值结论。

## 可运行源码检查

```text
node --test collection/imu-capture-suite/tests/*.test.cjs
python -m unittest discover -s collection/imu-capture-suite/tests -p "test_*.py" -v
cargo test --locked --manifest-path collection/imu-capture-suite/plugin/Cargo.toml
python -m unittest discover -s analysis/phone_pdr/tests -v
python -m unittest discover -s analysis/phone_ronin/tests -v
python -m unittest discover -s analysis/joint_privacy/tests -v
```

分析测试使用合成输入/外部预测器，不自动下载权重或启动训练。Android使用JDK21、Android SDK37/build-tools37.0.0、Gradle9.6.1，在native目录运行testDebugUnitTest与assembleDebug；本仓库不提供个人签名密钥。依赖安装与硬件采集不由上述源码测试自动触发。

网站沿用本机六页工作台；三维和历史曲线并未替换为本次恢复效果。源码入库只含经检查的文件，原始ZIP/日志/视频/点云、签名、私有诊断和本机完整状态日志不上传。旧PROJECT_STATE冻结正文只作为历史，当前以本快照和README为准。
