# Joint phone/watch experiment harness

This is an offline readiness kit for **activity budget / spatial coverage versus unknown-layout leakage**. It is not a validated joint model. The phone branch reuses RoNIN; S5 contributes only measured three-axis acceleration. There is no trained activity classifier or actual paired room run yet.

DS059 update: attack input/output schema is now **version 2**. Both wrist-shift
and symmetric phone-shift prediction streams/provenance are required. Regenerate
synthetic examples with `demo`; old v1 evidence remains unchanged. The activity
helper now requires `clock_uncertainty_s`, and its circular separation in either
direction must be at least `ceil(uncertainty / feature_spacing) + 1` samples.

## Boundaries and entries

| Entry | Input / output | Evidence limit |
|---|---|---|
| `prepare` | Existing native phone ZIP + S5 TXT; optional exact-SHA-bound clock contract → native diagnostics and trailing motion features | Reuses frozen read-only loaders, CRC/manifest/count checks. No probability generation; unknown clocks return unknown pairing |
| `activity.paired_activity_probabilities` | Aligned phone/wrist feature matrices + target/availability times + budget + supplied trained predictor | Truncates before inference/mismatch; phone fixed, wrist circularly shifted before the same joint classifier. Does not train a model |
| `attack` | Strict JSON schema: phone velocity windows + phone/joint/shifted-wrist predicted probabilities, identity/provenance, checked clocks | No region/room/radar/reference keys. Same policy for all gates. Missing real models cannot become a joint success |
| `from_prefix` | One saved validated RoNIN prefix → phone-only attack output | Allows evaluation-only oracle diagnosis before activity training, while reporting joint clocks/probabilities missing |
| `space` | Modeled XY polylines → bounded distance/inverse-distance raster | Small Walk2Map-inspired representation, not its model or free-space/wall inference. Cell size is a representation parameter, not measured accuracy |
| `evaluation` | Attack output + independent reference JSON → temporal and region-access metrics + oracle diagnosis | Reference-only entry; independent coordinate alignment required for region metrics; no wall error fabricated |
| `demo` | Explicit synthetic fixtures → all software paths | Toy probabilities, clocks, paths and references are synthetic; no research performance evidence |

Tests scan attack-side module imports and reject unknown/nested reference fields. This is a concrete software boundary, not proof that external labels/models/metadata can never be forged or contaminated. Held-out provenance and independent annotations still require experimental discipline.

## Reproduce on this computer

From the repository root, use the existing Python/NumPy/PyTorch environment. Replace `NEW_*` with unused paths under `output/joint-privacy`; originals and existing output are refused as write targets.

```text
python -m unittest discover -s analysis/joint_privacy/tests -v
python -m analysis.joint_privacy.demo --output output/joint-privacy/NEW_SYNTHETIC
python -m analysis.joint_privacy.attack output/joint-privacy/NEW_SYNTHETIC/synthetic-attack-input.json --output output/joint-privacy/NEW_ATTACK.json
python -m analysis.joint_privacy.evaluation output/joint-privacy/NEW_ATTACK.json output/joint-privacy/NEW_SYNTHETIC/synthetic-eval-reference.json --output output/joint-privacy/NEW_EVAL.json
python -m analysis.joint_privacy.space output/joint-privacy/NEW_ATTACK.json --output output/joint-privacy/NEW_FIELD.json
```

To reuse actual saved phone prefixes without inventing wrist probabilities:

```text
python -m analysis.joint_privacy.from_prefix output/phone-pdr/2026-10-18-ds059-ready-178450f0 --index 2 --pair-id unpaired-old-phone --output output/joint-privacy/NEW_PHONE_ONLY.json
```

This produces `unverified_clock_pairing` plus a **phone-only** variant, not a joint result. The old phone walk and old watch ten-minute record are not a verified pair. Loader smoke check:

```text
python -m analysis.joint_privacy.prepare --phone data/raw/phone/pdr_corridor_right_001/imu_8c6bea5c-26f0-4307-960b-c05fbd778dbc.zip --watch data/raw/watch_s5/20261017-research-ready-full10min-usb/imu_s5_58c3188da12a30e2.txt --budget 22 --output output/joint-privacy/NEW_UNPAIRED.json
```

## Time and model contracts

The clock contract keys are `phone_id`, `watch_id` (exact original SHA256s), `paired_session_id`, `mode`, two `anchors`, independent `checks`, `available_s`, `valid_until_s`, `drift_bound_ppm`, `max_uncertainty_s`. Each observation has `watch_epoch_ms`, `phone_s`, `uncertainty_s`. Two anchors fit an affine relation; endpoint uncertainty is propagated through interpolation/extrapolation, with additional declared drift and check residual. Unverified drift bounds remain an experimental assumption. Calibration cannot be used before its observations are available. No first-row or equal-rate alignment fallback exists.

Shared events used for clock calibration are cooperative calibration; they do not establish an attacker with no user cooperation. If only a post-task anchor validates/changes a map, it cannot silently become pre-budget knowledge. Preserve both conditions separately. A clock step, excessive uncertainty, incomplete overlap or hidden/gapped watch features blocks that condition.

`observation_start_s` is explicit in the attack schema. Only phone target intervals
fully inside that task interval are integrated, and every variant is rebased at
its first supported task center. Saved-prefix bridging accepts `--task-start`.
Pre-task calibration may initialize attitude/clock as a declared common context;
it is not counted as task motion or extra task exposure. Reference region events
start at the task origin (include its initial region there), not during calibration.

Phone data are validated m/s² including gravity and rad/s; wrist scale is unvalidated. Trailing 1s norm CV/range/difference features are dimensionless. No fake wrist gyroscope or rotation matrix is synthesized. Feature rates remain separate. Prepending calibration changes the task origin; exposure budgets are `task_start_s + duration`, not time since an arbitrary first sample.

Attack input schema keys are listed in `attack.KEYS`; `demo.fixture()` is a complete executable synthetic schema example. Real probability provenance must identify the exact pair, trained model SHA256, training-data ID and held-out split ID. Phone and joint models use matched labels/splits; the shifted-wrist stream must use the same joint model with phone features unchanged. No blank or synthetic real probability model is accepted. The helper predictor interface may later wrap XGBoost's `predict_proba` after the oracle mechanism gate passes.

Controls include ungated phone, phone activity gate, joint gate, matched-mean constant, fixed-seed shuffled gate, within-prefix shifted final gate, and **wrist-feature shift before joint inference**. The last is the primary mismatch; shifting final scores is only additional diagnosis. All negative controls use only the admitted prefix, although permutation/shift are offline diagnostic controls rather than causal per-window deployments.

The gate policy is either `{"mode":"soft"}` or the same explicit hysteresis `on`/`off` values for learned and oracle paths. Lower path length is never an improvement by itself. Evaluation reports reference nonwalk model distance, walking model-distance retention, target-window-weighted gate suppression and region false/missed visits.

`probability_time_mode` defaults explicitly to `prefix_retrospective`: inputs
available by observation budget T may be used to assess earlier model windows.
It is not a claim that a score was known at that earlier instant. Set this field,
or the attack CLI `--probability-time-mode`, to `target_time` to additionally
require probability `available_s <= target_end_s`; missing scores then give
incomplete coverage rather than lookahead. Actual compute latency is unmeasured.

The two mismatch provenance records include `feature_stride_s`; it cannot exceed
the admitted probability grid's smallest spacing. Both use the same joint model.
`prepare --watch-max-gap 0.5` selects the preregistered pilot feature-gap policy
and records it. Default stays 0.25. This changes only feature eligibility, not
raw integrity or the phone integration gap limit. Raw and model tails are named
`raw_unobserved_tail_s` and `model_unscored_tail_s` respectively.

## Reference contract and remaining experimental work

Reference JSON keys: `schema_version`, `reference_source_id`, positive `time_resolution_s`, `reference_coverage_s`, ordered nonoverlapping `walk_intervals_s`, timed `region_events`, rectangular measured `regions`, optional independent `alignment`. The latter contains `rotation_rad`, `translation_xy_m`, `reference_source_id`, `fit_used_this_test_output:false`. A floorplan is evaluation data, never attack input. Alignment cannot be tuned to the test prediction error. Missing alignment yields unknown region scores but permits temporal mechanism diagnostics.

Oracle labels may use manual observations and are **evaluation-only privileged diagnostics**, not an attack result. Region scoring stops at the last supported model center and reports its lag from the observation budget; it does not extrapolate to T. Region sets use sampled modeled points, not an invented continuous human trajectory. An inverse-distance image is not ground truth or a complete room.

Next real run requires a room sketch/measurements, checked static geometry if claiming geometry, one explicitly paired task, timing uncertainty, coarse independent stop/walk/region events and completion counts. After the oracle check, train small matched activity models only if useful; split by whole session/date/room, never randomly by overlapping windows. Four 120s tasks, other rooms and real layout changes follow the first-pair acceptance; they have not been collected.
