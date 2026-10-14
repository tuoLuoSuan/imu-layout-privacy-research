"""Audit the 60/90/30 second phone test with its reported app-return interruption."""

import argparse
import csv
import io
import json
import math
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from verify_phone_export import CHANNELS, digest, read_channel
from verify_phone_lifecycle import intersect_intervals


def inspect_repro(path):
    content = Path(path).read_bytes()
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        failure = archive.testzip()
        if failure is not None:
            raise ValueError(f"ZIP CRC failure: {failure}")
        meta = list(csv.DictReader(io.StringIO(archive.read("Metadata.csv").decode("utf-8-sig"))))
        if len(meta) != 1:
            raise ValueError("Expected one metadata row")
        meta = meta[0]
        epoch_ms = int(meta["recording epoch time"])
        report = {
            "kind": "short_phone_lifecycle_reproduction_with_user_reported_interruption",
            "source": str(Path(path).resolve()), "sha256": digest(content), "archive_bytes": len(content),
            "zip_crc_passed": True, "metadata": {k: v for k, v in meta.items() if k != "device id"},
            "epoch_time_in_asia_shanghai": datetime.fromtimestamp(epoch_ms / 1000, timezone(timedelta(hours=8))).isoformat(),
            "user_report": {
                "nominal_phases_s": [[0, 60, "foreground"], [60, 150, "locked_period_interrupted_by_app_return"], [150, 180, "foreground"]],
                "settings_changed_since_long_recording": False,
                "interruption": "User unlocked and returned to Sensor Logger once during nominal locked period",
                "exact_interruption_time_available": False,
                "uninterrupted_90s_locked_control": False,
                "battery_policy": "not_checked_or_not_found",
            },
            "annotation_bytes": len(archive.read("Annotation.csv")),
            "channels": {}, "sensor_api_or_os_root_cause_confirmed": False,
            "training_performed": False, "hardware_dropout_rate_measured": False,
        }
        arrays = {}
        channel_intervals = []
        for name in CHANNELS:
            stats, array = read_channel(archive.read(name), epoch_ms)
            stats.pop("segments_user_reported_approximate")
            stats.pop("rate_in_10s_bins")
            stats["whole_span_row_density_hz"] = stats.pop("observed_rate_hz")
            times, elapsed = array["time_ns"], array["elapsed_s"]
            indices = [i for i, (a, b) in enumerate(zip(times, times[1:])) if b - a > 1_000_000_000]
            intervals = [(float(elapsed[i]), float(elapsed[i + 1])) for i in indices]
            stats["long_gaps"] = [{"from_s": a, "to_s": b, "duration_s": b - a} for a, b in intervals]
            stats["pre_start_rows"] = int(np.sum(elapsed < 0))
            stats["nominal_phase_counts"] = [int(np.sum((elapsed >= a) & (elapsed < b)))
                                             for a, b, _ in report["user_report"]["nominal_phases_s"]]
            edges = np.arange(math.floor(min(0, float(elapsed[0]))), math.ceil(float(elapsed[-1])) + 1)
            counts, _ = np.histogram(elapsed, bins=edges)
            assert int(np.sum(counts)) == stats["rows"]
            stats["counts_per_1s"] = [{"start_s": int(a), "end_s": int(b), "rows": int(n)}
                                     for a, b, n in zip(edges, edges[1:], counts)]
            report["channels"][name] = stats
            arrays[name] = array
            channel_intervals.append(intervals)
        common = channel_intervals[0]
        for intervals in channel_intervals[1:]:
            common = intersect_intervals(common, intervals)
        report["common_long_gaps_all_exported_motion_channels"] = [
            {"from_s": a, "to_s": b, "duration_s": b - a} for a, b in common]
        report["common_long_gap_duration_s"] = sum(b - a for a, b in common)
        report["outer_record_span_s"] = max(float(a["elapsed_s"][-1]) for a in arrays.values()) - min(float(a["elapsed_s"][0]) for a in arrays.values())
        report["continuous_export_accepted"] = all(s["gaps_gt_1s"] == 0 for s in report["channels"].values())
    return report, arrays


def plot_repro(report, arrays, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.8), sharex=True, layout="constrained")
    labels = {"Accelerometer.csv": "Linear acceleration", "TotalAcceleration.csv": "Total acceleration",
              "Gyroscope.csv": "Gyroscope", "AccelerometerUncalibrated.csv": "Uncal. acceleration",
              "GyroscopeUncalibrated.csv": "Uncal. gyroscope"}
    for index, (name, array) in enumerate(arrays.items()):
        start = float(array["elapsed_s"][0])
        runs = []
        for gap in report["channels"][name]["long_gaps"]:
            runs.append((start, gap["from_s"] - start))
            start = gap["to_s"]
        runs.append((start, float(array["elapsed_s"][-1]) - start))
        axes[0].broken_barh(runs, (index - .25, .5), facecolors="#176c85")
    axes[0].set_yticks(list(range(len(arrays))), [labels[n] for n in arrays])
    axes[0].invert_yaxis()
    axes[0].set_title("Recorded runs separated at gaps longer than 1 second", loc="left")
    for name, color in [("Accelerometer.csv", "#ac602c"), ("TotalAcceleration.csv", "#176c85"), ("Gyroscope.csv", "#54763e")]:
        bins = report["channels"][name]["counts_per_1s"]
        axes[1].step([(b["start_s"] + b["end_s"]) / 2 for b in bins], [b["rows"] for b in bins], where="mid", label=labels[name], color=color, linewidth=1.1)
    axes[1].set_title("Exported rows in each second", loc="left")
    axes[1].set_ylabel("Rows / s")
    axes[1].set_ylim(bottom=0)
    axes[1].set_xlabel("Elapsed recording time (s)")
    axes[1].legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=3, frameon=False, fontsize=9)
    axes[1].set_title("Exported rows in each second", loc="left", pad=29)
    for axis in axes:
        axis.axvspan(0, 60, color="#e8eff4", alpha=.45, zorder=-2)
        axis.axvspan(60, 150, color="#f5e3d8", alpha=.45, zorder=-2)
        axis.axvspan(150, 180, color="#e2eee4", alpha=.45, zorder=-2)
        axis.axvline(60, color="#777777", linestyle="--", linewidth=.7)
        axis.axvline(150, color="#777777", linestyle="--", linewidth=.7)
        axis.set_xticks(np.arange(0, 181, 30))
        axis.set_xlim(-1, max(float(a["elapsed_s"][-1]) for a in arrays.values()))
        axis.grid(axis="x", alpha=.2)
    fig.suptitle("Short reproduction | two gaps persist with unchanged settings", x=.01, ha="left", fontsize=14)
    fig.supxlabel("Nominal lock period (60-150 s) was interrupted by one reported unlock and return to Sensor Logger.\nExact transition markers are unavailable. No data filling; pre-start samples are retained.", fontsize=9)
    fig.savefig(destination, dpi=180)
    fig.savefig(Path(destination).with_suffix(".svg"))
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report, arrays = inspect_repro(args.archive)
    (args.output_dir / "acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_repro(report, arrays, args.output_dir / "phone-short-repro-diagnostics.png")
    print(json.dumps({"sha256": report["sha256"], "outer_record_span_s": report["outer_record_span_s"],
                      "epoch_local": report["epoch_time_in_asia_shanghai"], "common_gaps": report["common_long_gaps_all_exported_motion_channels"],
                      "common_long_gap_duration_s": report["common_long_gap_duration_s"]}, indent=2))


if __name__ == "__main__":
    main()
