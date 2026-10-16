# 小数入口正式录制观察字段 v1

沿用schema2六列和普通传输。head.metadata.record_purpose=recording；acquisition_api和requested_interval记录实际调用组合。通用入口仅high/mid/low，原入口仅game/ui/normal；名称互斥，不能都称请求50Hz。只有S5 3.102.036上一条generic/high原件实测约16.850974次/秒，非硬件采样率或所有档位的性能。

tail.acquisition_observation的schema_version=1，不改变运输版本：

| 字段 | 含义 |
|---|---|
| sensor_path / api / requested_interval | generic或legacy、实际方法、原样请求档位。 |
| accelerometer_type | generic实际读取的ACCELEROMETER常量，不猜固定数字。 |
| subscribe_return | 原生返回类型与有限数值；generic有效句柄用于取消。 |
| callback_count | 驱动看到且未在停止后忽略的JS回调数，不是硬件样本数。 |
| valid_xyz_callbacks | 形状与有限XYZ校验通过的回调数，允许大于实际写入行。 |
| accepted_rows | 实际被记录核心接纳的行数，封口后应等于CSV行数。 |
| fractional_xyz_scalars | 已接纳XYZ中非整数标量个数，不等于有效数字、分辨率或测量精度。 |
| first_callback_json / last_callback_json | 首末已接纳回调的有界原始JSON；不是每条回调JSON的全集。 |
| first/last_accepted_callback_epoch_ms | 对应首末接纳行的同一次Date.now到达读数；非硬件时间。 |
| rejected_callback_json | 新形状的有界原文；不会忽略额外时间字段后继续录制。不可JSON化数据明确失败，不转为null保存。 |
| error | 首次失败message/code，有截断标志，不被后续失败覆盖。 |
| cleanup | not_subscribed / pending_native_return / handle_unavailable / unsubscribe_returned / unsubscribe_exception；返回只证明普通取消调用已返回，不证明底层无残留。 |

快照每份≤2048 ASCII编码字符，完整观察≤32768；单块128行、512未确认行、单会话40000行和原时长上限保持。订阅/回调期间计数屏障禁止过早写tail，不阻断块写入；同步失败的返回句柄清理可进入封口观察。

sensor_cleanup_unconfirmed是手表产生的质量告警；analyze_precise_export新增derived_acquisition_warnings（例如acquisition_cleanup_not_confirmed），reported_warnings继续复制原tail，combined warnings包括计算告警。分析器校验api/档位、接纳数/小数数、首末原始JSON与CSV值/到达时间，并单列清理状态。

所有时间间隔来自JS墙钟；无硬件时间、原生批次完整性、物理息屏、单位/轴标定或跨设备同步证据。schema2 CRC只验运输错误，不提供来源认证。
