# 布局重建管线

输入一个 IMU 会话目录，输出房间与四件家具（床 / 桌 / 柜 / 椅）的带标签包围盒。

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
- 手机提供六轴 IMU；手表只有三轴加速度，不参与本管线。
- 目标类别清单始终给出，不推断「房间里有哪些类别的家具」。
