# Adapted pretrained RoNIN phone branch

This is the phone trajectory branch of the **joint phone-watch layout-leakage research**, and a phone-only ablation. It does not estimate a layout, validate body heading, or establish joint-device performance.

It reads existing native phone bundles using the unchanged phone-PDR reader. Author ResNet18 source and research-licensed weights are supplied separately; neither is bundled or automatically downloaded. Training is absent.

The fixed author architecture is `Sachini/ronin` commit `805b7f0f28bb164ce89ada9ac05a9470dbe3d715`, file `source/model_resnet1d.py`, SHA256 `24a4859272d2ee469ecaef192dddcaa287d40392de21f6c55b5b9b71c76d8e57`. Read the original code GPLv3 and the separate model license at DOI `10.20383/102.0543` before reuse. The audited checkpoint SHA256 is `5ae5c9e508f2dc9609c25b59d0e3dfd770ecbcde6920cbc5be3c6d9fed8a6346`.

From the repository root, with the existing NumPy and PyTorch CPU environment:

```text
python -m unittest discover -s analysis/phone_ronin/tests -v
python -m analysis.phone_ronin INPUT.zip --architecture AUTHOR_model_resnet1d.py --checkpoint CHECKPOINT.pt --checkpoint-sha256 CHECKPOINT_SHA256 --output output/phone-pdr/NEW_DIRECTORY
```

Paths above are command placeholders. Output must be a new strict descendant of `output/phone-pdr`; existing or linked output paths are refused. The reviewed architecture is checked before import; checkpoint bytes are checked before `torch.load(weights_only=True)`, with strict state matching. There is no unsafe-pickle fallback.

The adapter uses the existing estimated quaternion trace, not the device Euler yaw as human heading. It interpolates acceleration to native gyro times, rotates both signals, then linearly interpolates the world gyro XYZ and gravity-including acceleration XYZ to the model's 200 Hz input grid. This creates no additional observed bandwidth. Neither the Android game-rotation vector nor independently measured bias/scale calibration is available; this is explicitly an adaptation.

Each 200-frame window predicts a one-second average velocity with stride 10 frames. Its center is stored alongside the target interval start/end. Integration is trapezoidal between centers, with an arbitrary zero origin and no endpoint extrapolation. This differs from the author's visualization reconstruction. For future activity-budget prefixes, truncate native input independently and admit windows by their **end/availability**, not by their center; the current full-session CLI is not itself a prefix evaluator.

No room dimensions, turn angle, reference path or map is an inference input. Output JSON, model velocities, relative trajectory and model features preserve provenance and report unvalidated accuracy. Sliding windows are correlated.

Actual pilot, source receipts, joint-device plan and limitations are recorded in `docs/research/2026-10-18-joint-phone-watch-layout-leakage-route.md`. The 47-second pilot ran successfully and repeated identically, which establishes execution and reproducibility only.

## Arrival-aware budgets

The separate prefix entry point cuts native rows by both event and logged
callback receipt time **before** quaternion estimation and interpolation. It
requires `received_elapsed_realtime_ns`, assumes the documented Android clock
base relation, and records this assumption. Unknown/short or out-of-recording
budgets do not become zero-length successes. Run, with new output paths:

```text
python -m analysis.phone_ronin.prefix INPUT.zip --architecture AUTHOR_model_resnet1d.py --checkpoint CHECKPOINT.pt --checkpoint-sha256 CHECKPOINT_SHA256 --budget 10 --budget 22 --output output/phone-pdr/NEW_PREFIX_DIRECTORY
```

`path_end(T)` is the accumulated model path available at budget T, integrated
only between the centers of available windows. The last center is earlier than
T; no instantaneous endpoint at T is invented. A 200-sample window has a
0.995-second first-to-last sample span, while its author's velocity target
interval is one second. Both last input sample and target end are reported.
The original full-session files and CLI retain their original semantics.

The direct `evaluate_prefix(..., support_end_s=recorded_stop_s)` and `path_end`
APIs enforce support bounds. Without explicit stop metadata they now return
`unknown_support` and no estimate; array length is never substituted for a
recording stop. The CLI also has no fallback. Always pass the fixed recorded
stop during future-append experiments. Late rows are counted per sensor;
maximum effective gaps, `resampling_interpolation_used` and
`raw_unobserved_tail_s` are disclosed. Resampling interpolation does not claim
that a particular late-row hole was bridged. An effective gap over the existing
one-second limit returns `input_gap_exceeds_limit` with no estimate.

Optional `--yaw-ensemble 4` averages four rotations of the same licensed
network after rotating predicted velocities back. It is a C4 frame-consistency
control, not EqNIO, arbitrary-angle equivariance or a demonstrated accuracy
improvement. The default remains the original single prediction.

The separate `analysis/joint_privacy` package consumes saved prefixes and
predicted activity streams; references/regions enter its evaluation CLI only.
