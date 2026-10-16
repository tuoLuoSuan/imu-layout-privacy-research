# S5前台屏幕策略字段

适用0.4.3正式录制；运输仍schema2。0.4.2及更早原件不补字段、不交给本分析器冒充新版。输入检查继续使用自己的分析器。

- head.metadata.screen_policy：schema_version=1、mode=foreground_keep_awake、api=@system.brightness.setKeepScreenOn、physical_screen_verified=false。表示本版采集政策，不是屏幕电源测量。
- tail.screen_observation：同政策字段，acquire/release各含status、requested_epoch_ms、completed_epoch_ms，失败另有受控error.message/error.code。正式采集要求acquire=success，release必须终结为success/failed/exception/timeout，不能以pending封口。
- late_release_attempts：0为正常正式会话。等待开启期间取消或超时后晚到成功会补关闭；此时不会启动正式录制，不把这种尝试包装成正常会话。
- screen_keep_awake事件：会话建立后记录已获接口成功回调；不是外部亮屏证据。
- screen_release_unconfirmed：释放接口fail/exception/timeout，文件保留但不能宣告屏幕策略清理通过。分析器会独立派生此告警，即使原tail遗漏。
- page_hide/page_destroy：本版前台策略在离开页面时停止，原原因及告警保留；不会在回前台时自动重开。

屏幕请求发生在head之前，释放可在采样截止之后完成；stopped_epoch_ms仍指采样截止，不偷换为封口/系统保存时间。墙钟字段无硬件同步含义。自然息屏5.12次秒与前台16.68次秒只是一次记录中不同页面状态的实际到达统计，不作固件限速机制或硬件Hz结论。
