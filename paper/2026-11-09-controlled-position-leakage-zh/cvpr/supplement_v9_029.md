: Table S1. Whole-room recovery on 1,000 development rooms at four operating points of the layer-1 decoder. Every row uses a 0.5 m Euclidean centre tolerance. Contacts are total interactions per room. The declared desk-wall prior is active.

| Operating point | Centre tolerance (m) | Contacts | Whole-room (%) | Wilson 95% |
|---|---|---|---|---|
| 95%/14 | 0.50 | 14 | 64.7 | 61.7-67.6 |
| 100%/8 | 0.50 | 8 | 70.0 | 67.1-72.8 |
| 100%/14 | 0.50 | 14 | 82.6 | 80.1-84.8 |
| 100%/20 | 0.50 | 20 | 85.1 | 82.8-87.2 |

: Table S2. Prior-only control on the same 32 confirmation records used for the device chain. The prior-only arm receives the room outline, start and inventory only, with no signal, pose, walk point, contact, heading or event association. Both rows use the same directional decoder, candidate cap of 128 and support weight of 0.3, so the comparison isolates the contribution of the inertial evidence rather than the quality of the side information. The paired difference is 17 rooms, with a paired room-bootstrap 95% interval of [34.4, 68.8] percentage points and exact McNemar p = 1.5e-5.

| Arm | Input | Whole-room | Mean instance F1 |
|---|---|---|---|
| Declared priors only | outline, start, inventory | 0/32 | 0.0915 |
| Raw joint input | phone and wrist streams | 17/32 | 0.7275 |

: Table S3. The prior-only control repeated on a second independent 32-room set (11200-11231). Its comparator is that set's own stored raw arm, frozen before this control was run; the two sets are reported separately and are not pooled. Configuration is identical to Table S2.

| Arm | Input | Whole-room | Mean instance F1 |
|---|---|---|---|
| Declared priors only | outline, start, inventory | 0/32 | 0.0793 |
| Stored raw arm | phone and wrist streams | 21/32 | 0.8013 |

: Table S4. Declared-inventory control on the twelve replicated rooms at fourteen visits and severity zero: the front end, refiners, candidate cap of 128 and support weight of 0.3 are unchanged and only the declared list is edited. Whole-room recovery is zero in both edited arms by construction, because the reference still contains the missing instance, so the informative column is the share of declared items that are placed. Proposal conflicts are rooms where the solver returns no placement at all.

| Declared list | Items | Whole-room | Mean F1 | Items placed | Proposal conflicts |
|---|---|---|---|---|---|
| Correct | 5 | 7/12 | 0.8135 | 4.58/5 | 1/12 |
| No cabinet | 4 | 0/12 | 0.1965 | 1.08/4 | 9/12 |
| One chair | 4 | 0/12 | 0.4349 | 2.33/4 | 5/12 |
