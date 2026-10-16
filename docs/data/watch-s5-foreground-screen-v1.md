# S5前台屏幕策略字段

适用0.4.3/0.4.4正式录制；0.4.4只优化记录摘要读取，运输仍schema2。0.4.2及更早原件不补字段、不交给本分析器冒充新版。输入检查继续使用自己的分析器。

- head.metadata.screen_policy：schema_version=1、mode=foreground_keep_awake、api=@system.brightness.setKeepScreenOn、physical_screen_verified=false。表示本版采集政策，不是屏幕电源测量。
- tail.screen_observation：同政策字段，acquire/release各含status、requested_epoch_ms、completed_epoch_ms，失败另有受控error.message/error.code。正式采集要求acquire=success，release必须终结为success/failed/exception/timeout，不能以pending封口。
- late_release_attempts：0为正常正式会话。等待开启期间取消或超时后晚到成功会补关闭；此时不会启动正式录制，不把这种尝试包装成正常会话。
- screen_keep_awake事件：会话建立后记录已获接口成功回调；不是外部亮屏证据。
- screen_release_unconfirmed：释放接口fail/exception/timeout，文件保留但不能宣告屏幕策略清理通过。分析器会独立派生此告警，即使原tail遗漏。
- page_hide/page_destroy：本版前台策略在离开页面时停止，原原因及告警保留；不会在回前台时自动重开。

屏幕请求发生在head之前，释放可在采样截止之后完成；stopped_epoch_ms仍指采样截止，不偷换为封口/系统保存时间。墙钟字段无硬件同步含义。自然息屏5.12次秒与前台16.68次秒只是一次记录中不同页面状态的实际到达统计，不作固件限速机制或硬件Hz结论。

## 2026-10-16的0.4.3十秒原件

| 顺序/请求 | 保存条数 | 回调跨度ms | 到达次/秒 | 正间隔中位/p95/最大ms |
|---|---:|---:|---:|---|
| 首次high | 49 | 9595 | 5.002606 | 200/203/205 |
| mid对照 | 83 | 9852 | 8.323183 | 120/124/151 |
| 切回high | 166 | 9875 | 16.708861 | 60/71/104 |

三条均普通手机USB取回、手机前后与电脑SHA相同，项目分析与独立标准库CRC/清单/序号/封口复算相符。均9心跳、无hidden行/同毫秒/倒退或大于1秒样本间隔，acquire/release成功，取消句柄返回。到达次/秒仍不代表硬件Hz。

首次用户明确报告全程亮屏、停止后息屏；补报无触屏/切页、未开省电、电量67%。mid与high复测只回报已导出，其物理屏幕条件未单独确认，不继承首次口述为后两次实测。页面状态来自原件，与物理屏幕状态分开。

首次high接近5次/秒的原因未定位：文件确实声明high，采集驱动与0.4.2逐字节相同；切mid再切high后恢复约16.71次/秒不足以证明修复、固件限速或某个因果机制。49条原件及全部差异保留，不按计数删异常、不宣告一分钟/息屏持续性或同步通过。

三条TXT的SHA依次为`f6af5b408fc2a31c881062297038fc9ee1deea435d900162ff869a748caedf8e`、`8bf40549979c80bedfb01f2bb07428f1c48a253de8011c737a46a9ca3adeeb1c`、`9e56b3c1884ad2eb405a34961687b3ec4cf9dcfdadb2a743feedfdfa5771e5bb`。原件私有保留，不随源码发布。
