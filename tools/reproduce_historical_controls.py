"""Recompute the historical placement endpoints from archived synthetic scores."""

import argparse
from pathlib import Path

from analysis.layout.placement_stats033 import paired
from roomtrace.cli import read, write

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    archive = read(ROOT / "analysis/layout/expansion009-results.json")
    fixed = archive["mechanism"]["all10000"]["outline|1.0|14"]
    paired_counts = {key: fixed[key] for key in ("both", "a_only", "b_only", "neither")}
    n = sum(paired_counts.values())
    repeat = paired_counts["both"] + paired_counts["a_only"]
    dispersed = paired_counts["both"] + paired_counts["b_only"]
    fixed_walking = {
        "n": n,
        "repeat": repeat,
        "dispersed": dispersed,
        "delta_pp": 100 * (dispersed - repeat) / n,
        "archived_bootstrap95_pp": [100 * x for x in fixed["whole_difference_bootstrap_ci"]],
        "paired_counts": paired_counts,
    }

    archive = read(ROOT / "reproducibility/paired-synthetic-acquisition-scores.json")
    rooms = {row["room"]: {arm: row[arm] for arm in ("repeat", "dispersed")} for row in archive["pairs"]}
    complete = paired(rooms, "All synthetic acquisition pairs")
    excluded = set(archive["earlier_diagnostic_rooms"])
    nested = paired({room: row for room, row in rooms.items() if room not in excluded}, "Diagnostic overlap excluded")
    write(args.out, {"fixed_walking": fixed_walking, "paired_acquisition": complete, "overlap_excluded": nested})


if __name__ == "__main__":
    main()
