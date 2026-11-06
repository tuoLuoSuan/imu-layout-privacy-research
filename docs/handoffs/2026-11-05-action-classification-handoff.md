# 交接：用手持 IMU 录音跑冻结的 9 类动作分类模型

日期 2026-11-05。交接人：现场采集侧。接收方：GPT（负责实现特征提取并出分类时间线）。

## 1. 任务

用**已冻结、不得重训**的随机森林模型，对下面这一条 90 秒手持录音做**逐窗分类**，输出一条带时间戳的动作标签时间线。

原话需求：「你动作分类能分出来吗？」——上一轮我没能直接跑，因为**模型的 70 维特征提取代码不在工作区**（只有训练好的 `model-phone.joblib` 和预先算好的数据集 JSON）。所以这一步的实质工作是：**按下面的列名规格重新实现特征提取**，然后调用冻结模型推理。

## 2. 数据

包（原始，未改动）：

```
D:\Application\WechatHistory\xwechat_files\wxid_qfnm2p1ocigj22_9edf\msg\file\2026-11\IMU_07870ce8-a656-4a90-87af-783cc95cee5c.zip
```

已解包到：

```
D:\Project\imu环境重建\output\layout-recon\2026-11-05-handheld-001\
    bundle-manifest.json
    watch.jsonl                 (197,469 B)
    phone\
        accelerometer.csv       10,675 行
        gyroscope.csv           10,674 行
        anchors.csv
        events.jsonl
        integrity_report.json
```

CSV 列（两者相同）：

```
sequence, sensor_timestamp_ns, received_elapsed_realtime_ns,
writer_dequeued_elapsed_realtime_ns, x, y, z, accuracy
```

- 加速度单位 m/s²，陀螺单位 rad/s；`sensor_timestamp_ns` 纳秒。
- 跨度 **90.16 s**，采样率 **118.4 Hz**，两路各自连续、sequence 从 1 递增。
- 该录音**没有磁力计**。

## 3. 模型（不得重训）

```
D:\Project\imu环境重建\output\action-recognition\2026-11-03-heldout2-freeze-001\model-phone.joblib
```

`joblib.load` 后是一个 dict：`{"model": RandomForestClassifier, "columns": [...70 个元组...], "labels": [...]}`。

- `model.n_features_in_ == 70`，`n_estimators=400, random_state=0, criterion=gini, max_features=sqrt, bootstrap=True`
- 9 个类别（**顺序即模型类别编号**）：
  `close_cabinet, idle, lie_down, lying, open_cabinet, sit_down, stand_up, upright, walk`
- `columns` 是 `(设备, 特征名)` 元组，**必须严格按这个顺序拼行向量**。

### 70 列完整清单（顺序即输入顺序）

```
phone.acc_corr_01
phone.acc_corr_02
phone.acc_corr_12
phone.acc_end_start_direction_angle_rad
phone.acc_norm_mean
phone.acc_norm_q10
phone.acc_norm_q50
phone.acc_norm_q90
phone.acc_norm_range
phone.acc_norm_rms
phone.acc_norm_std
phone.acc_normalized_jerk_rms
phone.acc_x_end_minus_start
phone.acc_x_mean
phone.acc_x_range
phone.acc_x_std
phone.acc_y_end_minus_start
phone.acc_y_mean
phone.acc_y_range
phone.acc_y_std
phone.acc_z_end_minus_start
phone.acc_z_mean
phone.acc_z_range
phone.acc_z_std
phone.gyro_corr_01
phone.gyro_corr_02
phone.gyro_corr_12
phone.gyro_end_start_direction_angle_rad
phone.gyro_norm_mean
phone.gyro_norm_q10
phone.gyro_norm_q50
phone.gyro_norm_q90
phone.gyro_norm_range
phone.gyro_norm_rms
phone.gyro_norm_std
phone.gyro_normalized_jerk_rms
phone.gyro_x_end_minus_start
phone.gyro_x_mean
phone.gyro_x_range
phone.gyro_x_std
phone.gyro_y_end_minus_start
phone.gyro_y_mean
phone.gyro_y_range
phone.gyro_y_std
phone.gyro_z_end_minus_start
phone.gyro_z_mean
phone.gyro_z_range
phone.gyro_z_std
phone.temporal_acc_mean_0
phone.temporal_acc_mean_1
phone.temporal_acc_mean_2
phone.temporal_acc_norm_integral
phone.temporal_acc_std_0
phone.temporal_acc_std_1
phone.temporal_acc_std_2
phone.temporal_direction_first_0
phone.temporal_direction_first_1
phone.temporal_direction_first_2
phone.temporal_direction_last_0
phone.temporal_direction_last_1
phone.temporal_direction_last_2
phone.temporal_gyro_abs_integral_0
phone.temporal_gyro_abs_integral_1
phone.temporal_gyro_abs_integral_2
phone.temporal_gyro_energy_0
phone.temporal_gyro_energy_1
phone.temporal_gyro_energy_2
phone.temporal_gyro_integral_0
phone.temporal_gyro_integral_1
phone.temporal_gyro_integral_2
```

### 窗口规格（训练时冻结的）

- 事件起点后 `offset_s = 1.0` 秒开始，窗宽 `width_s = 3.0` 秒（即覆盖 [onset+1.0, onset+4.0) 秒）。
- 特征名里的 `_0/_1/_2` 表示把 3 秒窗**三等分**后的第 1/2/3 段。
- `temporal_*` 是分段统计；`acc_corr_ab` 是三轴相关系数；`*_end_minus_start` 是窗内首末差；`*_normalized_jerk_rms` 是归一化加加速度均方根；`*_end_start_direction_angle_rad` 是首末方向夹角。

**注意**：以上是列名语义的推断，原实现不在工作区。若重新实现的特征与该语义有出入，请**明确写出你的定义**，不要静默假设。

## 4. 输出要求

写一个 JSONL，每行一个窗：

```json
{"t_start_s": 1.0, "t_end_s": 4.0, "label": "walk", "proba": 0.83, "proba_all": {...}}
```

- 窗口按 0.5 秒步进滑过整段 90.16 秒。
- 另出一份**分段摘要**：把连续同标签的窗合并成区间，列出 `[起, 止, 标签, 平均置信度]`。
- 特别标注：`walk` / `sit_down` / `lying` / `stand_up` 四类的起止时刻。

## 5. 验收

1. 行向量长度 70、顺序与上面的清单逐字符一致（可用 `model.n_features_in_` 自检）。
2. 输出文件能被 `joblib` 模型直接接受，不报维度错。
3. 给出**自检证据**：随机抽 5 个窗，打印它们的 70 维向量前 5 个值，证明不是全零/全 NaN。
4. 报告`walk` 段总时长、`lying` 段起止——这两项会和视频对照（视频里 71 秒处躺在床上）。

## 6. 参考信息（不要用来“调参凑答案”）

同一次采集有视频：`D:\Application\QQ\downloads\IMG_0020.mp4`，118.19 s、29.97 fps、568×320，机位固定，画面里能看到床、书桌、椅子、门。人工目视：2 s 走动、24 s 坐椅子、71 s 躺在床上、95 s 在门口、116 s 走动。

IMU 录音 90.16 s 与视频 118.19 s **没有共同零点**，所以只能做定性对照，不能算时间对齐误差。

## 7. 已知的坑

- 上一轮我用经典 PDR 试过：55 个步候选，重力轴投影航向积分从 0 漂到 −714°、累计转角 2152°，相对轨迹是乱线。**不要**再走“陀螺积分求航向”这条路，这次只做动作分类。
- `watch.jsonl` 里也有数据，但本次只需要 phone 臂（70 列全带 `phone.` 前缀）。
