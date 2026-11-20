# Reproduce the paper panels and historical controls

Start with the [pinned environment and download instructions](../../README.md#reproduce-the-paper-table).

```bash
python -m roomtrace download
python -m tools.reproduce_paper_figures --out output/paper-panels
python -m tools.reproduce_historical_controls --out output/historical-controls.json
```

The figure command redraws the public panels with the archived values. It uses a compact presentation layout. Use a new output directory for each figure run.

## Figure and table sources

| Panel or table | Data and reproduction entry point |
| --- | --- |
| Fig. 1, architecture | [Decoder stages, shapes, scoring and routing](architecture.md). The submitted overview also uses measured waveform, registered-room drawings and render assets from the paper workspace. |
| Fig. 2, actions and constraints | [Action features](../../analysis/layout/action_features.py), [classifier](../../analysis/layout/action_model.py), [contact kernels](../../analysis/layout/recovery076_model.py) and [activity summary values](../../reproducibility/activity-development.csv). The measured signal strip requires the archived recording extract. |
| Fig. 3, position F1 | [Quarter-grid values](../../reproducibility/quarter-f1-surface.csv), [100% slice intervals](../../reproducibility/full-coverage-ci059.json) and the figure command above. The 0% marker is measured at zero contacts. |
| Fig. 4, paired layouts | [Frozen selected IDs](../../reproducibility/case-selection.json) and released primary confirmation targets, observations and predictions. |
| Fig. 5, dorm error bars | [Reported per-item values](../../reproducibility/real-dorm-errors.csv). The registered replay below regenerates the predictions when the observation is available. |
| Supplement, coverage surfaces | [Complete-room center](../../reproducibility/quarter-whole_room-surface.csv), [complete footprint](../../reproducibility/quarter-whole_footprint-surface.csv) and [eight-level position F1](../../reproducibility/dense-eight-f1-surface.csv). |
| Supplement, class checks | [Localization by class and coverage](../../reproducibility/class-localisation-by-coverage058.csv) and [activity classification summary](../../reproducibility/activity-development.csv). |
| Supplement, spatial representations | [Distance field, mask and contact heatmaps](../../analysis/layout/recovery083_fields.py), [frozen spatial score](../../analysis/layout/recovery083_runtime.py), and bundled synthetic observations under [examples](../../examples/). Submitted dorm panels use the original registered observation. |
| Main confirmation and components | `roomtrace summarize` for the confirmation table and [archived development component increments](../../reproducibility/component-increments059.json). |

## Historical placement controls

The fixed-walking study compares repeated and dispersed contacts at full coverage with 14 contacts. Its [archived contingency counts](../../analysis/layout/expansion009-results.json) give **3,978 vs 6,470 of 10,000**. The report computes the paired difference from the four outcome counts and displays the archived room-bootstrap interval.

The paired acquisition study compares two protocols on synthetic phone–watch streams. The [128 arm-level scores](../../reproducibility/paired-synthetic-acquisition-scores.json) reproduce **30 vs 48 of 64**, exact McNemar inference, the paired bootstrap interval and the 52-pair analysis excluding earlier diagnostic rooms. The archive includes the search-budget failure in its original pair.

The historical from-input scripts are [expansion10000](../../analysis/layout/expansion10000.py) and [placement033](../../analysis/layout/placement033.py). The latter used rooms 11700–11763, 14 visits, sensor severity 0 and prefix noise streams:

```bash
python -m analysis.layout.placement033 --ids 11700-11763 --visits 14 --severity 0 --streams prefix --workers 4 --out output/historical-acquisition-rerun
```

This historical inference command additionally requires the exact native-scene JSONs, wrist metadata and trained ensemble, and displacement checkpoint referenced by [exp_bias014](../../analysis/layout/exp_bias014.py). The 10,000-room generator and evaluator also require their original staged scene/evaluation archives. Those legacy inputs are outside the current release. The score reproduction commands above run with the published files.

## Registered room replay

The [registered dorm example](../../examples/registered-dorm/) provides the declared outline and inventory, 128 walking points, five contact positions and four reference footprints. The example uses the archived five-contact route with its rule settings, as implemented in [replay_registered_layout](../../tools/replay_registered_layout.py).

```bash
python -m tools.replay_registered_layout --observation examples/registered-dorm/observation.json --reference examples/registered-dorm/reference.json --out output/registered-room.json
```

The official replay returns four center matches within 0.5 m and a mean center error rounded to 0.143 m. The reference file maps item IDs to axis-aligned `[x0, y0, x1, y1]` footprints. Supply it to report matched errors. The decoder takes its input from the observation alone. Use [the capture guide](capture.md) for collecting a phone–watch session and [the public synthetic examples](../../examples/) for the main decoder input schema.
