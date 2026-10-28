# 2026-10-29: independent echo-reference replay and evaluation readiness

The executed stationary-reference protocol passes independent raw-data replay.
An offline evaluator now preserves time uncertainty, requires explicit session
identity and keeps calibration visits separate from held-out visits. This moves
the joint phone/watch trajectory experiment toward an external-reference test;
it does not establish phone localization accuracy.

## Observed single-capture findings

One participant, one sealed approximately 60-second capture and one revisit pair:

| Check | Observation | Scope |
|---|---|---|
| Raw replay | 603 point-cloud frames; published per-frame fields reproduced | Same raw capture, not a new replication |
| Empty validation | Maximum novelty about 0.0244%, gate 0.1% | Held-out empty interval |
| Stationary availability | 40/40 unique candidates in each primary window | Repeated frames, not independent subjects |
| Primary ambiguity | Zero multi-candidate primary frames | Two split-candidate transition frames retained |
| Revisit difference | About 6.2 cm XY, 6.4 cm XYZ | Visible echo centroid, one pair; not an error bound |
| Grid-phase sensitivity | Radius-one XY range 6.09–6.31 cm across eight phases | Exploratory, primary unchanged |
| No dilation | All eight phases fail the empty-reference gate | Diagnostic control |

All 32 combinations of four Chebyshev radii and eight half-voxel grid phases were
reported. Radius-two and radius-three variants also pass the admission gates;
no best variant replaces the primary. Radius one means one 5 cm voxel per axis,
not a Euclidean 5 cm precision guarantee.

## Timing and dynamic limitations

The first cloud header is about 2.9 seconds older than bag receipt, while later
receive-minus-header observations are around 0.10 seconds. These are software
timestamp relationships. They do not establish hardware acquisition latency,
audible cue onset or phone/watch synchronization. The original G3 protocol uses
bag receive time, and its stationary result is preserved.

A conservative candidate-association prototype retains missing and ambiguous
frames and restarts after long absence. It has no independent dynamic-position
or identity ground truth. Neither within-window jitter nor one revisit difference
can be promoted to physical accuracy. A fixed common bias can give perfect
repeatability and arbitrarily wrong absolute coordinates.

## Next decisive test

Prepare one approximately two-minute joint phone/watch record with three visible
standing sites and returns. Independent software clock observations must precede
and follow capture. Fit A1/B1 on the evaluation side only; reserve C and later
returns. Report rigid nominal-scale and similarity-fitted echo discrepancies
separately. No door-start condition is imposed. Radar references remain outside
the attacker's input. Unknown physical timing and reference-object offsets remain
explicit; missing clock correspondence returns an unavailable joint score.

## Reproducibility and evidence boundary

The new source package has 32 synthetic/regression tests and a deterministic
synthetic holdout demo. Raw IMU/point clouds, per-frame spatial values, device
logs, identifiers and local authentication configuration are excluded. The
independent replay is a second implementation by the same computing agent,
not a separate participant, lab or human audit.

`formal_score=null`, true-room ranking remains null, physical localization and
cross-device hardware timing remain unvalidated. Single-person action-recognition
results and existing finite-family simulations are unchanged.
