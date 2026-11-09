# 布局重建管线

输入一个 IMU 会话目录，输出房间与四件家具（床 / 桌 / 柜 / 椅）的带标签包围盒。2026-11-09新增手机＋手表入口：手机供轨迹和坐／躺事件，**柜门事件仅由手表三轴加速度给出**。旧手机入口保留作回归与对照。

## 手机＋手表与万房实验（009）

完整结果和解释见 [万房与双设备交接](../../docs/research/2026-11-09-ten-thousand-joint-imu.md)。三条入口的前提与端点不同，不能合并为一个成功率：

| 入口 | 输入与作用 | 范围 |
|---|---|---|
| `joint009.infer` | 手机六轴CSV＋手表三轴加速度CSV；手机静止端点积分，手表柜门事件，固定姿态朝向协议 | 100间受控四件房；模拟域手表规则与真实训练RF分臂 |
| `python -m analysis.layout.joint_real009` | 冻结RoNIN的真实原始重放＋同次手表；清除手机柜门事件后只用手表分类事件 | 既有单房案例；软件对齐，物理时钟未验 |
| `expansion10000` / `threshold009` / `dense_visits009` | 理想轨迹与语义接触坐标，已知外框／数量／尺寸 | 10,000间、55,000件；不是10,000次原始IMU推理 |

`watch_cabinet.fuse()` 在联合臂中删除手机的柜门结果；没有手表时不回退到手机柜门事件。模拟实际写出并读取 `watch/accelerometer.csv`，不把模拟动作标签当作柜门输入。手表没有陀螺仪，不补造六轴能力。

新增模块：`contact_contract`（设备位置／操作面／朝向契约）、`sim_handset` / `sim_watch`（两设备信号）、`inertial_replay`（静止端点基线）、`wrist_binary`（既有r1/r2训练，r3/r4腕部评估）、`joint_prefix009`（先截原始数据）、`joint_watch_controls009`（同手机数据的错时／缺表对照）、`fig_expansion009`（静态图）。

## 一条命令

```bash
IMU_LAYOUT_SESSION=<会话目录> python analysis/layout/analyze.py <bundle.zip> <输出目录>
```

## 模块

| 文件 | 作用 |
|---|---|
| `run_any_bundle.py` | 解包 → RoNIN → `ronin-xy.npy`（IMU 到二维轨迹） |
| `reconstruct_blind.py` | 房间先验常量、动作锚点提取、动作分类 |
| `layout_solver.py` | **主求解器**：四面墙联合似然 + 四件家具放置，产出 `prediction.json` |
| `layout_free.py` | 逐物体放置的一组可替代规则（床脚边、柜臂展、桌椅相对） |
| `layout_core.py` | 几何工具（矩形距离、重叠、点在框内） |
| `sim_eval.py` | 在 AI2-THOR 场景上做评测的辅助函数 |
| `paths.py` | 数据与权重的解析位置 |

## 路径

三个环境变量覆盖默认位置（默认都在仓库外或已 gitignore 的目录）：

| 变量 | 含义 |
|---|---|
| `IMU_LAYOUT_DATA` | 原始录音、点云、中间结果所在目录 |
| `IMU_LAYOUT_SESSION` | 单次会话目录（内含 `ronin-xy.npy`、`actions.json`、`phone/`） |
| `IMU_LAYOUT_THOR` | AI2-THOR 场景导出目录 |
| `IMU_LAYOUT_RONIN_ARCH` / `IMU_LAYOUT_RONIN_CKPT` | RoNIN 的网络定义与权重 |

## 输出

`prediction.json` 的主要字段：

```
status            ok | no_solution | missing_action
rot_deg           轨迹旋入房间坐标系的角度
cabinet_wall      柜所在的墙
wall_support      该墙的联合似然
boxes             bed / desk / cab / chair 的 [x0, y0, x1, y1]
anchors           三个动作锚点（房间坐标）
premise           自检：椅子单独定的墙 vs 柜子单独定的墙是否一致
```

`premise.ok = false` 表示「椅子在桌前」这一结构前提可疑，此时 `boxes` 中的桌与柜不应直接采信。

## 前提

- 房间外框与家具类别尺寸作为**已知先验**输入（`reconstruct_blind.py` 顶部常量）。
- 旧 `analyze.py` 手机入口只使用手机六轴；上方009联合入口使用手表三轴加速度识别柜门，二者的结果必须分开记账。
- 目标类别清单始终给出，不推断「房间里有哪些类别的家具」。
