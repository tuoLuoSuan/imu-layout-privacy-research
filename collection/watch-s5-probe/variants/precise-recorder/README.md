# 0.4.1 小数加速度正式录制候选

继承0.4.0到独立暂存构建；旧源/包/记录保持。S5 3.102.036上，0.4.0普通generic加速度入口已有一条33行原件，99个XYZ标量均含小数、原始JSON到行一致。这只证明该普通入口能提供小数，尚未证明量化分辨率、测量误差、单位或轴向。

默认通用入口high，可选high/mid/low；设置第7项可主动切回原入口game/ui/normal。切入口重置其请求档位，不同时订阅或失败回退。界面显示实际“回调到达×次/秒”；请求档位不能换算成保证Hz。该S5两秒原件high下约16.85次/秒，不能写50Hz或硬件Hz。

```powershell
node --test collection/watch-s5-probe/tests/*.test.cjs
python -m unittest discover -s collection/watch-s5-probe/tests -p test_precise_source_archive.py -v
node collection/watch-s5-probe/tools/build_precise_recorder_source.cjs
python collection/watch-s5-probe/tools/analyze_precise_export.py INPUT.txt --output NEW_PRIVATE_DIRECTORY
```

只用system.sensor/file/interconnect。JSC/Protobuf关闭、同包/同签名/圆图标。手机接收插件0.2.3与schema2运输保持，不申请新权限或改配对。

通用入口严格接受已见ACCELEROMETER{x,y,z}，出现新字段先保留有界原文并停止，避免漏掉潜在时间字段。XYZ和JS入口墙钟不舍入、不插值；每条均存六列CSV，首末完整JSON及计数/错误/取消状态另存tail.acquisition_observation。原始快照每份2KiB、总观察字段32KiB；过长错误有截断标记。正式录制不逐条重复保存完整JSON，但每条XYZ/到达时间仍保存，原生batch完整性未证。

取消generic订阅使用实际返回句柄；专用路径调用专用取消方法。订阅开始及回调期间用计数屏障等真实句柄/当前回调结果进入观察记录后才封口；原生阻塞不保证被JS计时中断。取消异常在tail质量告警和分析报告中显式保留。

现有2/10/30秒与1/3/5分钟选项仍在；0.4.1的真机分块/恢复/息屏/分钟测试尚待。当前无硬件时间、单位标定、六轴、同步或空间层腕部增益结论。
