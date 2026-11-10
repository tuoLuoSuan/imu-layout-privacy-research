# 2026-11-11 类别配额固定的接触选择（select032）

## 动机

select026 已经把「只保留部分接触事件、其余事件全部保留」这条链路建好，并用空间最远点（`pick_disperse`）相对随机抽样拿到过收益。审稿问题：这部分收益究竟是**类别配比**（少数类别被随机漏掉，导致某些类别整类缺席）带来的，还是**空间分散**本身带来的？

本实验把类别配比钉死：每条录音只选 k=6 个接触事件，seated/lying/cabinet 的配额按该房可用接触数用最大余数法分配、且每个存在的类别至少 1 个。配额固定之后，臂之间只剩「选哪几个」这一个自由度，于是 `bal_disperse` 与 `bal_random` 的差就只可能来自空间位置。

规则在跑确认集之前写死（模块 SHA 与 protocol 原文写进 stage-dev.json），确认集只在开发集冻结之后跑一次。

## 冻结的规则（原文，摘自 `select032.json.protocol`）

- visits = 14，severity = 0.0，offset = 0，streams = prefix。
- 配额：`largest remainder over available seated/lying/cabinet counts, min 1 per present class`。实现见 `selectbalanced032.quota(counts, k)`；校验：可用 5/4/5 → 2/2/2，1/0/5 → 1/0/5，1/1/1 → 2/2/2。
- `bal_random`：同配额随机子集，种子 `500000 + 10*room + seed`，seed ∈ (1, 2, 3)。
- `bal_disperse`：`start farthest from room centre, then farthest from the chosen set among classes with quota left`。
- `bal_oracle`：`quota-respecting truth classes chair/bed/cab, nearest contact per object first`（精度上界对照，只用真值类别与目标位置）。
- `plain_random`：不设配额的随机 6 次，沿用 `selectcount026.seed_of = 26000 + 10*room + seed`，seed ∈ (1, 2, 3)。
- 接触位置：未精修前端轨迹在 run 时间中点处的坐标。
- 非接触 run 一律保留（`selectcount026.subset`）。
- 选择之后一律走同一条链：`selectcount026.arm -> contact_loops011 -> wall_refine012 -> priorcost014 base -> score_instances`，本模块不重写精修/解码。

开发集 11500–11511，确认集 11700–11711，两批参数完全相同；模块 SHA256 `af72bac446afe5ae5865b33545da2d1ccfbb60454020439c896a9767e9a9a12c` 在两批 stage 文件中一致，`protocol.confirm_ran_after_dev = true`（dev 23:41:32 完成，confirm 23:46:04 完成）。

确认集为什么是 117xx：`grep` 发现 `analysis/layout/exp_sensor013.py:89` 的 `ids = list(range(11400, 11400 + count))` 与 `docs/research/2026-11-09-wall-prior-and-sensor-axis.md` 已经用过 11400–11411，因此按预案改用 11700–11711。输出目录扫描（12,624 个目录、446 个房间目录）显示 117xx 里只有 11704 出现过，位置是 `output/research-sync/2026-11-09-joint-input-and-recovery-010/raw-final100/multi-11704`（010 联合输入实验的输入暂存包，含 evaluation-truth.npz/input/results.json），不是接触选择结果；11000–11799 中不存在完全未被任何模块引用的 12 连号区段，这一点如实记录。

## 门

`base`（全部 14 个接触）必须复现 `output/layout-recon/select026b/select026.json`：

- 整屋命中 7/12，平均 F1 = 0.8134920634920634（0.8135）。
- 逐房 `all_instances_hit` 与 f1 在 1e-9 内逐位相等（含 11505 的 `proposal_conflict` → f1 0.0）。

门通过（`select032.json.gate.passed = true`）。另一条交叉校验：`plain_random` 在开发集得到 8/36、平均 F1 0.6435，与 select026 的 random 臂 8/36、0.6435 完全一致，说明种子方案与 026 的随机语义对齐。

## 结果

整屋命中按「跑了多少行里的命中数」记：base/bal_disperse/bal_oracle 每房 1 行（12 行），两个 random 臂每房 3 个种子（36 行）。

### 开发集 11500–11511（jobs=2，255.4 s）

| 臂 | 整屋命中 | 行数 | 平均 F1 | 平均 k |
|---|---|---|---|---|
| base | 7 | 12 | 0.8135 | 14 |
| bal_random | 14 | 36 | 0.7136 | 6 |
| bal_disperse | 7 | 12 | 0.7639 | 6 |
| bal_oracle | 3 | 12 | 0.6806 | 6 |
| plain_random | 8 | 36 | 0.6435 | 6 |

### 确认集 11700–11711（jobs=2，264.3 s）

| 臂 | 整屋命中 | 行数 | 平均 F1 | 平均 k |
|---|---|---|---|---|
| base | 10 | 12 | 0.9603 | 14 |
| bal_random | 16 | 36 | 0.7929 | 6 |
| bal_disperse | 7 | 12 | 0.8829 | 6 |
| bal_oracle | 2 | 12 | 0.7252 | 6 |
| plain_random | 11 | 36 | 0.8052 | 6 |

### 逐房配对差（主端点：bal_disperse − bal_random 三种子均值）

开发集：

| 房间 | base 命中/F1 | bal_random 均值 | bal_disperse | 配对差 | bal_oracle | plain_random 均值 |
|---|---|---|---|---|---|---|
| 11500 | 1 / 1.0000 | 0.6000 | 1.0000 | +0.4000 | 0.8000 | 0.8000 |
| 11501 | 1 / 1.0000 | 0.9444 | 1.0000 | +0.0556 | 1.0000 | 0.9444 |
| 11502 | 0 / 0.8333 | 0.8333 | 0.8333 | 0.0000 | 0.6667 | 0.7778 |
| 11503 | 0 / 0.7143 | 0.3333 | 0.0000 | −0.3333 | 0.4286 | 0.3810 |
| 11504 | 1 / 1.0000 | 0.9167 | 1.0000 | +0.0833 | 1.0000 | 0.8333 |
| 11505 | 0 / 0.0000 | 0.1333 | 0.0000 | −0.1333 | 0.4000 | 0.1333 |
| 11506 | 1 / 1.0000 | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 0.8000 |
| 11507 | 0 / 0.5000 | 0.6111 | 0.5000 | −0.1111 | 0.0000 | 0.2222 |
| 11508 | 1 / 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.8000 | 0.9333 |
| 11509 | 1 / 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.8333 | 0.6667 |
| 11510 | 1 / 1.0000 | 0.6667 | 0.8333 | +0.1667 | 0.6667 | 0.6111 |
| 11511 | 0 / 0.7143 | 0.5238 | 1.0000 | +0.4762 | 0.5714 | 0.6190 |

符号统计：好 5 / 差 3 / 平 4，平均配对差 +0.0503。次端点（整屋命中，按房配对）好 4 / 差 0 / 平 8，平均 +0.1944。

确认集：

| 房间 | base 命中/F1 | bal_random 均值 | bal_disperse | 配对差 | bal_oracle | plain_random 均值 |
|---|---|---|---|---|---|---|
| 11700 | 1 / 1.0000 | 0.9333 | 1.0000 | +0.0667 | 0.6000 | 0.8000 |
| 11701 | 1 / 1.0000 | 0.6111 | 0.8333 | +0.2222 | 0.8333 | 0.8889 |
| 11702 | 1 / 1.0000 | 0.8889 | 1.0000 | +0.1111 | 0.6667 | 0.9444 |
| 11703 | 1 / 1.0000 | 0.4762 | 0.7143 | +0.2381 | 0.7143 | 0.7619 |
| 11704 | 1 / 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.7500 | 0.8333 |
| 11705 | 1 / 1.0000 | 0.9333 | 1.0000 | +0.0667 | 0.8000 | 0.9333 |
| 11706 | 1 / 1.0000 | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 0.9333 |
| 11707 | 0 / 0.6667 | 0.8889 | 0.5000 | −0.3889 | 0.6667 | 0.4444 |
| 11708 | 1 / 1.0000 | 0.8000 | 1.0000 | +0.2000 | 0.6000 | 0.7333 |
| 11709 | 1 / 1.0000 | 0.8333 | 1.0000 | +0.1667 | 1.0000 | 0.9444 |
| 11710 | 1 / 1.0000 | 0.7222 | 0.8333 | +0.1111 | 0.5000 | 0.7778 |
| 11711 | 0 / 0.8571 | 0.4286 | 0.7143 | +0.2857 | 0.5714 | 0.6667 |

符号统计：好 9 / 差 1 / 平 2，平均配对差 +0.0899。次端点好 5 / 差 2 / 平 5，平均 +0.1389。

### 其他配对与状态

- `bal_random − plain_random`（只看配额、不看空间）：开发集 F1 +0.0700（好 7 / 差 3 / 平 2）、整屋命中 +0.0833（好 5 / 差 0 / 平 7）；确认集 F1 −0.0122（好 5 / 差 6 / 平 1），整屋命中 16/36 对 11/36。也就是说，单靠配额既不帮忙也不复现。**这一行已更正**，见文末「更正」。
- `bal_oracle − bal_random`：开发集 −0.0330（好 6 / 差 4 / 平 2），确认集 −0.0678（好 4 / 差 7 / 平 1）。按真值类别取「每个物体最近的那个接触」在实践中不是上界，反而低于随机：它把 6 个名额压到少数几个物体上，而评分要求覆盖该房出现的每个真实实例，集中取点会漏掉别的物体；这是 oracle 设计本身的缺陷，不改写、如实报。
- 状态分布（所有失败行保留，非 ok 行 f1 记 0，error 行 0）：开发集 108 行 = ok 96 / proposal_conflict 11 / search_budget_exhausted 1；确认集 108 行 = ok 105 / proposal_conflict 2 / search_budget_exhausted 1。`proposal_conflict` 与 `search_budget_exhausted` 是解码器自身的状态，不是异常，两批都原样保留在 JSON 里。
- 配额在两批 24 个房间里都是 2/2/2（每房可用 5/4/5、共 14 个接触）；本批没有出现某类别缺席的房间，1/0/5 这类退化情形由 `quota()` 处理并单独验证，但没有在本实验的房间里发生。

## 结论（只按数字）

1. 先冻结、再确认这一次成立：确认集上 `bal_disperse` 在 12 个房间里 9 好 1 差 2 平，平均配对差 +0.0899；整屋命中 7/12 对 `bal_random` 的 16/36（按房平均 5.33/12）。开发集方向相同但更弱（+0.0503，5/3/4）。
2. 配额本身不足以解释这个差：`bal_random` 对 `plain_random` 的平均 F1 在开发集是 +0.0700、在确认集是 −0.0122，两批反号、量级也小于分散效应。所以「把类别配比钉死」本身不是收益来源，收益来自**同一配比下的空间分散**。
3. 因此对审稿问题的回答是：在 k=6、配额固定的条件下，接触选择的收益主要来自空间分散，而不是类别配比；类别配比的效果在两个批次的 F1 上不一致。
4. 确认集上 6 个接触的 `bal_disperse`（7/12、0.8829）仍低于 14 个接触的 `base`（10/12、0.9603），即分散选择缩小但不能消除与全量接触的差距。

## 边界

- 每个批次只有 12 个房间，配对差的符号统计是 5/3/4 与 9/1/2 这个量级，不足以做显著性推断；本实验只报告配对差与符号计数，不做检验。
- 单一严重度 severity=0.0、单一 visits=14、单一 k=6；没有扫 k 曲线，也没有扫遮挡/偏移档。
- 一个场景生成器、一个解码器（priorcost014 base）、一条精修链；oracle 只按真值类别 chair/bed/cab 与物体中心匹配，不是全局最优上界。
- 确认集 11700–11711 中 11704 曾被 010 联合输入实验当作输入暂存目录使用（未参与任何接触选择评价），如实披露；117xx 之外无完全未使用的 12 连号区段可选。
- 非 ok 行保留为 f1=0，会同时压低相应臂的均值；这与 026/030 的口径一致，没有做剔除。

## 复现命令

```
python -m analysis.layout.selectbalanced032 --rooms 11500-11511 --jobs 2 --stage dev --out output/layout-recon/select032
python -m analysis.layout.selectbalanced032 --rooms 11700-11711 --jobs 2 --stage confirm --out output/layout-recon/select032
python -m analysis.layout.selectbalanced032 --combine --out output/layout-recon/select032
```

单批在 jobs=2 下约 255–265 s。stage 文件 `stage-dev.json` / `stage-confirm.json` 各自带 protocol 与模块 SHA；`--combine` 先核对两批 protocol 与 SHA 一致再写 `select032.json`。

## 产物

- `analysis/layout/selectbalanced032.py`（唯一新增模块；SHA256 `af72bac4…a9a12c`）
- `output/layout-recon/select032/select032.json`（108 行 × 2 批 + 两批汇总 + 三组配对 + 门 + verdict）
- `output/layout-recon/select032/stage-dev.json`、`stage-confirm.json`
## 更正（2026-11-11，主会话复算）

`select032.json` 里的 `paired_bal_vs_plain` 块在取 `f1_a` 时用的是该 (room, arm) 最后一条随机行（某一 seed），不是三种子的均值，于是它给出的开发集 +0.1204、确认集 −0.0389 与两臂各自的均值不一致（开发集均值差 0.7136 − 0.6435 = +0.0701，确认集 0.7930 − 0.8052 = −0.0122）。主端点块 `paired_disperse_minus_random` 用的是种子均值，未受影响（+0.0503 / +0.0899 与两臂均值差一致）；`oracle` 块每房只有一行，也未受影响。

以 `analysis/layout/selectbalanced_paired032.py` 从 `stage-dev.json` / `stage-confirm.json` 的逐行数据重算，写入 `output/layout-recon/select032/paired_recomputed.json`：

| 配对 | dev | confirm |
| --- | --- | --- |
| `bal_disperse − bal_random` | +0.0503（5/3/4） | +0.0899（9/1/2） |
| `bal_random − plain_random` | +0.0700（7/3/2） | −0.0122（5/6/1） |
| `bal_oracle − bal_random` | −0.0330（6/4/2） | −0.0678（4/7/1） |

`select032.json` 原块保留不动，作为“当时写进去的东西”的记录；引用一律以 `paired_recomputed.json` 为准。这条更正不改变主结论：配额本身既不帮忙也不复现，收益来自同一配额下的空间分散。
