# 局部 oracle：只评价连续已知的片段

2026-10-18。入口 `analysis.joint_privacy.local_oracle` 只消费已保存的 phone-only 输出与独立参考，不重新推理、不生成腕部概率。两条真实联合记录都没有通过它运行 oracle。

原 `evaluation` 将 coverage 中未列 walk 的时间按 nonwalk 处理。本模块在外层选择完整已知目标，逐片段调用原积分/评价函数；原模块、攻击入口、时钟公式和历史输出保持不变。

## 运行

在仓库根目录，用新的输出文件名：

```powershell
python -m analysis.joint_privacy.local_oracle ATTACK.json REFERENCE.json --output output/joint-privacy/NEW.json
```

输入是保存的、仅含 `phone` 变体的未门控基线，`gate_policy={"mode":"soft"}`。其他变体或迟滞策略拒绝，避免分段时重置门控状态。输出只能位于既有输出守卫允许的目录，独占新建；重复 JSON 键拒绝。

参考的完整 schema 示例（**纯合成**）：

```json
{
  "schema_version": 1,
  "reference_source_id": "SYNTHETIC-MANUAL",
  "time_resolution_s": 0.01,
  "timing_support_accepted": true,
  "interval_basis": "declared_common_interiors",
  "maximum_center_gap_s": 1.01,
  "intervals": [
    {"id": "still", "start_s": 0.0, "end_s": 3.0, "activity": "nonwalk"},
    {"id": "walk", "start_s": 3.0, "end_s": 6.0, "activity": "walk"}
  ],
  "excluded_intervals_s": [[2.8, 3.2]]
}
```

`intervals` 必须排序、不重叠、ID 唯一，activity 允许 `walk/nonwalk/unknown`；没有写到的范围同样未知。`excluded_intervals_s` 也须排序且不重叠，重叠轻拍护栏应先合并。

`start_s/end_s` 已经是传播时间与动作不确定度后的**共同内部**，不是名义口令或机械峰时间。`time_resolution_s` 只作来源披露，本模块不会再替调用者传播误差或缩窗。`timing_support_accepted` 是调用者的显式声明，不是工具对标签/时钟的认证；缺少外部证据时必须为 false，此时返回 `unverified_reference_timing`，没有 oracle。

## 纳入与积分规则

1. 校验每个模型目标完整位于原观察预算内，目标为 `[target_end-1,target_end]`，中心为 `target_end-.5`。不能筛中心后把伸出预算的窗带进来。
2. 整个目标须在一个已知 walk 或 nonwalk 共同内部中；接触未知/未覆盖范围不评分。与任一排除段有正长度交集的目标整窗排除，恰好相接而不重叠的边界不排除。
3. 只有原始索引连续、同一参考 ID、中心间隔不超过 `maximum_center_gap_s` 的目标才在同一片段。该阈值应在看结果前按模型步长约定；不是把缺失插值回来的许可证。
4. 每片段单独从 `[0,0]` 积分。至少两个中心才能给片段路程；单个完整目标会披露在 `singleton` 中，不伪造一个零距离成绩。路程仅覆盖首末中心之间，不覆盖目标支持的两个边缘半窗。
5. 输出逐片段 phone/oracle 模型路程、停走时间评价及原索引。所有原数据和观察预算保留，`global_trajectory=null`、`aggregate_path_m=null`；不跨缺口连接，不把分段的坐标原点解释为同一个地点。

这些是理想门控的诊断数，不是位置误差、腕部增益、动作分类精度或布局泄露。`joint_result=false`、`research_validated=false`、`clock_verified=false` 始终保留。

## 已验证的合成例子

六个中心 `.5,1.5,…,5.5 s`，速度均为 `[1,0] m/s`，nonwalk `[0,3]`、walk `[3,6]`，排除 `[2.8,3.2]`。保留索引 `[0,1,4,5]`，两个片段分别得到 phone/oracle 路程 `1/0 m` 和 `1/1 m`。排除点速度改成极大值也不影响片段结果。

对应产物在 `output/joint-privacy/2026-10-18-ds072-local-synthetic/`，证据在 `docs/reviews/evidence/2026-10-18-ds072-disposition/synthetic-exercise.json`。这验证软件的分段语义，不验证真实活动、对时或空间精度。
