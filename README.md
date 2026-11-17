# RoomTrace: furniture layouts from a phone and a watch

RoomTrace turns activity-derived contact events and walking geometry into a
complete declared furniture layout. Walking supplies free-space evidence;
sitting, lying and cabinet activity constrain object geometry. A compact
528,064-parameter decoder combines contact kernels, a learned Walk-Space Prior,
joint layout search, graph ranking and bounded refinement.

**Independent confirmation:** 412/1,500 complete rooms (27.47%), compared with
254/1,500 (16.93%) for the geometry-only baseline. At full walking coverage the
rates are 76.0% vs 50.2%; with zero contacts at full coverage, 71% vs 15%.
The primary evaluation uses synthetic registered geometric evidence, 50 held-out
condition groups and failures retained in the denominator.

[Architecture](docs/roomtrace/architecture.md) · [Evaluation protocol](docs/roomtrace/protocol.md) ·
[Training](docs/roomtrace/training.md) · [Reproduction matrix](docs/roomtrace/reproduction-matrix.md)

## Reproduce the paper table

Python 3.11+ and a CPU are sufficient for the decoder. Run from this clone:

```bash
python -m pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e .
python -m roomtrace download
python -m roomtrace summarize --out output/confirmation-recomputed.json
python -m roomtrace verify --out output/inference-check.json
```

`download` retrieves SHA-256-pinned Release assets. `summarize` re-scores every
archived prediction against its target and recomputes the paired group-bootstrap
intervals. `verify` reruns frozen inference on one case from each of the 15
coverage/contact conditions and compares all predicted coordinates.

Dependencies are pinned to the measured environment. The tested package
versions are also listed in `reproducibility/requirements-tested.txt`;
using newer numerical libraries can change candidate ordering and coordinates.

Run all three decoders on the complete 1,500-request cohort:

```bash
python -m roomtrace evaluate --out output/my-confirmation --threads 4
```

The archived evaluation took about 13 minutes on a 12-core desktop CPU; actual
time depends on hardware. The shipped weights and route stay fixed.

## Recover a layout and compare geometry-only inference

```bash
python -m roomtrace predict --input examples/synthetic-zero-contacts.json \
  --baseline --out output/zero-contact-layout.json
python -m roomtrace predict --input examples/synthetic-six-contacts.json \
  --baseline --out output/six-contact-layout.json
```

Inputs contain a declared room outline, item categories/dimensions, registered
walking points, class-labeled contacts and the declared desk–chair flag.
No reference layout is passed to prediction. The route reads the actual number
of events: zero activates the spatial residual; positive-contact inputs retain
frozen D. [Input examples](examples) contain synthetic evidence.

## Activities and IMU acquisition

```bash
python -m roomtrace actions --session YOUR_EXPORTED_SESSION \
  --out output/activity-timeline.json
```

The [phone classifier](analysis/layout/action_model.py) and its frozen RF,
[feature extraction](analysis/layout/action_features.py),
[phone–watch collection suite](collection/imu-capture-suite), and
[RoNIN adapter](analysis/phone_ronin) connect inertial recording to activity and
registered movement evidence. Watch input is three-axis acceleration; phone
input includes acceleration and angular velocity. Device recording, activity
recognition, registration and layout decoding are documented as distinct stages.

The real-dorm registered replay recovers four items with 0.143 m mean center
error from 56.45 s of exported evidence. Raw recordings, video, device logs,
signing keys and third-party model weights are not distributed. The original
RoNIN model is obtained under its authors' terms from [Sachini/ronin](https://github.com/Sachini/ronin).

## Training and source layout

```bash
python -m roomtrace download --training
```

This additionally installs the original synthetic training observations and
refiner coarse views. [Training instructions](docs/roomtrace/training.md)
cover cache regeneration, candidate graphs, refiners and the archived spatial
trainer. Versioned checkpoint protocols accompany the code.

| Directory | Role |
|---|---|
| `roomtrace/` | Portable download, prediction, scoring and verification commands |
| `analysis/layout/recovery076*`–`recovery088*` | Exact scientific implementation; hash-bound files retain their bytes |
| `analysis/layout/action_*` | Phone activity features and classifier |
| `collection/`, `analysis/phone_ronin/` | Acquisition and odometry adapters |
| `reproducibility/` | Frozen route, asset hashes, training protocols and result tables |
| `docs/roomtrace/` | Method, evidence contract and regeneration instructions |

```bash
python -m unittest discover -s tests -v
python -m unittest analysis.layout.tests.test_spatial088 -v
```

The previous interactive showcase has been retired. Use the reproducible
commands and data manifests above. Existing third-party components retain
their original terms; this update does not assign a new license to them.
