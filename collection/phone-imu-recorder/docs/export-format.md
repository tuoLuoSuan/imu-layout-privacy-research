# 原生手机 IMU 导出格式 v1

原始输入：Android TYPE_ACCELEROMETER（含重力m/s²）、TYPE_GYROSCOPE（rad/s）。0.1.0/0.1.1/0.2.0共同请求20,000µs，0.2.1共同请求10,000µs；均maxReportLatencyUs=0，以每份metadata的requested_period_us和app_version为准，实际事件/交付率分别由原始时间计算。固定使用实际返回的非唤醒传感器，元数据保存名称、厂商、量程、分辨率、FIFO等；这些不是物理精度验证。格式v1和r2验收规则没有随请求周期调整而变化。

私有会话以UUID命名。封口后源文件不再改写；重复导出验证ZIP内每文件哈希，外层ZIP字节不是连续性证据。通过系统保存页导出，不申请READ/WRITE_EXTERNAL_STORAGE，不自动分享或上传。

0.2.2保留格式v1与r2，新增可选共同请求25–200整数Hz，默认100。metadata增加`requested_rate_hz`，既有`requested_period_us`仍是实际传入两次registerListener的整数微秒周期，按`round(1000000 / Hz)`换算；120Hz例如为8333µs。配置在启动时冻结，不能将名义值解释为硬件定频。旧会话缺新字段时只读显示原周期，不补写Hz或重算manifest。

用户确认删除时，整个已封口会话从私有`sessions/UUID`移入同级`pending-session-deletions/UUID`再清理；此区不参与会话恢复或导出。不修改已导出ZIP。清理失败可能仍占空间，会明确提示并允许重试；它不是可恢复回收站。

| 文件 | 内容 |
|---|---|
| accelerometer.csv、gyroscope.csv | sequence,sensor_timestamp_ns,received_elapsed_realtime_ns,writer_dequeued_elapsed_realtime_ns,x,y,z,accuracy |
| anchors.csv | planned_elapsed_ns,elapsed_before_ns,wall_ms,elapsed_after_ns |
| events.jsonl | 实际执行的elapsed_ns、type、details；含状态、注册/注销、I/O分阶段耗时、通知与电源观察 |
| metadata.json | 系统/源码摘要、实际传感器、起止、计数、状态、租期/通知观察、mtime、错误及完成原因 |
| integrity_report.json | 事件/交付/存储/基线/UTC分项，全部>100ms间隔、>1秒否决项、锚缺覆盖、待外部审查状态 |
| state.json | 初始化/记录中标记；成功封口后为sealed。sealed不表示数据连续或完整结束 |
| manifest.json | 自身以外全部稳定文件的SHA256与字节数，CSV另有数据行数 |
| recovery.json（可能存在） | 进程中断后的恢复说明；不修改或补齐原始CSV，不声称已知死亡时刻 |

每通道序号从1开始，由应用分配，不是硬件样本序号。三个纳秒时间为十进制整数：传感器原始事件、回调入口接收、写线程出队。前两者依据Android API使用同类含深度睡眠的单调基准；不直接与Unix毫秒相减，也不把回调率称硬件率。accuracy只记录API状态。

采集起点是两通道注册成功后开启接收闸门的时刻；闸门外/启动前样本单列，不作为已接收数据静默丢弃。接受后无法入队记录丢弃并异常停止。正常封口时接收=入队=写入=同步确认=CSV行数。容量4096的队列满时不阻塞回调。每通道64KiB或脏数据5秒先到触发写出/flush/fd sync；I/O事件不递归触发自身日志。

每段partial wake lock申请60秒、20秒续租。这是应用逻辑租期，不是AOSP时长上限或内核全程生效证明。恢复执行时发现过期、续租跨旧截止、异常或观察到未持有，均异常收尾。冻结期间应用不能写心跳或自证冻结原因。

45分钟触发正常停止 `stopped_reason=max_duration`；排空/关闭30秒超时为aborted/drain_timeout。中断线程请求不能证明I/O已关闭，仍不稳定的文件不得导出。文件实际关闭或下次恢复后可导出异常会话；恢复保持CSV原样，包括可能的半行，完整性检查须失败或未知。不能将恢复的最后样本时刻称为实际进程死亡/停止时刻。

基线固定[2,60)秒，头两秒原始行保留；至少1000个正间隔、端点覆盖和前台观察合格。任何>1秒事件/交付间隔、原始事件重复/回退、丢弃/计数或会话条件失败先否决；>100ms且≤1秒首层告警；随后才比较同状态中位数±20%。若实际状态边界不清，不能用预定操作时刻补成精确边界。

锚点三读数必须前后严格递增、宽≤5ms。相邻有效锚间隔≤15秒、墙钟/单调增量差≤100ms才局部映射，输出不可映射区间；坏锚保留，不跨缺失插值，不用一个偏移外推。UTC部分/不可用与原始单调连续性分开；跨设备同步另验。

应用报告的overall保持pending_external_review，data_checks_passed只代表内部数据判据。独立Python检查器重算哈希、序号/计数、间隔、基线/状态稳定性与锚，并核对应用报告数值。退出码1=明确数据失败，2=无数据失败但待外部审查/未知或输入错误；**该工具目前不自动返回整体验收通过的0**。最终有线验收由实际外部快照、用户通知观察与独立检查报告共同记录，不能靠传入一个布尔值伪造外部审查。

```powershell
python 'D:/Project/imu环境重建/collection/phone-imu-recorder/tools/check_export.py' --zip 'D:/Project/imu环境重建/data/raw/phone/native_short_wired_001/session.zip' --output 'D:/Project/imu环境重建/environment/reports/native_short_wired_001'
```

该路径是首轮真机协议的目标，尚无对应数据时不得写成已采集。已有Sensor Logger ZIP格式不同，不能直接传入本检查器。
