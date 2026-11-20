# Evaluation contract

The held-out confirmation uses 50 condition groups with two layouts each.
We test every layout at 25%, 50% and 100% walking coverage, with contact
budgets of 0, 2, 6, 10 and 14. Of the 1,500 requests, 1,439 have usable
observations. The other 61 stay in the denominator and score zero for each
method.

We match predictions to references one-to-one within each furniture class.

- A complete-room center success requires every item to match within 0.5 m and leaves no extra prediction.
- A complete-room footprint success requires every item to match at IoU ≥0.5.
- For instance and footprint F1, we compute F1 in each request and average across all requests.

Paired intervals use 4,000 resamples of the **50 condition groups**, preserving
both layouts and all repeated budgets within each sampled group.

| Method | Complete centers | Complete footprints | Instance F1 | Footprint F1 |
|---|---:|---:|---:|---:|
| Geometry-only baseline | 254/1500 (16.93%) | 10/1500 (0.67%) | 0.433340 | 0.253248 |
| Frozen D | 366/1500 (24.40%) | 142/1500 (9.47%) | 0.533431 | 0.415313 |
| RoomTrace | 412/1500 (27.47%) | 154/1500 (10.27%) | 0.580708 | 0.451867 |

RoomTrace gains 10.53 percentage points in complete centers over the
geometry-only baseline (95% group-bootstrap interval [8.20, 12.87]) and
0.1474 in instance F1. It gains 46 complete-center successes over D, with
49 successes gained and three lost. With positive contact counts, it returns
the same outputs as D.

The 10%, 40%, 60%, 75% and 90% extension adds 2,500 requests from the same
groups. The zero-walk, zero-contact check adds 100. Both describe the same
cohort at additional budgets. Find the aggregate and surface tables under
`reproducibility/` and the observations, reference boxes and predictions
in the release archives.

## Device evidence

The [dorm replay](../../examples/registered-dorm/) starts with evidence
exported from a 56.45 s recording. The decoder places four items using
128 registered walking points and five contacts. Center errors for the bed,
desk, cabinet and chair are 0.145, 0.146, 0.090 and 0.189 m, with a mean of
0.143 m. This test measures decoding from registered evidence in one room.
