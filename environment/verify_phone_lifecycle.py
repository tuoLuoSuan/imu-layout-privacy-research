"""Inspect a user-reported 30 minute Sensor Logger lifecycle experiment.

State ranges are approximate protocol times, not OS lifecycle telemetry.
No signal interpolation, gap filling, or training is performed.
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


PHASES = [
    (0, 300, "foreground_screen_on"),
    (300, 900, "screen_locked"),
    (900, 1500, "other_app_screen_on"),
    (1500, 1800, "returned_foreground"),
]


def intersect_intervals(left, right):
    """Intersection of sorted, internally disjoint open intervals."""
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        start = max(left[i][0], right[j][0])
        end = min(left[i][1], right[j][1])
        if start < end:
            result.append((start, end))
        if left[i][1] < right[j][1]:
            i += 1
        else:
            j += 1
    return result


def inspect_lifecycle(path):
    content = Path(path).read_bytes()
    archive_hash = digest(content)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        failure = archive.testzip()
        if failure is not None:
            raise ValueError(f"ZIP CRC failure: {failure}")
        metadata = list(csv.DictReader(io.StringIO(archive.read("Metadata.csv").decode("utf-8-sig"))))
        if len(metadata) != 1:
            raise ValueError("Expected one metadata row")
        metadata = metadata[0]
        epoch_ms = int(metadata["recording epoch time"])
        report = {
            "kind": "phone_lifecycle_export_continuity_audit",
            "source": str(Path(path).resolve()), "sha256": archive_hash,
            "archive_bytes": len(content), "zip_crc_passed": True,
            "metadata": {key: value for key, value in metadata.items() if key != "device id"},
            "epoch_time_in_asia_shanghai": datetime.fromtimestamp(
                epoch_ms / 1000, timezone(timedelta(hours=8))).isoformat(),
            "user_report": {"followed_protocol": True, "no_visible_errors_reported": True,
                            "battery_policy": "not_checked_or_not_found",
                            "nominal_phases_s": PHASES,
                            "actual_transition_markers_available": False},
            "annotation_bytes": len(archive.read("Annotation.csv")),
            "archive_members": [{"name": member.filename, "bytes": member.file_size,
                                 "sha256": digest(archive.read(member.filename))} for member in archive.infolist()],
            "long_gap_threshold_s": 1.0,
            "channels": {}, "training_performed": False,
            "sensor_api_or_os_root_cause_confirmed": False,
            "hardware_dropout_rate_measured": False,
        }
        arrays = {}
        all_long_gaps = []
        for name in CHANNELS:
            if name not in archive.namelist():
                continue
            stats, array = read_channel(archive.read(name), epoch_ms)
            # The first-pilot helper computes 30/15/15 s activity summaries.
            # Those instructions do not apply to this lifecycle experiment.
            stats.pop("segments_user_reported_approximate")
            stats.pop("rate_in_10s_bins")
            stats["whole_span_row_density_hz"] = stats.pop("observed_rate_hz")
            elapsed = array["elapsed_s"]
            times = array["time_ns"]
            gap_indices = [i for i, (a, b) in enumerate(zip(times, times[1:])) if b - a > 1_000_000_000]
            gaps = [(float(elapsed[i]), float(elapsed[i + 1])) for i in gap_indices]
            stats["long_gaps"] = [{"from_s": start, "to_s": end, "duration_s": end - start} for start, end in gaps]
            stats["nominal_phase_statistics"] = []
            for start, end, state in PHASES:
                selected = (elapsed >= start) & (elapsed < end)
                selected_time = [t for t, keep in zip(times, selected) if keep]
                intervals = [(b - a) / 1e6 for a, b in zip(selected_time, selected_time[1:])]
                stats["nominal_phase_statistics"].append({
                    "nominal_start_s": start, "nominal_end_s": end, "user_reported_state": state,
                    "rows": int(np.sum(selected)),
                    "rows_per_s_of_full_nominal_window": int(np.sum(selected)) / (end - start),
                    "within_window_median_gap_ms": float(np.median(intervals)) if intervals else None,
                    "long_gap_overlap_s": sum(max(0, min(gap_end, end) - max(gap_start, start)) for gap_start, gap_end in gaps),
                })
            edges = np.arange(0, np.ceil(float(elapsed[-1]) / 10) * 10 + 0.1, 10)
            counts, _ = np.histogram(elapsed, bins=edges)
            if int(np.sum(counts)) != stats["rows"]:
                raise AssertionError("Time-bin counts do not reconcile")
            stats["counts_per_10s"] = [{"start_s": float(start), "end_s": float(end), "rows": int(count)}
                                      for start, end, count in zip(edges, edges[1:], counts)]
            stats["expected_semantics_from_author_docs"] = CHANNELS[name]
            report["channels"][name] = stats
            arrays[name] = array
            all_long_gaps.append(gaps)
        common = all_long_gaps[0] if all_long_gaps else []
        for gaps in all_long_gaps[1:]:
            common = intersect_intervals(common, gaps)
        report["common_long_gaps_all_exported_motion_channels"] = [
            {"from_s": start, "to_s": end, "duration_s": end - start} for start, end in common]
        total = sum(end - start for start, end in common)
        span = max(float(array["elapsed_s"][-1]) for array in arrays.values()) - min(float(array["elapsed_s"][0]) for array in arrays.values())
        report["common_long_gap_duration_s"] = total
        report["common_long_gap_fraction_of_outer_record_span"] = total / span
        report["outer_record_span_s"] = span
        report["nominal_phase_common_gap_overlap_s"] = [
            {"state": state, "nominal_start_s": start, "nominal_end_s": end,
             "common_long_gap_overlap_s": sum(max(0, min(b, end) - max(a, start)) for a, b in common)}
            for start, end, state in PHASES]
        report["continuous_export_accepted"] = all(stats["gaps_gt_1s"] == 0 for stats in report["channels"].values())
    return report, arrays


def plot_lifecycle(report, arrays, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})
    fig, axes = plt.subplots(3, 1, figsize=(12, 8.8), layout="constrained", sharex=True)
    labels = {"Accelerometer.csv": "Linear acceleration", "TotalAcceleration.csv": "Total acceleration",
              "Gyroscope.csv": "Gyroscope", "AccelerometerUncalibrated.csv": "Uncal. acceleration",
              "GyroscopeUncalibrated.csv": "Uncal. gyroscope"}
    colors = {"Accelerometer.csv": "#ac602c", "TotalAcceleration.csv": "#176c85", "Gyroscope.csv": "#54763e"}
    for row_index, (name, array) in enumerate(arrays.items()):
        first = float(array["elapsed_s"][0])
        runs = []
        for gap in report["channels"][name]["long_gaps"]:
            runs.append((first / 60, (gap["from_s"] - first) / 60))
            first = gap["to_s"]
        runs.append((first / 60, (float(array["elapsed_s"][-1]) - first) / 60))
        axes[0].broken_barh(runs, (row_index - 0.25, 0.5), facecolors="#176c85")
    axes[0].set_yticks(list(range(len(arrays))), [labels[name] for name in arrays])
    axes[0].set_title("Recorded runs separated at gaps longer than 1 second", loc="left", pad=28)
    axes[0].invert_yaxis()
    for name, color in colors.items():
        bins = report["channels"][name]["counts_per_10s"]
        centers = [(item["start_s"] + item["end_s"]) / 120 for item in bins]
        counts = [item["rows"] for item in bins]
        axes[1].step(centers, counts, where="mid", color=color, label=labels[name], linewidth=1.2)
        array = arrays[name]
        times = array["time_ns"]
        gap_seconds = [(b - a) / 1e9 for a, b in zip(times, times[1:])]
        axes[2].semilogy(array["elapsed_s"][1:] / 60, gap_seconds, ".", color=color, markersize=1.5, alpha=0.65)
    axes[1].set_title("Rows in each 10 second bin (zero means no exported samples)", loc="left")
    axes[1].set_ylabel("Rows / 10 s")
    axes[1].set_ylim(bottom=0)
    axes[1].legend(loc="upper left", bbox_to_anchor=(0, -0.035), frameon=False, ncol=3, fontsize=9)
    axes[2].set_title("Recorded timestamp gaps, including all long intervals", loc="left")
    axes[2].set_ylabel("Gap (s), log scale")
    axes[2].set_xlabel("Elapsed recording time (minutes)")
    axes[2].axhline(1, color="#777777", linestyle="--", linewidth=0.8)
    names = ["Foreground", "Locked", "Other app", "Foreground"]
    band_colors = ["#e8eff4", "#f5e3d8", "#f6edcf", "#e2eee4"]
    for axis in axes:
        axis.set_xlim(0, max(float(array["elapsed_s"][-1]) for array in arrays.values()) / 60)
        axis.set_xticks(np.arange(0, 31, 5))
        axis.grid(axis="x", alpha=0.2)
        for (start, end, _), band_color in zip(PHASES, band_colors):
            axis.axvspan(start / 60, end / 60, color=band_color, alpha=0.4, zorder=-2)
        for boundary in (5, 15, 25):
            axis.axvline(boundary, color="#777777", linestyle="--", linewidth=0.7)
    for (start, end, _), name in zip(PHASES, names):
        axes[0].text((start + end) / 120, 1.02, name, ha="center", transform=axes[0].get_xaxis_transform())
    fig.suptitle("Phone lifecycle 001 | export continuity did not pass", x=0.01, ha="left", fontsize=15)
    fig.supxlabel("Shaded state windows follow the user-confirmed protocol; exact transition markers and OS logs are unavailable.\nNo waveform interpolation or gap filling. Missing export rows do not identify the root cause.", fontsize=9)
    fig.savefig(destination, dpi=180)
    fig.savefig(Path(destination).with_suffix(".svg"))
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report, arrays = inspect_lifecycle(args.archive)
    (args.output_dir / "acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_lifecycle(report, arrays, args.output_dir / "phone-lifecycle-diagnostics.png")
    print(json.dumps({"sha256": report["sha256"], "outer_record_span_s": report["outer_record_span_s"],
                      "continuous_export_accepted": report["continuous_export_accepted"],
                      "common_long_gaps": report["common_long_gaps_all_exported_motion_channels"],
                      "common_long_gap_duration_s": report["common_long_gap_duration_s"],
                      "nominal_phase_common_gap_overlap_s": report["nominal_phase_common_gap_overlap_s"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
