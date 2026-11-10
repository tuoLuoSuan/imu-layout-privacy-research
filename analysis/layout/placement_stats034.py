"""Paired statistics for the multi-decoder placement run (034).

placement034 decodes the same two recordings per room with three decoders.  This
script reports, per decoder, the exact McNemar test and the paired room
bootstrap interval of dispersed minus repeated placement, plus the agreement
between decoders on the same record, and writes
output/layout-recon/placement034/paired034.json.
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RUN = "output/layout-recon/placement034/placement034.json"
DEV = set(range(11500, 11512))
OUT = "output/layout-recon/placement034/paired034.json"


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1))
    return min(1.0, 2 * tail / 2 ** n)


def load():
    data = json.load(open(os.path.join(ROOT, RUN), encoding="utf-8"))
    by = {}
    for row in data["rows"]:
        if row.get("error"):
            continue
        by.setdefault(row["room"], {})[row["placement"]] = row["decoders"]
    return data, by


def block(by, rooms, arm):
    dh, rh, f1d, f1r = [], [], [], []
    for room in rooms:
        cell = by.get(room, {})
        d = cell.get("dispersed", {}).get(arm)
        r = cell.get("repeat", {}).get(arm)
        if not d or not r or "error" in d or "error" in r:
            continue
        dh.append(1.0 if d["all_instances_hit"] else 0.0)
        rh.append(1.0 if r["all_instances_hit"] else 0.0)
        f1d.append(d["f1"])
        f1r.append(r["f1"])
    n = len(dh)
    if not n:
        return None
    b = sum(1 for x, y in zip(dh, rh) if x > y)
    c = sum(1 for x, y in zip(dh, rh) if y > x)
    diffs = np.array([x - y for x, y in zip(dh, rh)])
    rng = np.random.default_rng(0)
    boot = [diffs[rng.integers(0, n, n)].mean() * 100 for _ in range(50000)]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return dict(n=n, dispersed=int(sum(dh)), repeat=int(sum(rh)), b=int(b), c=int(c),
                p=float(mcnemar_exact(b, c)),
                delta_pp=float((sum(dh) - sum(rh)) / n * 100),
                boot=[float(lo), float(hi)],
                f1_dispersed=float(np.mean(f1d)), f1_repeat=float(np.mean(f1r)))


def main():
    data, by = load()
    arms = sorted({a for cell in by.values() for arm in cell.values() for a in arm})
    rooms = sorted(by)
    result = {"decoders": arms, "rooms": len(rooms), "blocks": {}}
    for arm in arms:
        result["blocks"][arm] = {
            "dev12": block(by, sorted(DEV & set(rooms)), arm),
            "fresh64": block(by, sorted(set(rooms) - DEV), arm),
            "pooled": block(by, rooms, arm)}
        print(arm, json.dumps(result["blocks"][arm])[:400])
    # agreement between decoders on the same record
    pairs = {}
    for i, a in enumerate(arms):
        for b_arm in arms[i + 1:]:
            agree, total = 0, 0
            for room in rooms:
                for p in ("dispersed", "repeat"):
                    ca = by[room].get(p, {}).get(a)
                    cb = by[room].get(p, {}).get(b_arm)
                    if not ca or not cb or "error" in ca or "error" in cb:
                        continue
                    total += 1
                    agree += int(bool(ca["all_instances_hit"]) == bool(cb["all_instances_hit"]))
            pairs[f"{a}|{b_arm}"] = {"agree": agree, "total": total}
    result["hit_agreement"] = pairs
    dest = os.path.join(ROOT, OUT)
    json.dump(result, open(dest, "w", encoding="utf-8"), indent=1)
    print("wrote", dest)


if __name__ == "__main__":
    main()
