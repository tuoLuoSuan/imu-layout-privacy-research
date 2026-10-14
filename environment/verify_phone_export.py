"""Audit a Sensor Logger ZIP without extracting or changing its original files.

All timestamp arithmetic starts with integer nanoseconds. Different channels
remain on their own recorded time grids. Units are documented expectations,
not a calibration performed by this script.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np


CHANNELS = {
    "Accelerometer.csv": "linear_acceleration",
    "TotalAcceleration.csv": "acceleration_with_gravity",
    "Gyroscope.csv": "angular_velocity",
    "AccelerometerUncalibrated.csv": "uncalibrated_acceleration",
    "GyroscopeUncalibrated.csv": "uncalibrated_angular_velocity",
}
SEGMENTS = [(0, 30, "stationary"), (30, 45, "rotation"), (45, 60, "walking")]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def describe(values):
    if not len(values):
        return None
    arr = np.asarray(values, dtype=float)
    ordered = np.sort(arr)
    return {
        "count": len(arr),
        "mean": float(np.mean(arr)),
        "std_population": float(np.std(arr)),
        "min": float(np.min(arr)),
        "median": float(np.median(arr)),
        "p95_nearest_rank": float(ordered[math.ceil(0.95 * len(arr)) - 1]),
        "max": float(np.max(arr)),
    }


def read_channel(payload, metadata_epoch_ms):
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    header = reader.fieldnames
    required = {"time", "seconds_elapsed", "x", "y", "z"}
    if not header or not required.issubset(header):
        raise ValueError(f"Required columns missing: {header}")
    rows = list(reader)
    if len(rows) < 2:
        raise ValueError("Not enough samples to audit sampling intervals")
    integer_encoding = all(re.fullmatch(r"[+-]?\d+", row["time"] or "") for row in rows)
    if not integer_encoding:
        raise ValueError("time must contain integer text; do not round floating epoch timestamps")
    timestamps = [int(row["time"]) for row in rows]
    elapsed = np.asarray([float(row["seconds_elapsed"]) for row in rows])
    xyz = np.asarray([[float(row[axis]) for axis in ("x", "y", "z")] for row in rows])
    if not np.isfinite(xyz).all() or not np.isfinite(elapsed).all():
        raise ValueError("Nonfinite sensor/elapsed values found")
    delta_ns = [right - left for left, right in zip(timestamps, timestamps[1:])]
    span_ns = timestamps[-1] - timestamps[0]
    if span_ns <= 0:
        raise ValueError("Nonpositive timestamp span")
    magnitudes = np.linalg.norm(xyz, axis=1)
    elapsed_from_epoch = np.asarray([(t - metadata_epoch_ms * 1_000_000) / 1e9 for t in timestamps])
    stats = {
        "rows": len(rows),
        "header": header,
        "time_integer_text": integer_encoding,
        "time_first_ns": str(timestamps[0]),
        "time_last_ns": str(timestamps[-1]),
        "time_span_s": span_ns / 1e9,
        "elapsed_first_s": float(elapsed[0]),
        "elapsed_last_s": float(elapsed[-1]),
        "observed_rate_hz": (len(rows) - 1) / (span_ns / 1e9),
        "gaps_ms": describe([value / 1e6 for value in delta_ns]),
        "duplicate_timestamps": sum(value == 0 for value in delta_ns),
        "timestamp_regressions": sum(value < 0 for value in delta_ns),
        "elapsed_regressions": int(np.sum(np.diff(elapsed) < 0)),
        "gaps_gt_100ms": sum(value > 100_000_000 for value in delta_ns),
        "gaps_gt_1s": sum(value > 1_000_000_000 for value in delta_ns),
        "exact_duplicate_rows": len(rows) - len({tuple(row.get(col) for col in header) for row in rows}),
        "missing_cells": sum(value is None or value == "" for row in rows for value in row.values()),
        "timestamp_step_gcd_ns": math.gcd(*delta_ns),
        "timestamps_divisible_by_100ns": all(t % 100 == 0 for t in timestamps),
        "elapsed_vs_epoch_residual_ns": describe((elapsed - elapsed_from_epoch) * 1e9),
        "axis_summary": {axis: describe(xyz[:, i]) for i, axis in enumerate(("x", "y", "z"))},
        "magnitude_all": describe(magnitudes),
        "segments_user_reported_approximate": [],
        "rate_in_10s_bins": [],
    }
    for start, end, label in SEGMENTS:
        mask = (elapsed >= start) & (elapsed < end)
        local_time = [t for t, keep in zip(timestamps, mask) if keep]
        stats["segments_user_reported_approximate"].append({
            "start_s": start, "end_s": end, "activity_instruction": label,
            "magnitude": describe(magnitudes[mask]),
            "axis_mean": dict(zip(("x", "y", "z"), map(float, np.mean(xyz[mask], axis=0)))) if mask.any() else None,
            "observed_rate_hz": (len(local_time) - 1) * 1e9 / (local_time[-1] - local_time[0]) if len(local_time) > 1 else None,
        })
    for start in range(0, math.ceil(float(elapsed[-1])), 10):
        mask = (elapsed >= start) & (elapsed < start + 10)
        local_time = [t for t, keep in zip(timestamps, mask) if keep]
        stats["rate_in_10s_bins"].append({
            "start_s": start, "end_s": start + 10, "rows": len(local_time),
            "observed_rate_hz": (len(local_time) - 1) * 1e9 / (local_time[-1] - local_time[0]) if len(local_time) > 1 else None,
        })
    return stats, {"time_ns": timestamps, "elapsed_s": elapsed, "xyz": xyz, "magnitude": magnitudes}


def inspect_archive(path):
    path = Path(path).resolve()
    content = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"ZIP CRC failure: {bad_member}")
        metadata_rows = list(csv.DictReader(io.StringIO(archive.read("Metadata.csv").decode("utf-8-sig"))))
        if len(metadata_rows) != 1:
            raise ValueError("Expected exactly one Metadata.csv row")
        metadata = metadata_rows[0]
        epoch_ms = int(metadata["recording epoch time"])
        local_datetime = datetime.fromtimestamp(epoch_ms / 1000, timezone(timedelta(hours=8)))
        report = {
            "kind": "single_phone_foreground_input_audit_not_har_or_sync_validation",
            "source": str(path), "archive_bytes": len(content), "sha256": digest(content),
            "zip_crc_passed": True,
            "metadata": {key: val for key, val in metadata.items() if key != "device id"},
            "epoch_time_in_asia_shanghai": local_datetime.isoformat(),
            "epoch_time_in_utc": local_datetime.astimezone(timezone.utc).isoformat(),
            "metadata_datetime_difference_from_local_s": (
                local_datetime.replace(tzinfo=None) - datetime.strptime(metadata["recording time"], "%Y-%m-%d_%H-%M-%S")
            ).total_seconds(),
            "user_report": {"segments_s": SEGMENTS, "foreground": True, "screen_on": True,
                            "boundary_precision": "user reported approximate; no per-event markers"},
            "archive_members": [{"name": member.filename, "bytes": member.file_size,
                                 "sha256": digest(archive.read(member.filename))} for member in archive.infolist()],
            "annotation_bytes": len(archive.read("Annotation.csv")) if "Annotation.csv" in archive.namelist() else None,
            "channels": {},
            "dropout_rate_measured": False,
            "background_lifecycle_tested": False,
            "physical_axis_calibrated": False,
            "cross_device_clock_alignment_tested": False,
            "training_performed": False,
        }
        arrays = {}
        for filename, semantics in CHANNELS.items():
            if filename not in archive.namelist():
                continue
            stats, array = read_channel(archive.read(filename), epoch_ms)
            stats["expected_semantics_from_author_docs"] = semantics
            report["channels"][filename] = stats
            arrays[filename] = array
        report["required_motion_channels_present"] = all(name in arrays for name in (
            "Accelerometer.csv", "TotalAcceleration.csv", "Gyroscope.csv"))
        report["common_channel_overlap_s"] = [
            max(stats["elapsed_first_s"] for stats in report["channels"].values()),
            min(stats["elapsed_last_s"] for stats in report["channels"].values()),
        ]
    return report, arrays


def plot_diagnostics(arrays, output_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.fonttype": "none"})
    figure, axes = plt.subplots(4, 1, figsize=(11, 9), layout="constrained")
    titles = [
        ("TotalAcceleration.csv", "Acceleration incl. gravity", "Magnitude (m/s²)*"),
        ("Accelerometer.csv", "Linear acceleration", "Magnitude (m/s²)*"),
        ("Gyroscope.csv", "Angular velocity", "Magnitude (rad/s)*"),
    ]
    for axis, (name, title, unit) in zip(axes, titles):
        array = arrays[name]
        axis.plot(array["elapsed_s"], array["magnitude"], color="#176c85", linewidth=0.8)
        axis.set_ylabel(unit)
        axis.set_title(title, loc="left", fontsize=11)
        axis.set_xlim(0, max(a["elapsed_s"][-1] for a in arrays.values()))
        axis.grid(axis="y", alpha=0.2)
        for start, end, label in SEGMENTS:
            axis.axvspan(start, end, facecolor={"stationary": "#e9eef3", "rotation": "#f3e6d0", "walking": "#dfede5"}[label], alpha=0.5)
        for boundary in (30, 45, 60):
            axis.axvline(boundary, color="#777777", linestyle="--", linewidth=0.6)
    for start, end, label in SEGMENTS:
        axes[0].text((start + end) / 2, 1.01, label, ha="center", transform=axes[0].get_xaxis_transform())
    for name, color, label in [("Accelerometer.csv", "#a9612b", "Linear accel."),
                                ("TotalAcceleration.csv", "#176c85", "Total accel."),
                                ("Gyroscope.csv", "#597644", "Gyroscope")]:
        array = arrays[name]
        times = array["time_ns"]
        gaps = [(b - a) / 1e6 for a, b in zip(times, times[1:])]
        axes[3].plot(array["elapsed_s"][1:], gaps, label=label, color=color, linewidth=0.8)
    axes[3].set_ylim(0, 45)
    axes[3].set_ylabel("Recorded gap (ms)")
    axes[3].set_xlabel("Elapsed time within this phone recording (s)")
    axes[3].legend(loc="lower right", ncol=3, frameon=False)
    axes[3].grid(axis="y", alpha=0.2)
    figure.suptitle("Phone pilot 001 | foreground recording", fontsize=14, x=0.01, ha="left")
    figure.supxlabel("Approximate 30/15/15 s instructions supplied by user; no event labels.\n* Units follow author documentation and are not a physical calibration.", fontsize=9)
    figure.savefig(output_path, dpi=180)
    figure.savefig(Path(output_path).with_suffix(".svg"))
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report, arrays = inspect_archive(args.archive)
    (args.output_dir / "acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_diagnostics(arrays, args.output_dir / "phone-pilot-diagnostics.png")
    summary = {"sha256": report["sha256"], "zip_crc_passed": report["zip_crc_passed"],
               "annotation_bytes": report["annotation_bytes"],
               "epoch_local": report["epoch_time_in_asia_shanghai"],
               "channels": {name: {key: stats[key] for key in (
                   "rows", "time_span_s", "observed_rate_hz", "gaps_gt_100ms", "timestamp_regressions")}
                   for name, stats in report["channels"].items()}}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
