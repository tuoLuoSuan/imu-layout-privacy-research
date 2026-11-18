# What can be reproduced from this release

| Paper component | Released material | Verification route |
|---|---|---|
| Primary 1,500-request table | All synthetic observations/targets, three arms' prediction rows, frozen models and evaluator | `roomtrace summarize`, `verify`, `evaluate` |
| Coverage surfaces | Primary and dense/zero-walk extension observations, predictions and CSV source tables | Re-score each released manifest/row pair and build the [figure panels](paper-artifacts.md) |
| Contact vs spatial architecture | Exact hash-bound scientific source and weights | Model loading and route tests |
| Spatial training | Original training JSONs, split manifest, archived trainer and frozen parent | Regenerate tensor cache, train a new run |
| Graph/refiner stages | Trainers, graph builder, protocols, coarse views and weights | Run the linked per-stage commands |
| Action classification | Feature extraction, training/inference code, frozen RF and metadata | Run on an exported phone session; original participant recordings remain local |
| Phone–watch capture and export | Original Android APK, Xiaomi Watch S5 RPK, AstroBox bridge ABP, matching sources and validator | [Install the three components and validate your own recording](capture.md) |
| Registered real dorm | Item-error source table and a registered replay command | Redraw the error panel. The replay command accepts a locally available registered observation and optional reference file. |
| Historical geometry and raw-stream controls | Fixed-walking outcome counts, 64 acquisition pairs and archived experiment code | [Recompute the reported comparisons](paper-artifacts.md) and see the input requirements for inference reruns |

The table distinguishes score reproduction, frozen inference and retraining.
The public release does not turn synthetic evidence into raw phone/watch
recordings, and the desktop runtime does not become a phone benchmark.

The retired interactive showcase is removed. Reproducibility uses command-line
entry points, versioned source, model hashes and data manifests.
