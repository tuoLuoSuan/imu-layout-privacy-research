# Record and export phone–watch IMU

The three installers below form the current capture suite. Use them to record new input. The frozen synthetic paper evaluation in the repository README runs on a computer and requires no devices.

| Component | Version and compatibility | Download | Source |
|---|---|---|---|
| Phone recorder | 0.2.4, version code 7, Android 14 or newer (API 34+) | [APK](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/download/joint-watch-v0.2.23/IMU-Capture-0.2.4.apk) | [Android source](../../collection/imu-capture-suite/native/) |
| Watch recorder | 0.2.23, version code 25, Xiaomi Watch S5 with Vela | [RPK](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/download/joint-watch-v0.2.23/org.imuresearch.s5joint.release.0.2.23.rpk) | [S5 source](../../collection/imu-capture-suite/maintenance/daily-0.2.23/) |
| Watch-to-phone bridge | 0.2.5, AstroBox NG plugin API 4 and WASI 3 | [ABP](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/download/joint-watch-v0.2.23/IMU-Bridge-0.2.5-clock-discard.abp) | [Bridge source](../../collection/imu-capture-suite/maintenance/bridge-0.2.5/) |

[All downloads and checksums](https://github.com/tuoLuoSuan/imu-layout-privacy-research/releases/tag/joint-watch-v0.2.23) · [AstroBox NG upstream](https://github.com/AstralSightStudios/AstroBox-NG)

## Install, record and export

1. Install the APK on the Android phone. Use AstroBox NG to connect to the S5, import the ABP as a plugin, and install the RPK as a watch app. The phone and watch apps are labeled **IMU 联合采集**, and the bridge is labeled **IMU 联合时间桥**.
2. In the bridge, select **准备采集** (Prepare capture). In the phone app, select **开始采集** (Start capture). Wait for the phone to report that it is connected, then start on the watch. The phone records accelerometer and gyroscope channels. The S5 records three-axis acceleration.
3. Stop the recording and let both devices finish saving and transferring. In the phone app, select the session under **记录** (Records) and export the combined ZIP to a folder you can access on your computer. A complete export contains `phone.zip`, `watch.jsonl` and `bundle-manifest.json`.

For updates from S5 versions 0.2.20–0.2.22, the current package uses the same signing identity. Versions 0.2.19 and earlier use the older signing identity. Export and verify any records you need before migrating from the older identity or replacing an AstroBox plugin that has unsaved logs.

## Check and use the export

From the repository root, run the validator shipped with bridge 0.2.5. It checks archive integrity, matching session IDs and recorded row counts. Use an output path that does not exist yet.

```bash
python collection/imu-capture-suite/maintenance/bridge-0.2.5/analyze.py CAPTURE.zip --output capture-check.json
```

A phone-only export is reported separately. The report checks transport and integrity and retains the exported clock diagnostics. Physical clock alignment and room registration require separate calibration.

For a phone action timeline, extract the outer ZIP, then extract `phone.zip` into `SESSION/phone/` so that `SESSION/phone/accelerometer.csv` and `SESSION/phone/gyroscope.csv` exist. Install the Python dependencies from the main README, then run:

```bash
python -m roomtrace actions --session SESSION --out output/activity-timeline.json
```

The layout decoder reads a separate registered-evidence JSON with the declared room outline, furniture classes and dimensions, walking points, and class-labeled contacts. See the [synthetic decoder examples](../../examples/) and the [reproduction matrix](reproduction-matrix.md) for tested entry points and the scope of the real-room replay.

## Package integrity

Compare the SHA-256 of downloaded installers against these values. On Windows use `Get-FileHash FILENAME -Algorithm SHA256`. On Linux use `sha256sum FILENAME`.

| File | SHA-256 |
|---|---|
| `IMU-Capture-0.2.4.apk` | `64634dc2a78285e0c409ddac244ed7608ce37636b5b5833bdda7d174e4f9b015` |
| `org.imuresearch.s5joint.release.0.2.23.rpk` | `1ccc868de25d7d8aa539d841fef9273deb6eafe959ad8f775b9fe3b3b18b797c` |
| `IMU-Bridge-0.2.5-clock-discard.abp` | `b9cfc2199fc6a20d0b7129bc94fea20080a22d6794f19a62eca809be4e81c71d` |

The current release was checked by downloading all three packages and comparing their hashes. Runtime compatibility on a particular phone, watch firmware or AstroBox installation depends on that device setup.
