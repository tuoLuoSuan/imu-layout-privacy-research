"""Paired statistics for the quota budget sweep (034).

Reads the per-room outputs of quota_k034 and reports, for every budget k, the
per-room paired difference between the quota-dispersed arm and the seed-mean of
the quota-random arm, together with whole-room hit counts, an exact sign-flip
test and a room bootstrap interval.
"""
import glob
import json
import os
from itertools import product

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "output/layout-recon/quota_k034/rooms")
OUT = os.path.join(ROOT, "output/layout-recon/quota_k034/paired_stats.json")


def sign_flip(diff, draws=200000, seed=7):
    d = np.asarray([x for x in diff if x != 0], float)
    if not len(d):
        return 1.0
    obs = abs(d.sum())
    rng = np.random.default_rng(seed)
    count = 0
    for _ in range(draws):
        s = np.abs((d * rng.choice([-1.0, 1.0], len(d))).sum())
        count += int(s >= obs - 1e-12)
    return (count + 1) / (draws + 1)


def tier(rows, k):
    by_room = {}
    for r in rows:
        if r["k"] != k or r.get("error"):
            continue
        by_room.setdefault(r["room"], {}).setdefault(r["arm"], []).append(r)
    out = []
    for room in sorted(by_room):
        cell = by_room[room]
        if "bal_disperse" not in cell or "bal_random" not in cell:
            continue
        a = cell["bal_disperse"][0]
        ref = cell["bal_random"]
        out.append({"room": room, "f1_a": a["f1"], "f1_b": float(np.mean([r["f1"] for r in ref])),
                    "hit_a": float(bool(a["all_instances_hit"])),
                    "hit_b": float(np.mean([1.0 if r["all_instances_hit"] else 0.0 for r in ref])),
                    "k_used": a["k_used"], "quota": a["quota"]})
    return out


def main():
    rows = []
    for path in sorted(glob.glob(os.path.join(SRC, "room-*.json"))):
        data = json.load(open(path, encoding="utf-8"))
        rows.extend(data["rows"])
    ks = sorted({r["k"] for r in rows})
    result = {"rooms": len({r["room"] for r in rows}), "k": {}}
    for k in ks:
        t = tier(rows, k)
        if not t:
            continue
        diff = np.array([x["f1_a"] - x["f1_b"] for x in t])
        ha = np.array([x["hit_a"] for x in t])
        hb = np.array([x["hit_b"] for x in t])
        b = int(((ha > hb)).sum())
        c = int(((hb > ha)).sum())
        rng = np.random.default_rng(0)
        boot = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(50000)]
        result["k"][k] = {
            "n_rooms": len(t),
            "f1_disperse": float(np.mean([x["f1_a"] for x in t])),
            "f1_random": float(np.mean([x["f1_b"] for x in t])),
            "mean_diff": float(diff.mean()),
            "sd": float(diff.std(ddof=1)),
            "boot95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "sign_flip_p": sign_flip(diff),
            "hits_disperse": float(ha.sum()),
            "hits_random": float(hb.sum()),
            "hit_b": b, "hit_c": c,
            "mean_k_used": float(np.mean([x["k_used"] for x in t]))}
        print(k, json.dumps(result["k"][k]))
    json.dump(result, open(OUT, "w", encoding="utf-8"), indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
