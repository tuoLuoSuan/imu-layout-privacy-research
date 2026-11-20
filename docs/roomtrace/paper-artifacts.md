# Reproduce the paper panels and historical controls

Start with the [pinned environment and download instructions](../../README.md#reproduce-the-paper-table).

```bash
python -m roomtrace download
python -m tools.reproduce_paper_figures --out output/paper-panels
python -m tools.reproduce_historical_controls --out output/historical-controls.json
```

The figure command draws eight panels from the archived values in a compact layout. Give each run a new output directory.

## Figure and table sources

| Panel or table | Data and reproduction entry point |
| --- | --- |
| Fig. 1, architecture | [Decoder stages, shapes, scoring and routing](architecture.md). The submitted overview also uses measured waveform, registered-room drawings and render assets from the paper workspace. |
| Fig. 2, actions and constraints | [Action features](../../analysis/layout/action_features.py), [classifier](../../analysis/layout/action_model.py), [contact kernels](../../analysis/layout/recovery076_model.py) and [activity summary values](../../reproducibility/activity-development.csv). The measured signal strip requires the archived recording extract. |
| Fig. 3, position F1 | [Quarter-grid values](../../reproducibility/quarter-f1-surface.csv), [100% slice intervals](../../reproducibility/full-coverage-ci059.json) and the figure command above. The 0% marker is measured at zero contacts. |
| Fig. 4, paired layouts | [Frozen selected IDs](../../reproducibility/case-selection.json) and released primary confirmation targets, observations and predictions. |
| Fig. 5, dorm error bars | [Per-item errors](../../reproducibility/real-dorm-errors.csv) and [the registered dorm input](../../examples/registered-dorm/). |
| Supplement, coverage surfaces | [Complete-room center](../../reproducibility/quarter-whole_room-surface.csv), [complete footprint](../../reproducibility/quarter-whole_footprint-surface.csv) and [eight-level position F1](../../reproducibility/dense-eight-f1-surface.csv). |
| Supplement, class checks | [Localization by class and coverage](../../reproducibility/class-localisation-by-coverage058.csv) and [activity classification summary](../../reproducibility/activity-development.csv). |
| Supplement, spatial representations | [Distance field, mask and contact heatmaps](../../analysis/layout/recovery083_fields.py), [frozen spatial score](../../analysis/layout/recovery083_runtime.py), and bundled synthetic observations under [examples](../../examples/). Submitted dorm panels use the original registered observation. |
| Main confirmation and components | `roomtrace summarize` for the confirmation table and [archived development component increments](../../reproducibility/component-increments059.json). |

## Historical placement controls

The first study held walking coverage at 100% and varied where the 14 contacts occurred. Repeated contacts recovered **3,978 of 10,000** rooms. Dispersed contacts recovered **6,470**. The script computes the paired difference from [the four archived outcome counts](../../analysis/layout/expansion009-results.json) and prints the recorded bootstrap interval.

The second study generated a pair of synthetic phone–watch recordings for each of 64 rooms. Repeated acquisition recovered 30 rooms and dispersed acquisition recovered 48. From the [128 archived scores](../../reproducibility/paired-synthetic-acquisition-scores.json), the script recalculates the exact McNemar test, paired bootstrap interval and the 52-pair comparison after excluding earlier diagnostic rooms. The search-budget failure stays in its original pair.

The historical from-input scripts are [expansion10000](../../analysis/layout/expansion10000.py) and [placement033](../../analysis/layout/placement033.py). The latter used rooms 11700–11763, 14 visits, sensor severity 0 and prefix noise streams:

```bash
python -m analysis.layout.placement033 --ids 11700-11763 --visits 14 --severity 0 --streams prefix --workers 4 --out output/historical-acquisition-rerun
```

To rerun inference from the historical inputs, you need the native scenes, wrist metadata, trained ensemble and displacement checkpoint listed in [exp_bias014](../../analysis/layout/exp_bias014.py). The 10,000-room study also needs its original scene and evaluation archives. Use the score reproduction commands at the top of this page with the public release files.

## Registered room replay

The [registered dorm example](../../examples/registered-dorm/) provides the declared outline and inventory, 128 walking points, five contact positions and four reference footprints. The example uses the archived five-contact route with its rule settings, as implemented in [replay_registered_layout](../../tools/replay_registered_layout.py).

```bash
python -m tools.replay_registered_layout --observation examples/registered-dorm/observation.json --reference examples/registered-dorm/reference.json --out output/registered-room.json
```

The replay places all four centers within 0.5 m, with a mean error of 0.143 m. The decoder reads the observation. The reference maps item IDs to `[x0, y0, x1, y1]` boxes for scoring. See the [capture guide](capture.md) to record a new session and the [synthetic examples](../../examples/) for the decoder's input schema.
