# 2026-11-11 类别配额固定的接触选择：64 房批次（select032_64 / run 034）

## 动机：为什么把冻结实验跑到 64 房

12 房确认批（`docs/research/2026-11-11-class-balanced-selection-032.md`）只够报方向：`bal_disperse` 对 `bal_random` 的逐房配对差 +0.0899、9 好 1 差 2 平，用精确符号秩检验算 p = 0.080，落在显著线之外。审稿必然会问：这到底是效应，还是 12 个房间的抽样噪声。要回答这个问题只有一条路——不改规则、不重新调参，把同一个模块（SHA256 `af72bac446afe5ae5865b33545da2d1ccfbb60454020439c896a9767e9a9a12c`）跑到更大的房间块上，让逐房配对检验有 64 个配对单位。

房间块 11700–11763 是连续 64 个 id，其中**11700–11711 就是 12 房确认集本身**，11712–11763 共 52 个房间是首次进入这个实验。所以 64 房不是"换一批新房间重做"，而是"确认集 + 52 个新房间"：这 12 个房间在新批次里逐行复现（108 行 f1、`all_instances_hit`、`contacts_kept` 与 `stage-confirm.json` 完全相同，最大差 0），这既是流水线的确定性检查，也说明 64 房与 12 房批次的数字可以直接比较。真正的新证据是那 52 个房间，单列在 `paired64_new52.json` 里。

## 冻结的规则（两行）

- k = 6；配额 = 对该房可用的 seated/lying/cabinet 接触计数做最大余数分配、每个存在的类别至少 1 个（5/4/5→2/2/2，1/0/5→1/0/5）；`bal_random` 同配额随机子集、种子 500000+10·room+s，`plain_random` 无配额随机 6 个、`selectcount026.seed_of` = 26000+10·room+s，s ∈ (1,2,3)；`bal_disperse` 从离房间中心最远的接触起步、此后每次取"离已选集合最远且所在类别仍有配额"的接触；`bal_oracle` 按真值类别 chair/bed/cab 的物体中心，每个物体先取最近的那个接触（精度对照，不是全局上界）。
- 选完之后走同一条链：`selectcount026.arm → contact_loops011 → wall_refine012 → priorcost014 base → score_instances`；非接触 run 从不丢弃；接触位置取未精修前端轨迹在 run 时间中点的坐标。本批次除了房间 id 之外没有任何参数、种子或阈值变化，两个 stage 的 `protocol.rules` 与模块 SHA 完全一致（`paired64.json.sources_consistent.passed = true`）。

## 运行

```
# 第一次尝试（失败，日志保留）：jobs=6 时 6 个 OpenBLAS 线程池把内存打爆
python -m analysis.layout.selectbalanced032 --rooms 11700-11763 --jobs 6 \
  --out output/layout-recon/select032_64 --stage confirm64   # → BrokenProcessPool, run_confirm64.log

# 按预案拆成两个 32 房 stage（同一输出目录），BLAS 线程钉到 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m analysis.layout.selectbalanced032 --rooms 11700-11731 --jobs 3 --out output/layout-recon/select032_64 --stage confirm64a
python -m analysis.layout.selectbalanced032 --rooms 11732-11763 --jobs 3 --out output/layout-recon/select032_64 --stage confirm64b

# 统计（从 stage 原始行重算，不使用模块自带的 paired()）
python -m analysis.layout.selectbalanced64_034 --out output/layout-recon/select032_64 --stages confirm64a,confirm64b
python -m analysis.layout.selectbalanced64_034 --out output/layout-recon/select032_64 --stages confirm64a,confirm64b \
  --target output/layout-recon/select032_64/paired64_new52.json --rooms 11712-11763
```

第一次尝试一行都没写出：日志开头就是反复刷出的 `OpenBLAS error: Memory allocation still failed after 10 retries, giving up.`（28 次），随后 `selectbalanced032.py:368` 的 `pool.map` 抛 `BrokenProcessPool`——worker 是被直接终止的，日志里没有 worker 内部 traceback（本机 31.5 GiB 中可用只约 6.7 GiB、12 核，6 个 worker 各自会拉起 OpenBLAS 线程池）。单房试探确认 `OPENBLAS_NUM_THREADS=1` 下单房 12.3 s、9 行、0 error，于是两个 stage 各用 jobs=3。`confirm64a` 11700–11731 用时 218.6 s、`confirm64b` 11732–11763 用时 200.9 s，合计 576 行（64 房 × 9 行），**error 行 0**。

## 结果（按房聚合，不把行当独立样本）

随机臂每房 3 个种子：先在房内取三种子的均值，再对房间取均值；base/bal_disperse/bal_oracle 每房 1 行。命中列沿用 12 房文档的口径——"跑了多少行里的整屋命中数"，随机臂的分母是 192 行；跨臂比较请看"每房命中率"。

| 臂 | 房间 | 整屋命中 | 行数 | 平均 F1 | 每房命中率 | 平均 k |
|---|---|---|---|---|---|---|
| base | 64 | 48 | 64 | 0.9304 | 0.7500 | 14 |
| bal_random | 64 | 77 | 192 | 0.7770 | 0.4010 | 6 |
| bal_disperse | 64 | 38 | 64 | 0.8972 | 0.5938 | 6 |
| bal_oracle | 64 | 11 | 64 | 0.6818 | 0.1719 | 6 |
| plain_random | 64 | 53 | 192 | 0.7525 | 0.2760 | 6 |

状态分布（576 行全部保留，非 ok 行 f1 记 0，与 026/030/032 口径一致）：ok 552 / `proposal_conflict` 14 / `search_budget_exhausted` 9 / `no_proposals` 1。这些是解码器自身的状态，不是异常，也没有剔除。

## 三组配对对比（逐房，随机臂先取三种子均值）

| 配对 | 平均差 | 95% CI | 好/差/平 | 精确符号秩 p | 符号翻转 p（MC） | 整屋命中差 好/差/平 |
|---|---|---|---|---|---|---|
| `bal_disperse − bal_random` | +0.1202 | [+0.0660, +0.1744] | 44/6/14 | 1.33e-07 | 3.5e-05 | 26/7/31 |
| `bal_random − plain_random` | +0.0245 | [−0.0191, +0.0681] | 29/18/17 | 0.284 | 0.275 | 21/4/39 |
| `bal_oracle − bal_random` | −0.0952 | [−0.1512, −0.0392] | 16/35/13 | 1.13e-03 | 1.17e-03 | 3/28/33 |

- 平均差定义：逐房 `F1(a) − F1(b)` 的均值，其中每臂先按房聚合（随机臂取三种子均值，非随机臂是单行）。逐房差的四分位（`bal_disperse − bal_random`）：最小 −0.7619、Q1 0.0000、中位 +0.0833、Q3 +0.2056、最大 +0.8333。分布不是靠少数大正值撑起来的：中位数为正、Q3 明显为正，坏的方向只有 6 个房间。
- 精确符号秩检验：零差丢弃（`bal_disperse − bal_random` 14 房为零差，故 n = 50），同值取中位秩后**按并列结构枚举零分布**（并列组 24 组），不是正态近似；用 14 项子集暴力枚举 2^14 个符号模式交叉验证过，9 次抽样与 DP 结果差 0。符号翻转 p 是 200000 次抽样的 Monte-Carlo 对照（种子 20261111），与精确值同量级。
- 断言（brief 要求）：配对差的均值必须等于两臂房间均值的差。三组分别是 gap = 0.0、6.94e-18、1.39e-18（阈值 1e-12），`paired64.json.assertions.paired_mean_equals_arm_mean_difference.passed = true`。随机臂每房都恰好贡献种子 1、2、3（`seed_mean_not_single_seed.passed = true`），所以这次不存在"用了某一个种子当随机臂均值"的问题。

## 相对 12 房确认批，变了什么

12 房确认批：`bal_disperse` 7/12、平均 F1 0.8829，`bal_random` 16/36、0.7929，配对差 +0.0899、9/1/2——方向对，但精确符号秩 p = 0.080125（同一统计模块对 `stage-confirm.json` 的重算，见 `paired12_reference.json`），只能说"不显著、方向一致"。64 房批次把这个差推到 +0.1202、44/6/14、p = 1.33e-07、95% CI [+0.066, +0.174] 不含 0：**结论没变，变的是它能承受的推断强度**。这不是新效应，也不是换样本换出来的——12 房那 12 个房间在新批次里逐行复现，点估计从 +0.090 涨到 +0.120 只是多了 52 个房间后的加权结果；把这 52 个首次使用的房间单独拿出来仍然是 +0.1272、35/5/12、p = 9.97e-07，方向与量级一致。另外两个对照在更大样本上给出的信息也更清楚：`bal_random − plain_random` 是 +0.0245（p = 0.284，CI 跨 0），与 12 房批次两批反号（开发集 +0.070、确认集 −0.0122）一起说明**固定类别配额本身不是收益来源**；`bal_oracle − bal_random` 在 64 房上是 −0.0952（p = 1.13e-03），把 12 房"真值取点反而不如随机"的描述性观察变成一个显著的负效应，原因是同一个：6 个名额被压到少数几个真值物体上，而评分要求覆盖房间里出现的每个真实实例。

## 边界：这个实验不能声称什么

- **单一解码器、单一精修链**：全部数字来自 `priorcost014.decode_arm('base')` + `contact_loops011 → wall_refine012`；换解码器或精修链之后这 +0.12 是否还在，本实验没有回答（同一批次的 decoder-transfer 是另一份文档、另一组实验，不能互相背书）。
- **只有 k = 6**：没有扫 k 曲线，不能外推到 k=3、k=9 或全量接触；也不能把"6 个里怎么选"的结论当成"该保留多少接触"的结论。
- **一种摆位协议**：一个场景生成器、visits=14、severity=0.0、offset=0、prefix 流；其他摆位/遮挡/录制长度下是否成立未测。
- **房间不是全新的独立样本**：64 房里 12 个（11700–11711）与确认批重叠且逐位复现，真正的新房间是 52 个；"64 房"作为一个样本量来报功效时，应理解为 12 + 52 的合并，而不是 64 个从未用过的房间。
- **非 ok 行保留为 f1 = 0**：`proposal_conflict` 14 行、`search_budget_exhausted` 9 行、`no_proposals` 1 行会同时压低相应臂的均值；这是与 026/030/032 一致的口径，没有做剔除，也没有另算"只统计成功行"的版本。
- **F1 与整屋命中不是物理精度**：它们衡量的是"该房出现的实例是否被全部找回、匹配得多好"，不外推到真实房间部署、也不外推到定位/建图精度。
- 本批只有一次运行（拆成两个 stage），没有重复整套实验来估流程噪声；房间间的方差已计入配对检验，机器/调度噪声没有单独估计。

## 产物

- `analysis/layout/selectbalanced64_034.py`（新模块，SHA256 `5294aa54cbb72dbc45274e0a2b246567d2eef264f6ec65a278c1f1f8d0da7c2e`）：读 stage 文件、按房聚合、三组配对、精确符号秩 + 符号翻转、断言。
- `output/layout-recon/select032_64/stage-confirm64a.json`、`stage-confirm64b.json`：两个 stage 的 288 行 × 2，含 protocol/module SHA。
- `output/layout-recon/select032_64/paired64.json`：64 房汇总、三组配对（含逐房差）、断言、`sources_consistent`。
- `output/layout-recon/select032_64/paired64_new52.json`：只用 11712–11763 的 52 个新房间重算的同一套统计。
- `output/layout-recon/select032_64/paired12_reference.json`：用同一统计模块对 12 房 dev/confirm 的重算（只读旧 stage 文件），本文引用的 12 房 p 值出自这里。
- `output/layout-recon/select032_64/run_confirm64.log`（失败的第一次尝试）、`run_confirm64a.log`、`run_confirm64b.log`、`run_split.log`、`paired64_stdout.txt`。
