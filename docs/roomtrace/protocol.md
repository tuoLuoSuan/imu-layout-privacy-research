# Evaluation contract

The primary independent confirmation contains **50 condition groups, 100
layouts and 1,500 requested cells**: coverage targets 25/50/100% crossed with
contact budgets 0/2/6/10/14. There are 1,439 usable observations and 61
acquisition failures. Failures retain their place in every denominator and
score zero for every arm.

Category-preserving one-to-one matching defines:

- complete-room centers: every instance matches within 0.5 m and no unmatched prediction;
- complete-room footprints: every instance matches at IoU ≥0.5;
- instance F1 and footprint F1: per-request precision/recall harmonic means, averaged over requested cells.

Paired intervals use 4,000 resamples of the **50 condition groups**, preserving
both layouts and all repeated budgets within each sampled group.

| Method | Complete centers | Complete footprints | Instance F1 | Footprint F1 |
|---|---:|---:|---:|---:|
| Geometry-only baseline | 254/1500 (16.93%) | 10/1500 (0.67%) | 0.433340 | 0.253248 |
| Frozen D | 366/1500 (24.40%) | 142/1500 (9.47%) | 0.533431 | 0.415313 |
| RoomTrace | 412/1500 (27.47%) | 154/1500 (10.27%) | 0.580708 | 0.451867 |

RoomTrace vs geometry: +10.53 percentage points in complete centers
(group-bootstrap 95% interval [8.20, 12.87]); +0.1474 instance F1.
RoomTrace vs D: +46 centers, comprising 49 repairs and three losses.
Positive-contact outputs are unchanged relative to D.

The 10/40/60/75/90% extensions reuse the same groups and add 2,500 requests.
The zero-walk, zero-contact diagnostic adds 100 requested cells. These are
descriptive extensions of the original confirmation, not new independent cohorts.
`reproducibility/` contains the exact aggregate and surface tables; Release
assets provide the underlying observations, targets and prediction rows.

## Device evidence

The real dorm result uses **registered contacts and odometry exported from a
56.45 s recording**: 128 walking points, five contacts and four items. The
item errors are 0.145/0.146/0.090/0.189 m, mean 0.143 m. This is a registered
evidence replay with the archived real-record settings. It is not the
synthetic confirmation protocol or an evaluation of raw-stream end-to-end
generalization. Raw recordings, videos, participant/device identifiers and
signing material are outside the release.
