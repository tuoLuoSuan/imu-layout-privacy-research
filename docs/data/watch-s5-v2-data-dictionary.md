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


## 2026-10-17：0.4.8三十分钟前台工程选项

0.4.8独立profile增加1800秒。此前≤300秒档仍按2000ms定时触发；仅1800秒档使用8000ms，128行触发不变。head.metadata.storage_policy为schema_version=1、row_trigger=128、timed_flush_ms=8000或2000、write_timeout_ms=8000、max_buffered_rows=512、semantics=JS_scheduling_dependent_no_durability_guarantee。字段记录触发策略，不证明完成写入或断电持久化；调度挂起或等待写回调可使未提交窗口更长。

运输、样本/缓冲、块/文件/帧上限不变：B个完整块对应B+2文件、B+3part；清单len<=401和最大part索引401共同要求sealed链B<=399/总part<=402，不能只看inventory允许400块。三万合成行得到235块/238part，不是新真机样本，也不证明30分钟或息屏通过。实际需按独立协议获取新原件；不按29000–30100预期条数筛选，不补点或回填旧metadata。

## 2026-10-17：0.4.9分级时长

0.4.9保留0.4.8策略字段，增加600、900、1200秒档。600/900/1200/1800秒统一128行触发与8000ms定时触发；原≤300秒档仍2000ms。metadata.requested_duration_ms与metadata.storage_policy必须对应实际选择，旧0.4.8时长白名单不随新版放宽。8000ms仅是JS调度依赖的触发周期，不是写入完成或最大断电损失保证。运输/接收/样本/缓冲/文件等边界不变。

当前执行按5→10→15→20→30分钟逐级核原件。0.4.6五分钟旧基准与0.4.9长档分别归属；用户报告0.4.9启动/旧记录/选项/退出正常不代表10分钟通过。每轮另核来源、完整性、连续性及物理条件，不用期望行数区间筛掉异常，不把合成行计入真机语料。

## 2026-10-17：0.4.10运行计时诊断候选

原0.4.9十分钟1510ms空窗/告警保留，连续性未过。独立0.4.10沿用0.4.9采集与时长/存储策略，head.metadata.runtime_timing_policy声明schema1、bounded_runtime_observation、Date.now_wall_clock_not_monotonic、top_limit5、extra_timers0、physical_or_hardware_verified=false。tail.runtime_timing_observation是新增受CRC保护的封口字段，在tail构造时一次取快照，不回写已封口旧记录。

九项指标为callback_body_ms、callback_between_ms、tick_body_ms、tick_entry_gap_ms、tick_between_ms、notify_body_ms、block_encode_ms、write_call_ms、write_ack_ms。每项count/total_ms/max_ms/invalid/pending、固定9桶与最大5条起止/context；直方图上界0/1/5/20/100/500/1000/2000/无上界，不是新增科研接纳门，没有精确p99。未完成跨度保留pending，最终tick/同步重入可尚未结束；毫秒墙钟不单调，非法/负耗时观察计invalid。

callback检查点在beforeCallback持有之后与afterCallback释放之前，between仍含释放和其它工作；write两项仅数据块，ACK包含异步等待/投递，不能单独证明阻塞；tick入口间隔含正常周期，不是纯迟到。所有值为同JS循环路径的墙钟经过时间，可能受GC/调度/时钟跳变及观测扰动影响，不是CPU或硬件时间，不足以单独定因果。候选本机检查不代表S5兼容、原空窗修复或长档通过。


## 0.4.13工程启动保护（不作科研接纳门）

新增head.metadata.startup_rate_policy与tail.startup_rate_observation。仅generic/high且目标>=10000ms：首次录制tick达到5000ms时，以原始接纳first/last/count计算墙钟到达率；跨度至少2500ms且>=10次秒继续，偏低startup_rate_low、跨度不足startup_rate_unconfirmed停止并保存全部失败行。10次秒为工程止损阈值，不是硬件Hz、研究筛样或完整十分钟验收。旧阈值与旧原件不回填。

observation包含schema_version、status、evaluated_epoch_ms、elapsed_ms、count、callback_span_ms、arrival_per_second。status为passed/stopped_slow/insufficient/not_applicable/not_checked_before_stop；后两者所有计算字段为null，不冒充通过。JS挂起不能承诺物理5秒准时执行。分析器按检查时点的前count条重算，保留等毫秒边界的顺序不确定，不改变原始行。停止失败必须保留对应stop_reason/警告，拒篡改策略/未知0414。

0.4.13的列表旧快照仅作展示；配额为含回收区的40会话，不是可用存储字节。浏览8秒、core及页面导出读逐次30秒为工程等待；写入8秒、ACK和保亮屏障不改。不自动重订阅、降档、补样、删点或删除记录。
