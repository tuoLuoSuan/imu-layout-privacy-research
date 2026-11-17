# Training and regeneration

Use the frozen release for numerical reproduction of the primary table.
Retraining creates a new checkpoint; the shipped lock continues to identify
the published weights. Exact training protocols are exported as
`reproducibility/training-{teacher,k2,k6,refiner}.json`.

## Data and cache

```bash
python -m roomtrace download --training
python -m roomtrace cache \
  --manifest output/layout-recon/recovery076/main400/manifest.json \
  --out output/layout-recon/recovery076/main400/packed-g24.pt
```

The cache is generated from the explicit train/validation manifest rows.
Test and confirmation rows are excluded. The approximately 1.9 GiB local
tensor cache is regenerable and is not a release download. The release
contains the original synthetic observation/target JSONs and split manifest.

For a new geometric cohort, use the generator separately:

```bash
python -m analysis.layout.recovery076_generate \
  --out output/new-geometry --groups 50 --copies 2 --seed 99001 \
  --coverages 0.25,0.5,1.0 --budgets 0,2,6,10,14 --confirmation
```

This creates a new experiment, not the archived 98001 confirmation.

## Spatial residual

```bash
python tools/train_spatial083_archived.py \
  --steps 2000 --batch 4 --threads 12 --seed 8301 \
  --out output/retrained-spatial083
```

This is the archived training program: five convolutional blocks, zero output
initialization, AdamW learning rate 1e-3 and weight decay 1e-4, uniform budget
sampling and then a training-cell sample. The gradient-carrying target is
candidate cross-entropy. The logged selected-IoU term is a detached scalar;
it is not a differentiable IoU loss.

## Contact, graph and refinement stages

- Contact kernel: `python -m analysis.layout.train076 --help`.
- Candidate scorer: `python -m analysis.layout.train077 --help`, followed by `analysis.layout.calibrate077`.
- Candidate/graph caches: `python -m analysis.layout.build078 --help`.
- Graph ranking: `python -m analysis.layout.train078 --help`.
- Bounded refiner: `python tools/train_refine081.py --help`.

The K2 graph uses 96 complete-layout hypotheses, width 48, seed 7801 and
actual-contact specialization 2. Its candidate graph construction uses
80/64 candidates/beam; deployment uses 160/128. The K6 graph uses
160/128 construction, width 48, seed 7901; the selected operating point is
epoch 6 with residual strength 0.25. The shared refiner uses seed 8101,
2,000 updates, batch 32 and learning rate 1e-4. Each complete command and
source/checkpoint hash is retained in the corresponding protocol JSON.

The refiner's frozen coarse training views are included in the training
asset. The archived development evaluation rows used for checkpoint
selection are also provided there. Reusing confirmation labels for new
selection changes the protocol and requires a new held-out evaluation.

## Action recognition

```bash
python -m analysis.layout.action_model train \
  --rounds-root YOUR_LABELED_ROUNDS --output output/my-action-model.joblib
python -m roomtrace actions --session YOUR_EXPORTED_SESSION \
  --out output/action-timeline.json
```

The frozen phone RF has 400 trees and uses 340 overlapping windows from four
same-person development recordings. Its feature extraction and exact model
metadata are distributed; the private source recordings are not. The command
expects `SESSION/phone/{accelerometer,gyroscope}.csv` with
`sensor_timestamp_ns,x,y,z`, optionally `received_elapsed_realtime_ns`.
Odometry uses RoNIN under its authors' distribution terms; the existing
[`analysis/phone_ronin`](../../analysis/phone_ronin) adapter is retained.
