"""Paired statistics for the placement experiment under sensor error (034b).

Reads output/layout-recon/placement034b/placement033.json (32 rooms, severity
0.5) and writes the exact McNemar test, the paired room bootstrap interval and
the mean F1 of both placement protocols.
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RUNS = [os.path.join(ROOT, "output/layout-recon/placement034b/placement033.json"),
        os.path.join(ROOT, "output/layout-recon/placement034c/placement033.json")]
OUT = os.path.join(ROOT, "output/layout-recon/placement034b/paired64.json")


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1))
    return min(1.0, 2 * tail / 2 ** n)


def main():
    by = {}
    for run in RUNS:
        if not os.path.exists(run):
            continue
        data = json.load(open(run, encoding="utf-8"))
        for row in data["rows"]:
            by.setdefault(row["room"], {})[row["placement"]] = row
    rooms = sorted(by)
    dh = [1.0 if by[r]["dispersed"]["all_instances_hit"] else 0.0 for r in rooms]
    rh = [1.0 if by[r]["repeat"]["all_instances_hit"] else 0.0 for r in rooms]
    b = sum(1 for x, y in zip(dh, rh) if x > y)
    c = sum(1 for x, y in zip(dh, rh) if y > x)
    diffs = np.array([x - y for x, y in zip(dh, rh)])
    rng = np.random.default_rng(0)
    boot = [diffs[rng.integers(0, len(rooms), len(rooms))].mean() * 100 for _ in range(50000)]
    out = {"n": len(rooms), "severity": 0.5,
           "dispersed": int(sum(dh)), "repeat": int(sum(rh)),
           "b": int(b), "c": int(c), "p": float(mcnemar_exact(b, c)),
           "delta_pp": float((sum(dh) - sum(rh)) / len(rooms) * 100),
           "boot95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
           "f1_dispersed": float(np.mean([by[r]["dispersed"]["f1"] for r in rooms])),
           "f1_repeat": float(np.mean([by[r]["repeat"]["f1"] for r in rooms]))}
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
