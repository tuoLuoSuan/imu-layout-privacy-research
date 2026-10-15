# 腕部 S5 v2 数据字典

适用科研记录器 0.3.0，不追溯改写 schema_version=1 文件；与手机 v1 字典独立。

| 数据 | 定义和限制 |
|---|---|
| head.json | 不可变初始元数据，写成功后才订阅；含 schema_version=2、session_id、started_epoch_ms、row_fields、metadata |
| b0000.json… | 连续编号块，每块≤128行、≤32事件，kind=block；写成功回调只证明 API 返回成功，不证明介质同步 |
| tail.json | 停止后排空成功才写；含 count、persisted、blocks、stop_reason、stopped_epoch_ms、quality |
| sequence | 本会话接受的样本从0连续编号；不是硬件序号，拒绝的非法样本不占序号 |
| callback_epoch_ms | JS Date.now 读取时刻，墙钟毫秒；不是硬件事件时间、单调时间或已同步 UTC |
| x / y / z | API 原始数值，未舍入、校准或插值；单位与物理轴向尚未验收 |
| page_state | visible／hidden，为页面生命周期观察；不能代替锁屏、电源或系统冻结证明 |
| metadata.requested_interval | game／ui／normal 请求档位；官方近似回调说明不是实测。没有“设置任意 Hz”含义 |
| metadata.requested_duration_ms | 请求时长；实际接收、停止延迟和数据覆盖应分别检查 |
| metadata.participant / room | 预先选择的匿名编号或 null，不填姓名地址。旧会话不得补填假标签 |
| metadata.wrist | left／right／not_recorded，人工选择，无自动佩戴识别 |
| activity_instruction | 指令而非动作真值，不替代事件起止标注 |
| events[].callback_epoch_ms | JS 记录该事件的墙钟；冻结/进程死亡时无法继续写，是观测上限 |
| page_show / hide / destroy | 页面生命周期事件；destroy 后写盘仅尽力收尾，不能保证 OS 给足执行时间 |
| stop_requested | 首次停止请求原因；后续存储失败可让尾文件最终原因不同，原事件保留 |
| storage_error / save_retry | 文件接口失败及用户重试；失败批次在当前进程内保留，退出后仅已存部分可恢复 |
| write_timeout | 文件回调超过8秒；底层操作不可取消，晚到成功不把本会话改判封口，不并发重试 |
| queue_overflow | 未确认保存达到512行后下一样本被拒，立即停止；不自动丢掉旧缓存腾空间 |
| sensor_silence | 定时检查超过3秒没有回调时停止；本机规则，不是硬件故障定位 |
| clock_regression | 时钟倒退，停止并保留此前文件；回退后的停止时刻可能早于最后接受样本 |
| no_samples / invalid_samples | 零有效样本／收到非有限或缺字段读数，必须显示告警，不以零补值 |
| duration / manual | 到请求时长／手动触发正常停止，走排空+封口；不代表该段数据通过研究验收 |
| sample_limit | 达40,000条软件保护上限，不是测得硬件容量 |
| callback_hz | (N−1)×1000/(末回调时间−首回调时间)；少于2条、跨度不正或序列时钟倒退时为 null |
| gaps_over_100ms / gaps_over_1s | 相邻有效回调墙钟间隔超过100／1000毫秒的次数；不等于传感器丢样数 |
| interrupted | 无尾文件；冻结、退出、强杀、写盘异常等原因未区分，不自动补封口 |
| sealed / sealed_with_warnings | 原始文件传输完整且有尾文件／另有质量告警；不是硬件或科研“通过” |
| transfer_status=complete | 清单列出的各文件二维码齐页且各段 CRC 通过；无尾会话仍可“传输完整、采集中断” |

二维码协议：`IMUS5|2|session_id|part|page|total|crc32|payload`。part从0起，page从1起；part0为包含实际文件名顺序的manifest，后续各part一一对应文件。每页payload≤300 ASCII字符、单文件≤64KiB；CRC32按该段拼接ASCII字节计算。段清单完整性和文件内身份/序号/行数还要独立检查。旧IMU9P协议不变。

回收采用 `_trash.json` 标记，不移改样本；恢复删该标记。永久删除先落 `_purge.json` 固定文件清单，逐项删除并最后删会话头，可在 I/O 失败后重试。目录/文件名严格由受限 ID 和固定后缀构成；不接受用户输入路径。标记写入未声称原子或抗断电。

本机完整性报告不证明 S5 长期/后台能力、物理量标定、两端同步、HAR 或空间泄露。没有外部系统日志时，应用无法自证冻结机制。正式采集要另外绑定协议与用户现场条件。
