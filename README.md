# IMU 室内家具布局重建

本仓库研究：在明确侧信息和采集协议下，手机与手表的惯性观测能将二维家具布局约束到什么程度，以及活动增加后候选范围如何变化。目前已跑通**手机六轴 IMU → 轨迹 → 五类动作 → 家具框**的真实单房案例；手机与手表联合布局增益、跨房活动阈值仍待验证。

当前版本于 2026-11-08 复核。最新完整论证和 DS 交接见 [活动泄露边界](docs/research/2026-11-08-activity-leakage-frontier.md)，数值入口为 [RESULTS.md](RESULTS.md) 与 [activity-results.json](analysis/layout/activity-results.json)，运行摘要见 [activity-run.json](analysis/layout/activity-run.json)。[current-run.json](analysis/layout/current-run.json) 保留上一轮快照，不代表当前全部源码的重算。

最新进展：真实开发记录在 0.25 秒细网格中首次于 **37.0 秒**四件中心误差均 ≤0.5 m，前一档 36.75 秒未过；两档估计覆盖均约 33.47%。这说明该案例由交互窗口成熟触发，不能解释成跨房覆盖阈值。14 房几何活动实验的完整布局仍未达到预设的 80% 门槛；开发床门槛未通过新路线/误差确认。

## 当前能做什么

- 真实输入：手机原始加速度与角速度。手表三轴加速度可以生成旁证摘要，尚未进入家具位置估计。
- 已提供的侧信息：房间外框、室内起点、目标家具类别与尺寸，以及受控手持/坐卧姿态协议。当前实现**不从 IMU 发现房间外框、门位置或家具高度**。
- 输出：轨迹、动作窗口、床/桌/柜/椅的二维矩形及部分输出状态。模拟后端另提供候选布局和条件区间诊断。
- 家具固定；床和椅允许接触及轨迹进入占地。通行惩罚针对桌柜；不同后端的通行标签、互避让和墙关系仍有差别。
- 两路墙支持分数是固定带宽的启发式评分，不是校准后的概率；top-K 枚举也不是后验采样。

## 安装与输入准备

Python 依赖以本轮验证环境为准：

```powershell
python -m pip install -r analysis/layout/requirements.txt
```

仓库包含冻结的五类动作 RF 与特征代码。模型由四条同人开发记录的 340 个重叠窗口训练；类别为 walk、seated、lying、cabinet、other。冻结只使推理可复现，不代表跨人、跨房泛化准确率已经验证。模型与训练来源摘要见 [模型说明](analysis/layout/models/phone-five-class.json)。

以下外部输入没有随仓库分发，干净克隆不能自动下载它们：

| 输入 | 设置方式 | 用途 |
|---|---|---|
| RoNIN 作者模型结构 | `IMU_LAYOUT_RONIN_ARCH` | 手机轨迹 |
| RoNIN 预训练权重 | `IMU_LAYOUT_RONIN_CKPT` | 手机轨迹；按原作者许可获取 |
| AI2-THOR 场景导出 JSON 目录 | `IMU_LAYOUT_THOR` | 几何模拟 |
| 原始手机会话包 | 命令行参数 | 真实录音重放 |
| 派生会话目录 | `IMU_LAYOUT_SESSION` 或 `--session` | 真实诊断 |

RoNIN 来源为 [Sachini/ronin](https://github.com/Sachini/ronin)，适配约定与已核对摘要见 [adapter.py](analysis/phone_ronin/adapter.py)。场景 JSON 包含 `floor=[center_x,center_z,width,length]`、`agent` 与 `objects` 的 type/center/size 字段；数据仍需纠正上游导出中心定义，现有字节已冻结供本轮重放。原始录音、视频、雷达点云和签名密钥不公开。

## 可执行入口

在仓库根目录，先设置上表环境变量。以下尖括号内容必须替换为自己的文件路径。

```powershell
# 真实单房案例：重新生成轨迹、动作和布局，不使用旧轨迹缓存
python analysis/layout/analyze.py <bundle.zip> <new-session-dir>

# 本轮全部受影响诊断和扰动实验；需同时提供场景与 RoNIN 输入
python -m analysis.layout.reproduce --bundle <bundle.zip> --session <new-session-dir>

# 回归检查
python -m unittest discover -s analysis/layout/tests -v

# 稠密语义栅格：默认高度来自类别先验，另外输出 PNG/PDF/JSON/NPZ
python -m analysis.layout.dense_map <new-session-dir> --height-source prior

# 使用明确提供的参考高度；文件为 {"bed":0.5,"desk":0.75,"cab":0.75,"chair":0.45}
python -m analysis.layout.dense_map <new-session-dir> --height-source reference --height-json <heights.json>
```

`analyze.py` 是本间受控房间的生产入口，室内尺寸和起点参数仍在代码中；不能将它直接用于任意未知房间后宣称通用重建。多房模拟使用参数化的 `layout_core.py` / `layout_free.py`，其结果与生产入口分别报告。

## 两项经常混淆的进度

**原始 IMU 输入模拟：生成与独立运动学检查已实现，下游兼容性未通过。** 六轴生成流经过姿态、导数和再积分检查，但冻结 RoNIN 路程比仍为 0.6645、柜动作召回为 0，不能用于声称多房 IMU 阈值。多房活动结果仍是几何路线/交互输入；腕表不生成不可观测的角速度。

**稠密语义图：已完成可读取的 2.5D 表达。** 二维预测矩形栅格化为类别与高度数组；高度来自类别先验或提供的参考值。未赋类单元表示未知，不能解释成确认的空地。图示墙高仅用于显示。它没有恢复真实表面、家具细节或完整三维场景。

## 证据范围

本轮模拟从 25 个导出场景中得到 15 个类别齐全场景；其中 FloorPlan309 的目标框越界，按预先记录的几何规则排除，剩 14 个用于主后端诊断。重复加噪不增加独立房间数。类别高度与简化跨度分析使用不同对象集合，必须单列分母。

真实端只有一间开发房。原始 IMU 前缀中最早四件家具全部输出的测试点为 40 s；这是当前算法在该记录、该网格下的可用性结果，**不是“活动 40 秒即可重建任何房间”的阈值**。条件区间变窄也必须同时检查覆盖真值和跨模式歧义。

## 目录

| 目录 | 内容 |
|---|---|
| `analysis/layout/` | 本轮布局、前缀、候选集和敏感性诊断 |
| `analysis/phone_ronin/` | 六轴惯性里程计适配 |
| `analysis/action_recognition/`、`analysis/joint_privacy/` | 动作与双端研究基础模块 |
| `collection/` | 手机和手表采集端源码 |
| `paper/`、`research/` | 历史手稿与研究材料 |
| `tools/` | 仓库检查与维护 |

代码地址：[tuoLuoSuan/imu-layout-privacy-research](https://github.com/tuoLuoSuan/imu-layout-privacy-research)。论文引用与许可信息待正式稿完善；第三方代码和模型沿用各自许可。
