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
