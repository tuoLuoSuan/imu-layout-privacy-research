# S5 JS连续性观察 v1

0.4.2的schema2运输和六列样本不变，新字段只描述App已接纳的行与JS定时回调。单个样本仍是原样XYZ和Date.now到达读数，不能推出硬件Hz、单位、轴向、batch完整性或同步。

head.metadata新增sensor_path（generic/legacy）及continuity_policy：schema_version=1、heartbeat_period_ms=1000、tick_delay_warning_ms=1500、silence_limit_ms=3000、time_basis=JS_callback_wall_clock、external_liveness_reference=false。3000ms沿用已有静默工程门，其它两个值是观察配置，不是传感器验收标准。

tail.continuity_observation：

| 字段 | 定义 |
|---|---|
| accepted_rows | 观察模块收到的已接纳行数；应等于封口/CSV，不是所有原生样本数。 |
| started_epoch_ms / stopped_epoch_ms | 与head/tail相同的JS墙钟边界。 |
| first/last_accepted_epoch_ms | 首末已接纳行时间；空记录为null。 |
| start_gap_ms | 首行减开始；无行则停止减开始。 |
| terminal_gap_ms | 停止减末行；无行则停止减开始。 |
| max_no_accepted_gap_ms | 起始空窗、所有相邻已接纳间隔、末尾空窗的最大值。 |
| silence_observed | 上述最大值>3000ms，不定位驱动、JS或系统原因。 |
| tick_count / last_tick_epoch_ms | 实际录制期tick次数与末次时刻；无tick时末次锚点为开始。 |
| max_tick_gap_ms / late_tick_count | 从开始到首tick以及相邻tick的最大间隔，及>1500ms次数。 |
| terminal_tick_gap_ms | 停止时距末tick的间隔，未把停止本身算成一次tick。 |
| heartbeat_count | 实际写入的心跳事件计数，不补齐延后期间的事件。 |
| semantics / external_liveness_reference | JS_wall_clock_observations_only / false，共享事件循环与墙钟，非外部参考。 |

capture_heartbeat事件时间在callback_epoch_ms，与摘要及detail使用同一次实际tick读数，不在排入事件时重读时钟。detail是有界JSON文本，i为1起连续编号，n为该tick已接纳行数，a为其末行时间（无行为null），g为距该末行/开始的间隔。每次tick至多写一条；事件缓存/块边界沿用原32条/128行上限。落盘可能晚于事件时间，未声称fsync持久化。

sensor_silence_observed和heartbeat_tick_delay为设备告警。到时且末尾空窗>3000ms时stop_reason=sensor_silence；manual保留原停止原因并加告警。异常或无封口不改成完成。

新分析器先复用原正式录制检查，再复算头尾入口、行计数、边缘空窗、事件/摘要对应。摘要或事件篡改拒绝；缺静默/延后告警则增加derived_continuity_warnings并降为sealed_with_warnings。duration_with_terminal_silence表示原tail将长末尾空窗标为到时，heartbeat_reference_incomplete表示末tick到末心跳超出策略。reported_warnings仍复制原tail，不静默补写原件。

一条记录封口完整且告警为空，仅说明这些内部校验相符。整个JS循环停止时心跳也会停止；无独立外部参考就不能据此说“设备没有冻结”或“确认了某条系统冻结路径”。旧0.4.0/0.4.1用其原分析器，不回填新字段。
