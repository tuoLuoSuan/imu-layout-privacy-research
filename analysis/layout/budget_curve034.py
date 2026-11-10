"""Whole-room recovery against the contact budget, assembled from three runs.

Sources
  output/layout-recon/quota_k034/rooms/*.json     dev 12 rooms, k = 6..14
  output/layout-recon/quota_k034b/rooms/*.json    52 new rooms, k = 8,10,12
  output/layout-recon/select032_64/stage-*.json   64 rooms, k = 6 (+ base rows)

Only bal_disperse, bal_random and base rows are used.  Random arms are averaged
over their three seeds inside a room before any cross-room statistic, so the
paired difference equals the difference of the two arm means by construction.
"""
import glob
import json
import os
from itertools import product

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "output/layout-recon/budget_curve034.json")
K_LIST = (6, 8, 10, 12, 14)


def load_rows():
    rows = []
    for d in ("quota_k034", "quota_k034b"):
        for path in glob.glob(os.path.join(ROOT, "output/layout-recon", d, "rooms", "room-*.json")):
            rows.extend(json.load(open(path, encoding="utf-8"))["rows"])
    for path in sorted(glob.glob(os.path.join(ROOT, "output/layout-recon/select032_64/stage-*.json"))):
        rows.extend(json.load(open(path, encoding="utf-8"))["rows"])
    out = []
    for r in rows:
        if r.get("error"):
            continue
        arm = r["arm"]
        if arm not in ("base", "bal_disperse", "bal_random"):
            continue
        k = 14 if arm == "base" else int(r["k"])
        out.append({"room": int(r["room"]), "arm": "base" if arm == "base" else arm, "k": k,
                    "hit": bool(r["all_instances_hit"]), "f1": float(r["f1"]),
                    "seed": r.get("seed")})
    return out


def sign_flip(diff, seed=11):
    d = np.asarray([x for x in diff if abs(x) > 1e-12], float)
    if not len(d):
        return 1.0
    obs = abs(d.sum())
    rng = np.random.default_rng(seed)
    cnt = 0
    draws = 200000
    for _ in range(draws):
        cnt += int(abs((d * rng.choice([-1.0, 1.0], len(d))).sum()) >= obs - 1e-12)
    return (cnt + 1) / (draws + 1)


def main():
    rows = load_rows()
    by = {}
    for r in rows:
        by.setdefault((r["k"], r["room"]), {}).setdefault(r["arm"], []).append(r)
    report = {"k": {}, "rows": len(rows), "rooms": len({r["room"] for r in rows})}
    for k in K_LIST:
        pairs = []
        for (kk, room), cell in by.items():
            if kk != k:
                continue
            d = cell.get("bal_disperse") or cell.get("base")
            b = cell.get("bal_random") or cell.get("base")
            if not d or not b:
                continue
            pairs.append({"room": room,
                          "hit_a": float(bool(d[0]["hit"])),
                          "hit_b": float(np.mean([1.0 if x["hit"] else 0.0 for x in b])),
                          "f1_a": float(d[0]["f1"]),
                          "f1_b": float(np.mean([x["f1"] for x in b]))})
        if not pairs:
            continue
        diff = np.array([x["f1_a"] - x["f1_b"] for x in pairs])
        ha = np.array([x["hit_a"] for x in pairs])
        hb = np.array([x["hit_b"] for x in pairs])
        rng = np.random.default_rng(3)
        boot = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(50000)]
        report["k"][k] = {
            "n_rooms": len(pairs),
            "hits_disperse": float(ha.sum()), "hits_random": float(hb.sum()),
            "f1_disperse": float(np.mean([x["f1_a"] for x in pairs])),
            "f1_random": float(np.mean([x["f1_b"] for x in pairs])),
            "mean_diff": float(diff.mean()),
            "boot95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "better": int((ha > hb).sum()), "worse": int((hb > ha).sum()),
            "tie": int((ha == hb).sum()),
            "sign_flip_p": sign_flip(diff)}
        print(k, json.dumps(report["k"][k]))
    json.dump(report, open(OUT, "w", encoding="utf-8"), indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
