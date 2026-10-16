# S5输入检查附加字段 v1

0.4.0新增，运输/文件仍遵循[原schema2](watch-s5-v2-data-dictionary.md)。正常采集入口不替换。声明与真实返回分开记录，所有单位/轴/硬件时间/同步结论必须另验。

| 位置 | 含义 |
|---|---|
| head.metadata.record_purpose | input_probe为一次候选输入检查；recording为原专用入口记录。 |
| head.metadata.acquisition_api | @system.sensor.subscribe 或 @system.sensor.subscribeAccelerometer，实际调用标识。 |
| head.metadata.requested_interval | 检查为high；原录制保留game/ui/normal，不能互换名词或称实测Hz。 |
| tail.input_probe.schema_version | 附加诊断schema版本1；不是IMUS5运输版本。 |
| declaration | 方法typeof、仅ACCELEROMETER常量值及读取异常；eligible只表示声明形态满足候选要求。 |
| result | completed/no_callbacks/unavailable/native_fail/native_exception/invalid_handle/unknown_shape/raw_not_json/raw_budget_exceeded/report_budget_exceeded/callback_limit/page_hide/page_destroy等实际停止原因。completed仅表示本次短调用窗口正常结束。 |
| subscribe_return | 原生调用返回值类型和有限数值；有效句柄作为unsubscribe参数。未知句柄不猜。 |
| cleanup | 未订阅、unsubscribe已返回、清理抛异常或无法取得句柄，不能把返回当底层无残留证明。 |
| error | 错误message与code；过长字段有截断标记。完整小错误原话保留。 |
| callbacks[].raw_json | 回调对象的JSON快照，无自行XYZ舍入或时间插值；非有限/循环/不可JSON化对象明确停止，不静默转null。预算限制不宣称穷尽原生载荷。 |
| callback_index | 本候选看到的JS回调顺序，不是硬件样本序号。 |
| callback_epoch_ms | 本回调入JS时的Date.now；映射行使用同一值，不二次读取填入。 |
| performance_now_ms | 当前环境performance.now实际返回；缺失为null，未证硬件语义/单调性/手机对应，不能补值。 |
| row_sequence | 被识别的直接XYZ或ACCELEROMETER.XYZ映射到schema2行的序号，未映射为null；原始对象仍保存。 |
| batching_semantics | 原生batch边界未暴露，多个同毫秒不能自证同一原生batch，也不能反推漏掉多少原生样本。 |

单次raw_json最多2048、累计24576个ASCII线编码字符；最多128回调；完整input_probe报告最多49152。停止/超限原因单列。两秒是候选窗口上限，包含存储准备产生的可见时间，若准备已耗尽窗口则不订阅。JS计时不能保证中断原生阻塞。

新analyze_input_export报告中，reported_warnings复制原tail.quality.warnings；derived_time_warnings从行重算；原warnings继续为解码器合并结果。session_status也是计算分类，不是手表原始上报。正间隔p95：升序正间隔[ceil(0.95*N)-1]；median仅正间隔；callback_hz=(N-1)*1000/首末墙钟跨度，非硬件Hz。

hidden的两个合法口径：连续hidden行的首末跨度，与hide事件到后续show/stop的事件跨度。行中不存在的时间不补写；物理屏幕电源未知时保持未知。既有十秒原件的两者为1943ms与2233ms，不互相覆盖或用于证明息屏。

接收预算：外层8192、候选内包4096、核心单包d最多1024字节，单文件读取64KiB。现手机0.2.3对多个未识别/超限原因可统一显示ignored；未知停滞不能一概当作丢样。四字符串外层校验pkgName；直接p/data路径依赖宿主按注册包名路由。CRC检测运输错误，不提供身份认证。
