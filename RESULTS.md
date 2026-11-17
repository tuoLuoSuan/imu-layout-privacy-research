# Confirmed RoomTrace results

The current results are documented in [the evaluation protocol](docs/roomtrace/protocol.md).
The [machine-readable summary](reproducibility/confirmation-summary.json) contains
all endpoint values, paired confidence intervals and budget cells.

| Arm | Complete centers / 1,500 | Complete footprints / 1,500 | Instance F1 |
|---|---:|---:|---:|
| Geometry-only baseline | 254 | 10 | 0.433340 |
| Frozen contact-informed D | 366 | 142 | 0.533431 |
| RoomTrace | 412 | 154 | 0.580708 |

The cohort contains 50 independent condition groups and 100 synthetic layouts.
All 1,500 requests count, including 61 acquisition failures.
Earlier experimental iterations are historical results, not alternative versions
of this confirmation table. See Git history for their contemporary records.
