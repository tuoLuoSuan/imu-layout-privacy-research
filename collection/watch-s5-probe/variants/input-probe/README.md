# 0.4.0 普通输入检查

这是继承0.3.4的新构建配置，不覆盖旧profiles。正常录制仍用subscribeAccelerometer；只有用户主动进入“输入检查”并点按钮，才一次尝试公开参考中的generic subscribe/high。S5兼容性等待真实运行，声明存在不等于可采。

```powershell
node --test collection/watch-s5-probe/tests/*.test.cjs
python -m unittest discover -s collection/watch-s5-probe/tests -p test_input_probe_source_archive.py -v
node collection/watch-s5-probe/tools/build_input_probe_source.cjs
python collection/watch-s5-probe/tools/analyze_input_export.py INPUT.txt --output NEW_PRIVATE_DIRECTORY
```

默认构建输出dist/input-probe-0.4.0，已有目录拒覆盖。源JS/JSC关闭/Protobuf关闭，同包同签名和圆图标，仍仅system.sensor/file/interconnect。手机接收器0.2.3无需改变。

诊断会话仍是schema2文件与运输，head.metadata.record_purpose=input_probe，api为@system.sensor.subscribe，requested_interval=high；tail.input_probe含schema1诊断。正常记录的purpose为recording、api为subscribeAccelerometer；绝不把game与high默默当成相同请求。

限2秒/128回调；原始回调单次2KiB、累计24KiB ASCII线编码，整个诊断报告49,152字符上限。预算不足、字段不识别、异常、无回调、隐藏/销毁均明确停止，不递归找XYZ、不自动回退。只接受直接XYZ或公开参考的ACCELEROMETER.XYZ映射，同时保留原始JSON与映射序号。源JS不舍入XYZ。未知返回句柄不猜取消参数，提示退出本候选；原生阻塞不能被JS定时器保证中断。

`callback_epoch_ms`是Date.now到达时间；可选`performance_now_ms`是当前运行环境真实返回值，不宣称已证明单调性、硬件时间或跨设备对应。raw_json中的任何时间字段保存原名原值，未核语义。原生批次边界未由JS回调暴露，无法仅靠相邻同毫秒确定批次或补回样本时间。

新分析器先用原核验器验证CRC/清单/序号/封口，再逐项比对raw_json与派生行的XYZ、到达时间、序号；reported_warnings复制原tail，derived_time_warnings单独计算，warnings保留合并口径。正间隔p95用sorted[ceil(.95*N)-1]。旧原件/旧报告不变。

科研验收仍需后续原件、静态多姿态/缓慢转动标定、同步评估、严格前台/息屏持续性分项。手机中转/手动SAF是研究评估出口，不证明攻击者可无交互自动取数。当前不声称六轴、单位标定、硬件Hz或空间层腕部增益。
