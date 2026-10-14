"""Audit a phone export against saved foreground/locked/returned snapshots.

Snapshot instants are observations, not screen-transition ground truth.
The export and phone wall clock are compared without assuming external sync.
"""

import argparse
import csv
import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from verify_phone_export import CHANNELS, digest, read_channel
from verify_phone_lifecycle import intersect_intervals


LOCAL_TZ = timezone(timedelta(hours=8))


def local_time(ns):
    seconds, nanos = divmod(int(ns), 1_000_000_000)
    return (datetime.fromtimestamp(seconds, LOCAL_TZ) + timedelta(microseconds=nanos // 1000)).isoformat()


def inspect_adb_export(path, runtime_path):
    content = Path(path).read_bytes()
    runtime = json.loads(Path(runtime_path).read_text(encoding="utf-8"))
    report = {
        "kind": "phone_export_and_runtime_snapshot_comparison",
        "source": str(Path(path).resolve()), "sha256": digest(content), "archive_bytes": len(content),
        "runtime_summary_source": str(Path(runtime_path).resolve()),
        "runtime_summary_sha256": digest(Path(runtime_path).read_bytes()),
        "channels": {}, "user_report": {"sequence": ["foreground", "locked", "returned_foreground"],
                                           "exact_transition_markers_available": False,
                                           "fixed_60_90_30_protocol": False},
        "clock_comparison_assumption": "Export epoch and handset wall time have no independently measured offset; no cross-device synchronization claim",
        "training_performed": False, "hardware_dropout_rate_measured": False,
        "freeze_triggering_policy_identified": False,
    }
    arrays = {}
    common = None
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        failure = archive.testzip()
        if failure is not None:
            raise ValueError(f"ZIP CRC failure: {failure}")
        report["zip_crc_passed"] = True
        metadata = list(csv.DictReader(io.StringIO(archive.read("Metadata.csv").decode("utf-8-sig"))))
        if len(metadata) != 1:
            raise ValueError("Expected one metadata row")
        metadata = metadata[0]
        report["metadata"] = {k: v for k, v in metadata.items() if k != "device id"}
        report["annotation_bytes"] = len(archive.read("Annotation.csv"))
        report["archive_members"] = [{"name": item.filename, "bytes": item.file_size,
                                      "sha256": digest(archive.read(item.filename))} for item in archive.infolist()]
        for name in CHANNELS:
            stats, array = read_channel(archive.read(name), int(metadata["recording epoch time"]))
            stats.pop("segments_user_reported_approximate")
            stats.pop("rate_in_10s_bins")
            stats["whole_span_row_density_hz"] = stats.pop("observed_rate_hz")
            times = array["time_ns"]
            elapsed = array["elapsed_s"]
            differences = np.asarray([b - a for a, b in zip(times, times[1:])], dtype=np.int64)
            active = differences[(differences > 0) & (differences <= 100_000_000)]
            stats["active_median_interval_equivalent_hz"] = float(1e9 / np.median(active)) if len(active) else None
            stats["active_p95_interval_ms"] = float(np.percentile(active, 95) / 1e6) if len(active) else None
            stats["expected_semantics_from_author_docs"] = CHANNELS[name]
            indices = np.where(differences > 1_000_000_000)[0]
            intervals = [(times[i], times[i + 1]) for i in indices]
            common = intervals if common is None else intersect_intervals(common, intervals)
            stats["long_gaps"] = [{"from_s": float(elapsed[i]), "to_s": float(elapsed[i + 1]),
                                    "duration_s": (times[i + 1] - times[i]) / 1e9,
                                    "from_local": local_time(times[i]), "to_local": local_time(times[i + 1])}
                                   for i in indices]
            edges = np.arange(np.floor(min(0, float(elapsed[0]))), np.ceil(float(elapsed[-1])) + 1)
            counts, _ = np.histogram(elapsed, bins=edges)
            assert int(counts.sum()) == stats["rows"]
            stats["counts_per_1s"] = [{"start_s": float(a), "rows": int(n)} for a, n in zip(edges, counts)]
            report["channels"][name] = stats
            arrays[name] = array
    first = min(a["time_ns"][0] for a in arrays.values())
    last = max(a["time_ns"][-1] for a in arrays.values())
    reference = arrays["Accelerometer.csv"]
    origin = reference["time_ns"][0] - round(float(reference["elapsed_s"][0]) * 1e9)
    report["app_elapsed_origin_epoch_ns_approx"] = str(origin)
    report["outer_record_span_s"] = (last - first) / 1e9
    report["first_sample_local"] = local_time(first)
    report["last_sample_local"] = local_time(last)
    report["common_long_gaps"] = [{"from_s": (a - origin) / 1e9, "to_s": (b - origin) / 1e9,
                                   "duration_s": (b - a) / 1e9, "from_local": local_time(a),
                                   "to_local": local_time(b)} for a, b in common]
    report["common_long_gap_duration_s"] = sum(b - a for a, b in common) / 1e9
    report["common_gap_fraction_of_outer_span"] = report["common_long_gap_duration_s"] / report["outer_record_span_s"]
    report["snapshot_comparison"] = {}
    for stage, snapshot in runtime["stages"].items():
        moment = datetime.fromisoformat(f"{runtime['date']}T{snapshot['sensorservice_capture_time']}+08:00")
        epoch_ns = int(moment.timestamp()) * 1_000_000_000 + moment.microsecond * 1000
        neighbors = {}
        for name, array in arrays.items():
            times = array["time_ns"]
            index = int(np.searchsorted(times, epoch_ns))
            neighbors[name] = {
                "previous_sample_distance_s": (epoch_ns - times[index - 1]) / 1e9 if index else None,
                "next_sample_distance_s": (times[index] - epoch_ns) / 1e9 if index < len(times) else None,
            }
        report["snapshot_comparison"][stage] = {
            "local_time": moment.isoformat(), "app_elapsed_s_approx": (epoch_ns - origin) / 1e9,
            "inside_export_span": first <= epoch_ns <= last,
            "inside_common_long_gap_under_clock_assumption": any(a < epoch_ns < b for a, b in common),
            "client_listener_states": snapshot["client_listener_states"],
            "uid_event_connection_count": snapshot["uid_event_connection_count"],
            "android_services_dump_nothing": snapshot["android_services_dump_nothing"],
            "neighboring_samples": neighbors,
        }
    report["continuous_export_accepted"] = all(s["gaps_gt_1s"] == 0 for s in report["channels"].values())
    return report, arrays


def plot_audit(report, arrays, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})
    fig, axes = plt.subplots(3, 1, figsize=(12.5, 8.8), sharex=True, layout="constrained")
    labels = ["Linear accel.", "Total accel.", "Gyroscope", "Uncal. accel.", "Uncal. gyro."]
    for index, (name, array) in enumerate(arrays.items()):
        start = float(array["elapsed_s"][0])
        runs = []
        for gap in report["channels"][name]["long_gaps"]:
            runs.append((start, gap["from_s"] - start))
            start = gap["to_s"]
        runs.append((start, float(array["elapsed_s"][-1]) - start))
        axes[0].broken_barh(runs, (index - .26, .52), facecolors="#176c85")
    axes[0].set_yticks(range(len(arrays)), labels)
    axes[0].invert_yaxis()
    axes[0].set_title("Exported runs (split at gaps longer than 1 second)", loc="left", pad=27)
    for name, color, label in zip(list(arrays)[:3], ["#ac602c", "#176c85", "#54763e"], labels):
        bins = report["channels"][name]["counts_per_1s"]
        axes[1].step([b["start_s"] + .5 for b in bins], [b["rows"] for b in bins], where="mid", color=color, label=label, linewidth=1)
        array = arrays[name]
        intervals = [(b - a) / 1e9 for a, b in zip(array["time_ns"], array["time_ns"][1:])]
        axes[2].semilogy(array["elapsed_s"][1:], intervals, ".", color=color, markersize=1.6, alpha=.7)
    axes[1].set_title("Exported rows in each second", loc="left", pad=31)
    axes[1].set_ylabel("Rows / s")
    axes[1].set_ylim(bottom=0)
    axes[1].legend(frameon=False, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.005), fontsize=9)
    axes[2].set_title("All recorded timestamp intervals", loc="left")
    axes[2].set_ylabel("Interval (s), log scale")
    axes[2].set_xlabel("App seconds_elapsed (s)")
    axes[2].axhline(1, color="#777777", linestyle="--", linewidth=.7)
    for stage, color, title in [("foreground", "#486e36", "Foreground snapshot"),
                                ("locked", "#a04438", "Frozen snapshot"),
                                ("returned", "#524d8a", "Returned snapshot")]:
        x = report["snapshot_comparison"][stage]["app_elapsed_s_approx"]
        for axis in axes:
            axis.axvline(x, color=color, linestyle="--", linewidth=.9)
        axes[0].text(x, 1.015, title, ha="center", color=color, fontsize=8.6,
                     transform=axes[0].get_xaxis_transform())
    for axis in axes:
        axis.set_xlim(min(-1, min(float(a["elapsed_s"][0]) for a in arrays.values())),
                      max(float(a["elapsed_s"][-1]) for a in arrays.values()))
        axis.grid(axis="x", alpha=.18)
        for gap in report["common_long_gaps"]:
            axis.axvspan(gap["from_s"], gap["to_s"], color="#f0c9ad", alpha=.35, zorder=-2)
    fig.suptitle("Phone ADB diagnostic | frozen snapshot coincides with an export gap", x=.01, ha="left", fontsize=14)
    fig.supxlabel("Shading marks the measured common export gap, not a known lock interval. Dashed lines mark snapshot instants.\nPhone wall time is compared with export epoch; offset was not independently calibrated. No interpolation or training.", fontsize=9)
    fig.savefig(destination, dpi=175)
    fig.savefig(Path(destination).with_suffix(".svg"))
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--runtime-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report, arrays = inspect_adb_export(args.archive, args.runtime_summary)
    (args.output_dir / "acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_audit(report, arrays, args.output_dir / "phone-adb-export-diagnostics.png")
    print(json.dumps({k: report[k] for k in ["sha256", "outer_record_span_s", "first_sample_local", "last_sample_local",
                                           "common_long_gaps", "continuous_export_accepted"]}, ensure_ascii=False, indent=2))
    print(json.dumps({"snapshots": {stage: {k: v for k, v in item.items() if k != "neighboring_samples"}
                                    for stage, item in report["snapshot_comparison"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
