"""Recompute the paired contrasts of the class-quota selection experiment (032).

The paired block that select032.json stores for bal_random - plain_random read
one row per (room, arm) instead of the three-seed mean, so its values disagree
with the arm means. This module recomputes every paired contrast from the
per-row stage files and writes paired_recomputed.json. The stored block is left
untouched as a record of what was written.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT_DIR = "output/layout-recon/select032"
CONTRASTS = [
    ("disperse_minus_random", "bal_disperse", "bal_random"),
    ("bal_random_minus_plain_random", "bal_random", "plain_random"),
    ("oracle_minus_random", "bal_oracle", "bal_random"),
]


def sign(x, eps=1e-12):
    return 1 if x > eps else (-1 if x < -eps else 0)


def summarise(rows, arm_a, arm_b):
    rooms = sorted({r["room"] for r in rows})
    f1_diffs, hit_diffs = [], []
    for room in rooms:
        a_rows = [r for r in rows if r["room"] == room and r["arm"] == arm_a]
        b_rows = [r for r in rows if r["room"] == room and r["arm"] == arm_b]
        if not a_rows or not b_rows:
            continue
        f1_diffs.append(sum(r["f1"] for r in a_rows) / len(a_rows)
                        - sum(r["f1"] for r in b_rows) / len(b_rows))
        hit_diffs.append(sum(1 for r in a_rows if r["all_instances_hit"]) / len(a_rows)
                         - sum(1 for r in b_rows if r["all_instances_hit"]) / len(b_rows))
    count = lambda v, want: sum(1 for x in v if sign(x) == want)
    return dict(n=len(f1_diffs), mean_diff=sum(f1_diffs) / len(f1_diffs),
                better=count(f1_diffs, 1), worse=count(f1_diffs, -1),
                equal=count(f1_diffs, 0), mean_hit_diff=sum(hit_diffs) / len(hit_diffs),
                hit_better=count(hit_diffs, 1), hit_worse=count(hit_diffs, -1),
                hit_equal=count(hit_diffs, 0))


def main():
    result = {}
    for stage in ("dev", "confirm"):
        path = os.path.join(ROOT, OUT_DIR, "stage-%s.json" % stage)
        rows = json.load(open(path, encoding="utf-8"))["rows"]
        result[stage] = {name: summarise(rows, a, b) for name, a, b in CONTRASTS}
    dest = os.path.join(ROOT, OUT_DIR, "paired_recomputed.json")
    json.dump(result, open(dest, "w", encoding="utf-8"), indent=1)
    for stage, block in result.items():
        print(stage, {k: (round(v["mean_diff"], 4), v["better"], v["worse"], v["equal"])
                      for k, v in block.items()})
    print("wrote", dest)


if __name__ == "__main__":
    main()
