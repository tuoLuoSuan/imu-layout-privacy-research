# 独立参考的时间包络与时钟计划

2026-10-18。`reference_timing.py` 是评价侧的离线工具，不读取 IMU、预测轨迹或房间尺寸。它复用 `inputs.fit_clock` 与独占输出守卫，不认证原件身份、物理误差界或动作标签，也不生成可直接冒充真值的 `reference.json`。

## 时间包络

从仓库根运行，输出必须是 `output/joint-privacy/` 下尚不存在的文件：

```text
python -m analysis.joint_privacy.reference_timing map docs/reviews/evidence/2026-10-18-ds067-offline-ready/inputs/existing-local-timing.json --output output/joint-privacy/NEW_LOCAL_TIMING.json
```

完整输入示例：

```json
{
  "schema_version": 1,
  "time_unit": "seconds",
  "source_id": "SYNTHETIC-audio",
  "target_id": "SYNTHETIC-phone",
  "anchors": [
    {"source_s": 10, "source_error_s": 0, "target_s": 0},
    {"source_s": 110, "source_error_s": 0, "target_s": 100}
  ],
  "target_support_s": [0, 100],
  "target_window_s": 1,
  "intervals": [
    {"id": "walk-A", "activity": "walk", "start_s": 30, "end_s": 50,
     "start_error_s": 1, "end_error_s": 1}
  ]
}
```

两锚点定义仿射映射 `target = target0 + (source-source0)/(source1-source0)*(target1-target0)`。源锚点各有对称误差区间；目标锚点值是调用者提供的确切轴坐标，其对应关系仍待实验验证。两个源锚点误差区间必须严格有序、不重叠。每个动作起止也有独立误差区间，工具在角点传播边界极值。

输入严格按上述键集合；`activity` 只接受 `walk/nonwalk/unknown`。拒绝非有限值、布尔时间、重复 ID、未知键、重复 JSON 键；单位必须显式为秒。`target_support_s` 必须来自可信录制元数据，不能靠追加合成数组扩大。`source_id/target_id` 即便填 SHA，也仅是声明，调用者仍须核原件。

输出区分三个量：

- `start/end_phone_envelope_s`：各边界的范围；字段沿用手机轴命名。
- `correlated_duration_range_s`：起止共用同一个时钟映射时的时长范围。
- `common_interior_s`：所有允许映射都同意的内部交集。这是一种保守纳窗政策，交集不足不能推出所有不确定性评价都不可能。

只有活动已知、边界顺序确定、完整包络在录制支持内，且交集至少容纳 `target_window_s`，才给出 `admissible_target_end_s`。这仍不证明实际模型网格上存在目标窗，调用者必须检查每个完整 `[target_end-1,target_end]`。`unknown` 不变静止，超支持不静默裁剪，分离区间不代表中间也有连续标签。

首条真实回读复现交集 **0.7882347988594773 s**，状态 `insufficient_common_support`。本工具没有改变旧标签或据此生成 oracle。

## 手机与手表的时钟计划

```text
python -m analysis.joint_privacy.reference_timing clock-plan docs/reviews/evidence/2026-10-18-ds067-offline-ready/inputs/synthetic-wide-pre-task-clock-plan.json --output output/joint-privacy/NEW_CLOCK_PLAN.json
```

顶层严格为 `schema_version:1`、`clock_contract`、`budgets_s`、`threshold_s`。内部合同保持既有格式：两锚点和至少一个独立检查、双端身份、配对 ID、`available_s/valid_until_s/drift_bound_ppm/max_uncertainty_s`。每条观测为 `watch_epoch_ms/phone_s/uncertainty_s`。

逐预算检查校准是否已可用、是否仍在声明支持内、合同不确定度与严格阈值。此计划入口用 **uncertainty < threshold**；恰等于 0.5 s 也拒绝。未修改既有 `ClockMap.require_budget` 的语义。任务后才可用的校准不得进入早期因果预算。

5/45/85 s 三事件、95—155 s 任务的合成计划，在每锚点 ±0.15 s、100 ppm、检查残差 0.05 s 假设下，末端为 **0.4695 s**。这是数学预检，不是设备时钟验收；若这些界缺乏依据，只能报告条件性结果和敏感性，不能写外部验证通过。

两个入口均固定 `clock_verified:false`、`research_validated:false`，输出独占新建。攻击入口没有导入本模块。

## 复跑与评价边界

```text
python -m unittest discover -s analysis/joint_privacy/tests -p test_reference_timing.py -v
python -m unittest discover -s analysis/joint_privacy/tests -p test_reference_readiness_eval.py -v
```

证据 `docs/reviews/evidence/2026-10-18-ds067-offline-ready/` 保存首次红测、真实包络回读、合成全链与解析 oracle。解析样例的 gate `[0,.5,1,.5]`、路程 1.75、步行模型距离保留 0.75 都是合成数值，不是实测收益。

既有评价器的 `reference_coverage_s` 表示连续已知标签覆盖；其中未列为 walk 的时间会作为 nonwalk。不得把未知空档塞进该覆盖范围。若实际参考有缺口，不生成全程参考；仅在独立可核的连续局部段评价，或保留 `reference_support_incomplete`。当前工具不会自动切模型流、拼局部轨迹或填补未知。
