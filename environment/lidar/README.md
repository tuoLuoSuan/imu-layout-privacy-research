# MID-360参考工具（硬件路径待验）

本目录是旧采集脚本之外的新版本，不覆盖任何历史脚本/原包。Windows已测标准库逻辑和合成SQLite，**尚未在Ubuntu/真实雷达运行新ROS接入**。不要把代码准备完成称作设备已就绪。

`bag_check.py BAG_DIR`只读单SQLite、检查封口metadata存在、两个topic定义/数量/消息时间与SHA。每topic用自己的`(N−1)/(last−first)`，不跨topic混分母。它不解码CDR、不检查UDP丢包、传感器标定或几何精度。存在WAL/多SQLite分包时拒绝本工具路径，不能误检为通过；原bag不变。

`capture_reference.py`默认只打印计划，无目录写入、ROS导入或进程启动。必须显式`--execute`才进入硬件路径；要求Ubuntu普通用户、已source ROS及驱动环境、明确可执行文件/配置/新输出目录。默认15秒有效观测窗口，双topic到达前最多等10秒；窗口内观测交付间断>1秒报失败。这是新工程守卫，**不追溯改判旧数据**。

未来VM内的计划预览示例（先不加execute）：

```bash
python3 capture_reference.py --driver-executable /ABSOLUTE/PATH/livox_ros_driver2_node --config /ABSOLUTE/PATH/MID360_config.json --output /ABSOLUTE/NEW/SESSION --seconds 15
```

实际路径由重连后的只读预检确定，示例不是本轮已执行命令。使用系统Python/ROS环境，ML venv不承担ROS依赖。新工具直接启动驱动，记录直接POSIX子进程码；245等正包装码不反推出信号。

写入ROS原消息CDR，bag时间采用主机墙钟`time.time_ns`，原header保持；不宣称设备时钟已同步。保留就绪期消息及最后一次spin可能带入的尾部，`observer`另记有效窗口边界；不插值或裁剪。sensor_data QoS为best effort，不承诺无丢包。停止时先销毁订阅/封口writer，再停止自己拥有的驱动进程组。正常退出码、文件结构、观测窗口、几何质量分别报告。

ROS写盘/信号/性能仍待真机验证；信号升级、创建失败或中断留下失败/部分文件，不自动重试、不删除原包。正式参考采集前先按协议定位旧驱动退出异常。

`render_identification.py`从原NPZ生成私有XY/XZ/YZ网格指认图，验证输入SHA；网格编号不是家具标签，原Z不是已验证离地高度。输出应位于忽略的data/derived目录，不接入公开网站。

本机离线测试：`python -m unittest discover -s environment/lidar/tests -v`。
