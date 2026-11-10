"""Paired statistics for the contact-placement transfer experiment (033).

Reads the two placement033 runs, reports the exact McNemar test, the paired
room bootstrap interval on the percentage-point difference and the mean F1 of
each arm, and writes output/layout-recon/placement033/paired.json.
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RUNS = [
    ("dev12", "output/layout-recon/placement033/placement033.json"),
    ("fresh64", "output/layout-recon/placement033b/placement033.json"),
]
OUT = "output/layout-recon/placement033/paired.json"


def load(rel):
    data = json.load(open(os.path.join(ROOT, rel), encoding="utf-8"))
    by = {}
    for row in data["rows"]:
        by.setdefault(row["room"], {})[row["placement"]] = row
    return data, by


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1))
    return min(1.0, 2 * tail / 2 ** n)


def paired(by, label):
    rooms = sorted(by)
    dh = [1.0 if by[r]["dispersed"]["all_instances_hit"] else 0.0 for r in rooms]
    rh = [1.0 if by[r]["repeat"]["all_instances_hit"] else 0.0 for r in rooms]
    b = sum(1 for d, x in zip(dh, rh) if d > x)
    c = sum(1 for d, x in zip(dh, rh) if x > d)
    diffs = np.array([d - x for d, x in zip(dh, rh)])
    rng = np.random.default_rng(0)
    boot = [diffs[rng.integers(0, len(rooms), len(rooms))].mean() * 100
            for _ in range(50000)]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    f1d = float(np.mean([by[r]["dispersed"]["f1"] for r in rooms]))
    f1r = float(np.mean([by[r]["repeat"]["f1"] for r in rooms]))
    out = dict(n=len(rooms), dispersed=int(sum(dh)), repeat=int(sum(rh)),
               b=int(b), c=int(c), p=float(mcnemar_exact(b, c)),
               delta_pp=float((sum(dh) - sum(rh)) / len(rooms) * 100),
               boot=[float(lo), float(hi)], f1=[f1d, f1r])
    print(label, out)
    return out


def main():
    runs = {name: load(rel)[1] for name, rel in RUNS}
    result = {name: paired(by, name) for name, by in runs.items()}
    pooled = {}
    for by in runs.values():
        for room, arms in by.items():
            pooled.setdefault(room, {}).update(arms)
    result["pooled76"] = paired(pooled, "pooled76")
    dest = os.path.join(ROOT, OUT)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    json.dump(result, open(dest, "w", encoding="utf-8"), indent=1)
    print("wrote", dest)


if __name__ == "__main__":
    main()
