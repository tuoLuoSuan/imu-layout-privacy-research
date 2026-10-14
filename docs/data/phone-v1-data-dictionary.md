# 手机v1数据、质量状态与会话补充记录

更新：2026-10-14。依据冻结App0.2.2/格式v1/r2的实际实现整理；不修改原文件、检查器或判据。描述未覆盖的字段以源码为准，扩展须另定版本。本页是跨模块语义入口，手机模块[导出说明](../../collection/phone-imu-recorder/docs/export-format.md)保留为冻结历史合同。

## 文件与原始列

| 文件 | 语义 |
|---|---|
| accelerometer.csv | Android TYPE_ACCELEROMETER返回的含重力加速度，m/s²；并非线性加速度/单独重力向量 |
| gyroscope.csv | Android TYPE_GYROSCOPE返回的角速度，rad/s |
| anchors.csv | 同设备单调时钟与墙钟的读取区间；不直接提供手机/手表偏移 |
| events.jsonl | 进程实际执行时的状态、广播、I/O、租期等观察；不是完整系统因果轨迹 |
| metadata.json | 会话版本、请求、实际传感器、计数、状态与结束信息 |
| integrity_report.json | App内部r2分项与待外部审查状态 |
| state.json | 会话生命周期/封口状态，不代表采集质量通过 |
| manifest.json | 自身以外稳定文件的SHA-256、字节数及CSV行数；不是信号真实性/精度证明 |
| recovery.json（可选） | 异常恢复说明，不补齐原CSV，不知道精确进程死亡时刻 |

两份原始CSV列完全相同，均为每通道自有序列：

| 列 | 类型/单位 | 来源与可用解释 | 不可解释为 |
|---|---|---|---|
| sequence | int64，1起 | 应用为接收闸门内事件分配的通道序号 | 硬件样本编号，或单凭连续即证明硬件无漏样 |
| sensor_timestamp_ns | int64，ns | SensorEvent.timestamp；同设备含深度睡眠的单调时间基准 | Unix时间；跨设备共有时钟；硬件晶振精度证据 |
| received_elapsed_realtime_ns | int64，ns | 回调入口读取elapsedRealtimeNanos | 传感器采样时刻或写盘完成时刻 |
| writer_dequeued_elapsed_realtime_ns | int64，ns | 写线程取出该记录的单调时刻 | 文件已flush或已fsync的时刻 |
| x,y,z | 有限浮点 | 本传感器返回的设备坐标轴分量；单位依文件；当前物理朝向与独立标定尚未完成 | 世界坐标、已去零偏数值、位置或姿态真值 |
| accuracy | 整数API状态 | 原样保留Android提供的状态值 | 百分比精度、毫米级误差或经过标定的不确定度 |

accuracy状态码0=UNRELIABLE、1=LOW、2=MEDIUM、3=HIGH；它是Android回调/样本保留的状态枚举，不是独立物理误差估计。状态变化回调时刻也不自动是物理精度变化的精确起止。原状态保留，不能为连续性验收事后删样本。

manifest的CSV `rows`均不含表头，包括anchors.csv；例如本次181条锚数据加1表头为182物理行。冻结检查器对所有带rows的清单成员都比较该数据行数。

保留纳秒整数精度，不先转Unix毫秒或低精度浮点再做差。绘图可用本通道首事件为零点，但不能因此抹掉两通道真实相对起点；腕部Date.now回调时间不是同语义字段。

## 计时与频率

| 量 | 定义 |
|---|---|
| requested_rate_hz | 0.2.2采集前保存的整数请求值；25–200，缺字段的旧记录不补写 |
| requested_period_us | `round(1000000/requested_rate_hz)`；实际传入注册的整数微秒周期。120Hz请求对应8333µs |
| 中位事件间隔倒数 | `1e9/median(diff(sensor_timestamp_ns))`，说明所统计片段的典型事件密度；须同时报告缺口 |
| 跨度平均事件率 | `(N-1)*1e9/(last_event_ns-first_event_ns)`；报告使用的片段，不混同中位间隔倒数 |
| 回调到达间隔 | `diff(received_elapsed_realtime_ns)`，单独统计交付；不叫硬件采样率 |
| 队列等待 | `writer_dequeued_elapsed_realtime_ns-received_elapsed_realtime_ns`；不是全部磁盘耗时 |
| 实际采集时长 | metadata中`stop_elapsed_ns-collection_start_elapsed_ns`；包含无事件/延迟区间，不自动等于有效暴露时长 |
| 缺口 | 按事件时间与交付时间分别列出，不假定缺口中用户静止，不插值成观测 |

anchors.csv：`planned_elapsed_ns`是计划触发时刻；`elapsed_before_ns`、`elapsed_after_ns`包住`wall_ms`读取，后者为Unix毫秒墙钟。只使用前后严格递增且宽≤5ms的有效锚；相邻有效锚间隔≤15秒、墙钟与单调增量差≤100ms时才局部映射。坏锚和未覆盖区间保留，禁止跨缺失常量外推。文件名和mtime不代替时间基准。

冻结映射的每个锚用`mid = before + (after-before)//2`作为单调时刻。相邻有效锚构造`[mid_i,mid_next]`，先裁剪到本会话`[start,stop]`，取有效区间并集，再以会话区间的补集计算未覆盖；不把before/after端点任选，也不相加未裁剪长度。288c8700的首锚中点减start为253620ns，before/after减start分别为253334/253906ns；原未覆盖0.000253620秒保持。它不是同步残差或时钟精度。

## 元数据与事件

| 字段/事件 | 实现中的含义与限制 |
|---|---|
| session_id / app_version / source_digest | UUID、App版本、主源码/资源摘要；source_digest不覆盖全仓，完整来源另关联Git提交和冻结66文件清单 |
| sensors / units | 实际选用传感器的名称、厂商、类型、量程、分辨率、FIFO和单位等API信息；不是独立物理标定 |
| received / enqueued / written / confirmed / dropped | 两元素数组，依次对应accelerometer、gyroscope；接受、入队、写出、同步确认和丢弃计数，须与原始行核对 |
| outside_gate_callbacks | 闸门外或起止边缘未接受的回调数；不自动等于已接收样本丢失，也不是硬件无丢样证明 |
| states / state_observed | 程序实际执行时观察到foreground、other_app或screen_off及单调时间；不把用户计划时间补成精确边界 |
| system_broadcast | 收到广播后才记录action和电源观察；不是广播源事件的精确发生时刻 |
| runtime_observation | 观察通知权限/自身通知列表与电源状态；通知列表存在不等于用户确实看到了通知 |
| interactive / keyguard_locked / plugged | API读取的交互、锁屏和供电状态；非交互不等于CPU已深睡；不自动含电量百分比 |
| wake_lock_operations / wake_lock_acquire | 60秒租期、20秒续租及结果观察；不能自证被冻结期间仍执行或内核全程有效 |
| csv_io | 每通道64KiB或脏数据5秒先到触发的写出/flush/sync分阶段耗时；日志不递归记录自身I/O |
| source_mtimes | 封口时CSV修改时间；尾部滞后只能作旁证，不能单独归因为冻结/强杀或判通过 |
| visibility_condition_failed | 可选失败标记；没有该字段不等于已有全程可见性外部证明 |

## 质量词表与优先级

| 词/字段 | 权威位置与解释 | 判读 |
|---|---|---|
| collecting / sealed | state.json中的生命周期值；sealed表示源文件已稳定封口 | 与数据质量正交 |
| complete / aborted | metadata.completion_state；正常流程结束/异常结束 | complete也可能基线不足或频率失败 |
| user / notification / max_duration | metadata.stopped_reason正常停止来源；45分钟到限走正常排空 | 不自动表示质量通过 |
| drain_timeout | 排空/关闭超出30秒，异常结束；不证明底层I/O已关闭 | 对应工程失败/恢复处理 |
| queue_overflow / dropped | 队列无法接受已接收样本；丢弃不能静默隐藏 | 失败 |
| wake_lock_coverage_lost | 失锁/租期守卫发现覆盖问题的异常原因 | 失败；不是已定位系统冻结机制 |
| event_continuity / delivery_continuity | App报告的事件/交付时序分项 | 原始事件重复/回退或任一>1秒间隔否决；交付可相等但不能倒退 |
| storage_integrity | 行、计数、队列与同步确认核对 | 不符失败，不等于物理测量精度 |
| interval_over_100ms / over_100ms | App/独立工具对>100ms间隔的不同名称 | >100ms且≤1秒告警，须显式展示；>1秒仍失败 |
| baseline_invalid:<channel> | 独立工具unknown中的原因；同会话[2,60)秒覆盖、1000正间隔及前台条件等不足 | 无法判定稳定性；不能按通过统计 |
| baseline_stability=unknown_or_fail | App汇总状态可能合并未知/失败 | 必须查看baseline和逐状态原值，不一律当unknown或fail |
| state_stability / state_stability_insufficient | 独立工具频率比较失败/该状态证据不足 | 分别为失败/未知；不得互换 |
| completion_or_visibility_failed | 独立工具聚合失败词 | 不直接说明具体哪一条系统路径造成失败 |
| utc_mapping=complete/partial/unavailable | 单设备墙钟局部映射的覆盖状态 | 与原始单调连续性、跨设备同步分别报告 |
| data_checks_passed | App内部布尔汇总 | true不等于最终外部验收通过 |
| pending_external_review | App overall及独立工具无明确失败时保留的状态 | 不得改名为pass |
| fail / invalid_input | 独立工具明确数据失败/无法有效读取输入 | 后者不当成一次已完成的数据失败实验 |

优先级沿用r2：明确失败先否决；所有>100ms告警列出；再比较同会话有效前台基线的逐状态中位数±20%。基线无效保持未知，不借用别次基线、不放宽判据。检查器CLI退出1表示明确失败；退出2可能是待外部审查/未知或输入错误，必须查看JSON，不能作为“通过码”。当前工具不自动给整体验收通过的0。

| 独立工具overall | CLI | 含义 |
|---|---|---|
| fail | 1 | 已解析检查中存在明确failure |
| pending_external_review | 2 | 无明确failure，仍须查看unknown/warnings及外部观察 |
| invalid_input | 2 | 输入/读取/解析异常；不是一条已完成且无数据失败的验收 |

当前检查器已核对清单每项大小/hash及声明的CSV行数，另核实际解析行数与metadata计数；没有显式解析state.json.state是否sealed，也没有强制完整固定文件集合。哈希一致不等于sealed语义已审；必要时另读state作结构旁证，不回写冻结工具或旧结论。r2不以outside_gate_callbacks非零单独否决，仍按原始事件边缘、接受后计数/丢弃和时序核验；新增限制须另定版本，不能事后改判。

冻结时应用无法写“在场证明”；应用缺日志不能区分冻结、进程死亡和自身异常。有线短试需配外部只读快照，拔线观察边界另报，不能将有线快照当拔线全程证明。

## 会话sidecar：本轮准备，不回填旧记录

[模板](../../templates/session-context-v1.template.json)仅包含空值和计划，不是采集数据。新会话复制到本机`data/session_context/<session_id>.json`后再填写；真实sidecar不进源码白名单。它独立于App原始ZIP和manifest，不重封原件，不假装这些字段曾由App采集。

| 字段组 | 用途与来源 |
|---|---|
| raw_binding | 完成会话后填UUID、原始导出SHA-256、App版本/source_digest和源码commit；不凭文件名猜时间 |
| grouping_eval_only | 匿名人/物理房间/布局变体/场地ID，用于split与评估；身份对应表另存，不输入攻击器 |
| protocol_plan | 计划协议与阶段；绝不能当实际操作证据 |
| observations_eval_only | 携带位置、手机朝向说明、腕别、省电条件、充电/屏幕、电量读数及来源；未测留null，不猜填 |
| actual_phases_eval_only | 实际边界、原始时钟/来源引用与不确定性；没有精确边界就留空或说明范围 |
| reference_eval_only | 地图/量测报告/动作标注引用；只给评估、适当训练或独立oracle诊断，不传入主测试推断 |
| consent_review_ref | 机构伦理/豁免与知情同意记录的受控引用；null表示未记录，不代表已获批 |

模型推断接口须逐字段白名单取信号；不能因sidecar与信号同目录就全部加载为特征。携带位置/房间ID/人工事件/真实覆盖等可用作分层统计，不自动成为攻击者先验。活动和事件标签下一阶段另定，当前空模板不授权正式招募或训练。

源码依据：`RecordingContract.java`、`SessionController.java`、`SessionFiles.java`、`IntegrityAnalyzer.java`、`ClockMapping.java`、`RecorderService.java`、`AndroidRecordingRuntime.java`与`tools/check_export.py`，均在`collection/phone-imu-recorder/`。若文档与实现冲突，记录差异并核对，不擅改冻结实现来迎合文字。
