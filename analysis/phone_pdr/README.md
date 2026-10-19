# 手机六轴 PDR 诊断参考

2026-10-17。本模块独立于冻结的手机0.2.2、手表0.4.15与接收插件0.2.5；本轮仅本机新增，未提交或推送。用途是检查“步候选＋相对设备朝向”的计算链路，不是已验证的行人定位器或房间恢复器。

## 输入与运行

Python标准库，无模型下载或训练。输入为现有原生手机ZIP，或同时包含`metadata.json`、`accelerometer.csv`、`gyroscope.csv`的目录。不会解压/写回原件。

```powershell
python -X utf8 -m unittest discover -s analysis/phone_pdr/tests -v
python -X utf8 -m analysis.phone_pdr --session "现有原生ZIP的绝对路径" --output "D:/Project/imu环境重建/output/phone-pdr/新的独占目录名"
```

输出目录必须是工作区`output/phone-pdr/`的严格子目录，且尚不存在。拒绝逃出根目录的`..`、已存在目的地与链接父路径；文件独占创建。报错时保留原件、失败日志与可能产生的部分输出，改用新输出目录，不覆盖证据。

每通道序号按原生格式从**1**开始，严格连续；事件时间严格递增。核验字段、有限值、metadata的written计数及声明单位。时间先用整数纳秒减共同起点，再转秒；使用实际采样间隔，不假设请求100Hz就是实际100Hz。

声明单位要求加速度`m/s^2 including gravity`、角速度`rad/s`。约9.81的模长只能作一致性观察，不用来猜单位。`SensorEvent.timestamp`在此称Android传感器事件时间，不称独立验证的物理硬件时钟。读取成功不替代原生r2完整性验收。

## 算法和输出

- 模长双EMA、局部峰与0.3秒最小间隔生成**步候选**；默认阈值是工程起点，未在人类标注数据上调优。
- 重力反馈四元数积分提供设备相对yaw，处理手机倾斜，不只积分机身Z轴。没有磁场/地图校正，未标定陀螺偏置。
- 用四次根形式`k * amplitude**0.25`估计单步位移尺度。amplitude是本实现滤波峰谷差，其k须针对这一定义标定，不能直接搬别处系数。
- 未给k时，`relative_x/y`为未标定尺度，`x_m/y_m`为空；给了k也标`m_coefficient_unverified`，不自动认定它来自合格标定。
- 两通道只用共同时间段，记录边界排除数量；不排序修复、不填补超过1秒的输入空窗。每个候选用此前最近的陀螺姿态，并记录其时间年龄。
- `diagnostic.json`含输入摘要/版本、参数、假设和候选；`step-candidates.csv`含候选时刻、确认时刻、幅度、相对yaw和坐标。峰值需要后一个样本确认；未声明严格实时或观测前缀评测。

始终`research_validated=false`。初始加速度近似重力、手机方向随人行走且偏移固定，这些都是待检查假设。摆手/拿手机也会出峰；设备转动也不一定是人转弯。输出没有墙、家具、房间类型或布局精度。

## 本轮实跑与边界

14项合成/契约检查通过，含不均匀时间间隔90度转向、倾斜设备、四次根、异常输入和防覆盖。测试通过不表示真实步数/轨迹精度通过。

旧0.2.2约30分钟ZIP只读跑通：加速度213213行、角速度213212行，事件率约118.398/118.397Hz；共同时间段仅边界排除2行加速度。得到**100个候选**，不是100步真值。用户补记这条“主要原地操作”，不能用于房间行走验证；未给k、没有米制轨迹或墙图。输入前后SHA均为`1b98c5528911f49725a20174e16bce2b5c7722821f5f3aff75b430ec5f755996`。

诊断输出：`output/phone-pdr/2026-10-17-old022-handling-0ea991f3/`。证据：`docs/reviews/evidence/2026-10-17-ds052-pdr-390a9bdc/`。最初错误地按0起始序号验证，已依据冻结原生代码和CSV改成1起始；失败与红绿日志保留，原件未改。

## 与XGBoost的关系

PDR回答“相对走到哪里”；XGBoost候选回答“这段在做什么”。后者尚未训练，需要独立活动标注、按完整会话/人员分组的划分与类别概率。相邻滑窗不能随机拆分后冒充独立测试。

空间模块以后再结合轨迹、活动与不确定性。坐下事件最多提示可坐物件附近，不能直接判定椅子/沙发/床；步行直段不能直接当墙。完整目标与下一条短试见：

- `docs/protocols/2026-10-17-phone-pdr-short-controlled-walk.md`
- `docs/reviews/2026-10-17-ds052-disposition-and-phone-pdr.md`

## DS053后：显式分段与标定

新增独立命令，原`pdr.py`、`session.py`、`__main__.py`未改。先对整段算候选与姿态，再按注记选取；不逐段重新滤波/积分。新旧合计24项检查通过，并以合成原生ZIP端到端复算两次，三个输出文件逐字节相同；这仍不是人体轨迹验证。

```powershell
python -X utf8 -m analysis.phone_pdr.evaluate --session "原生ZIP绝对路径" --annotations "人工分段JSON绝对路径" --output "D:/Project/imu环境重建/output/phone-pdr/全新分段目录"
```

注记格式如下，**所有数字是合成示例，不能拿作真人会话标签**：

```json
{
  "schema_version": 1,
  "time_basis": "seconds_since_first_sensor_event",
  "annotation_source": "synthetic example only; replace with actual observation and clock mapping",
  "time_uncertainty_s": 0.05,
  "AB": {"start_s": 10, "end_s": 20, "distance_m": 12, "manual_steps": 20},
  "BC": {"start_s": 34, "end_s": 44, "distance_m": 12, "manual_steps": 20},
  "turn_before": {"start_s": 22, "end_s": 24},
  "turn_after": {"start_s": 28, "end_s": 30},
  "expected_turn_deg": 90
}
```

时间是两通道首个事件较早者之后的秒，继承原读取器的共同起点；人工计时的映射方法/偏差写在annotation_source，误差写time_uncertainty_s。manual_steps不清楚用null，不填猜测数字。屏幕朝上、顶边朝前时左转预期为正、右转为负；实际参考角与持法必须记录，不能强制结果匹配。

所有窗在共同段内且按AB、转前、转后、BC顺序互不重叠，`[start,end)`以滤波峰选择。原候选的1起始编号与对应旧诊断CSV物理行号（编号+1）保存；边界不确定候选列出，不自动剔除。至少两个AB候选才能计算删一敏感性；不足时明确报错，不自动降低阈值或补造步数。

输出`evaluation.json`、原字节`annotations.json`、`candidate-selections.csv`，包括k、AB/BC计数/编号、BC路径长度误差、转向静止窗中位数差、描述提示、输入/代码SHA。输出不含墙与布局精度，也不声称连续轨迹/终点真值成立。

删一个候选的k范围来自实际权重；加一个候选只假定新增权重落在观测最小/最大之间，未知漏步不一定满足，不是置信区间。提示“步数差≤1、转角误差≤15°、标定候选<15”仅用于排查，不是科学通过标准。

旧诊断的accelerometer/gyroscope统计覆盖全流；新评价另列full_stream_statistics与overlap_statistics，共同观察跨度为overlap_span_s。候选在共同段检测，不能除以全流跨度混作观测速率。relative_device_yaw_end_rad仅是整段设备yaw末值，不是漂移率或单次转角；滤波峰延迟也不是固定80ms。

## DS055后：持法风险与水平主轴诊断

新增`carry_diagnostic.py`，旧pdr/session/evaluate保持，合计31项检查通过。本模块不恢复人体轨迹，结果明确`body_heading_observable=false`、`global_trajectory=null`，跨窗口人体转角不填。

```powershell
python -X utf8 -m analysis.phone_pdr.carry_diagnostic --session "已有原生ZIP" --output "D:/Project/imu环境重建/output/phone-pdr/新持法诊断目录"
```

沿用旧姿态更新并保留四元数trace，按一秒窗统计估计重力坐标下的水平/竖直角速度。默认水平RMS>0.35rad/s或总峰值>4rad/s标device_rotation_risk，竖直RMS>0.35rad/s标yaw_rotation_ambiguous；余者只称quiet_device_rotation。阈值是未调优的工程起点，不是人动作或稳定携带真值。

加速度旋到任意yaw的估计重力坐标系，XY按窗去均值做2x2协方差。方差不足0.05或主能量占比不足0.75时主轴未知；否则仅给mod180°轴和相反的两种方向。PCA可跟随侧摆而非前进，不能用地图/右转90°选择符号。均未给距离尺度、位置、墙或房间。

输出carry-diagnostic.json和window-metrics.csv，含源码/输入SHA、全部原候选和风险身份。原47.53秒记录得到48窗（23低转动/24转动风险/1竖直歧义），24候选全部保留；没以删数据制造直线。原件上新trace与旧yaw逐样本差为0，说明沿用同一算法，不表示真实姿态已验证。

已保留反例：纯竖直轴换握与人转身不能靠此分类保证分开；纯pitch过90°可让设备X轴水平投影反向、Euler yaw变180°而世界竖直角速度为0；横摆主导PCA可以指向侧方。对应结果见`docs/reviews/2026-10-17-ds055-codex-disposition-and-carry-diagnostic.md`。
