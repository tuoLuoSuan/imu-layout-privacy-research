# RoomTrace: furniture layouts from a phone and a watch

[简体中文](README.zh-CN.md) · **English**

How much of a room can you recover from a walk and a few furniture contacts?
RoomTrace starts with a known room outline and a list of furniture sizes. It
uses registered walking points and contacts such as sitting, lying down, or
opening a cabinet to place one box per item.

On the held-out synthetic evaluation, RoomTrace places every furniture center
within 0.5 m in **412 of 1,500 requests (27.47%)**. The geometry-only baseline
gets 254 (16.93%). At full walking coverage the rates are 76.0% and 50.2%.
At full coverage with zero contacts, they are 71% and 15%. These results use
50 held-out condition groups and count failed generations as zero.

[Reproduce the table](#reproduce-the-paper-table) ·
[Replay the real dorm](examples/registered-dorm/) ·
[Record your own session](docs/roomtrace/capture.md)

Device downloads · [Android APK](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/download/joint-watch-v0.2.23/IMU-Capture-0.2.4.apk) ·
[S5 watch RPK](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/download/joint-watch-v0.2.23/org.imuresearch.s5joint.release.0.2.23.rpk) ·
[AstroBox bridge ABP](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/download/joint-watch-v0.2.23/IMU-Bridge-0.2.5-clock-discard.abp) ·
[Installation and export](docs/roomtrace/capture.md)

## Reproduce the paper table

This path runs on a computer with Python 3.11+ and an x86-64 CPU with AVX2.
Run these commands from the repository root.

```bash
python -m pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e .
python -m roomtrace download
python -m roomtrace summarize --out output/confirmation-recomputed.json
python -m roomtrace verify --out output/inference-check.json
```

`download` checks release assets against their SHA-256 hashes. `summarize`
scores the archived predictions and recalculates the paired confidence
intervals. `verify` runs frozen inference on one case from each of the 15
coverage and contact conditions and compares the predicted coordinates.

Use the [tested package versions](reproducibility/requirements-tested.txt) for
coordinate comparisons. Different numerical kernels can break close ties
in different orders. The CLI selects the reference AVX2/oneDNN/MKL kernels
before loading the libraries and honors explicit environment settings.

Run all three decoders on the complete 1,500-request cohort:

```bash
python -m roomtrace evaluate --out output/my-confirmation --threads 4
```

The archived run took about 13 minutes on a 12-core desktop CPU.

## Recover a layout and compare geometry-only inference

```bash
python -m roomtrace predict --input examples/synthetic-zero-contacts.json \
  --baseline --out output/zero-contact-layout.json
python -m roomtrace predict --input examples/synthetic-six-contacts.json \
  --baseline --out output/six-contact-layout.json
```

Each example gives the decoder a room outline, furniture categories and
sizes, registered walking points, class-labeled contacts and a desk–chair flag.
Ground-truth boxes are used for scoring. The decoder counts the supplied
events. With zero contacts it uses the learned spatial residual. With any
contacts it uses frozen D. The [decoder guide](docs/roomtrace/architecture.md)
walks through the 528,064-parameter system.

## Activities and IMU acquisition

The [capture guide](docs/roomtrace/capture.md) shows how to record a session,
check the exported ZIP and extract the phone files for action recognition.

```bash
python -m roomtrace actions --session YOUR_EXPORTED_SESSION \
  --out output/activity-timeline.json
```

The [phone classifier](analysis/layout/action_model.py) uses a frozen random
forest and [features](analysis/layout/action_features.py) from acceleration
and angular velocity. The watch records three-axis acceleration. The
[RoNIN adapter](analysis/phone_ronin) supports phone odometry. To decode a
layout, provide walking points and contacts already registered to the room.

The [real-dorm registered replay](examples/registered-dorm/) recovers four items
with 0.143 m mean center error from evidence exported from a 56.45 s session.
The public example provides room-frame geometry, contacts and walking points.
Get RoNIN under its authors' terms from [Sachini/ronin](https://github.com/Sachini/ronin).

## Training and source layout

```bash
python -m roomtrace download --training
```

This adds the synthetic training observations and the refiner's coarse
layouts. The [training guide](docs/roomtrace/training.md) covers cache
generation, candidate graphs, refiners and the archived spatial trainer.

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

For experiment definitions and figure sources, see the [evaluation protocol](docs/roomtrace/protocol.md),
[reproduction matrix](docs/roomtrace/reproduction-matrix.md) and
[paper artifact guide](docs/roomtrace/paper-artifacts.md).

## Licensing

Original RoomTrace code and model weights are Apache-2.0. Original RoomTrace
synthetic data are CC BY 4.0. See [the licensing guide](LICENSING.md) for the
registered example, installation packages and third-party material.
