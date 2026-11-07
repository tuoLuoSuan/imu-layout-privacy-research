"""Category height priors from the AI2-THOR bedroom scenes.

The IMU never observes height, so the dense map's vertical dimension is a
category prior.  This module measures how good that prior actually is: the
table gives each category's median extent and 10-90 percentile band, and
`loso` scores the median against leave-one-scene-out held-out objects.
"""
import glob
import json
import os

import numpy as np

CATS = ("Bed", "Desk", "Cabinet", "Chair", "Shelf")


def load_objects(root):
    """One row per furniture instance: scene, category, height, footprint, wall contact."""
    rows = []
    for f in sorted(glob.glob(os.path.join(root, "FloorPlan*.json"))):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        if "objects" not in d:
            continue
        scene = os.path.basename(f)[:-5]
        # floor 契约是 [中心 x, 中心 z, 宽, 长]（与 sim_eval.load_scene 一致）
        fcx, fcz, fw, fl = d["floor"]
        fx0, fx1 = fcx - fw / 2, fcx + fw / 2
        fy0, fy1 = fcz - fl / 2, fcz + fl / 2
        for o in d["objects"]:
            s, c = o["size"], o["center"]
            x0, x1 = c["x"] - s["x"] / 2, c["x"] + s["x"] / 2
            z0, z1 = c["z"] - s["z"] / 2, c["z"] + s["z"] / 2
            gap = min(x0 - fx0, fx1 - x1, z0 - fy0, fy1 - z1)
            rows.append(dict(scene=scene, cat=o["type"], h=float(s["y"]),
                             area=float(s["x"] * s["z"]), against_wall=bool(gap < 0.15)))
    return rows


def table(rows, cats=CATS):
    """Median extent and 10-90 band per category, pooled over every scene."""
    out = {}
    for c in cats:
        v = np.array([r["h"] for r in rows if r["cat"] == c])
        if len(v):
            out[c] = dict(n=int(v.size), med=float(np.median(v)),
                          lo=float(np.percentile(v, 10)), hi=float(np.percentile(v, 90)))
    return out


def loso(rows, cats=CATS):
    """Score the category median on held-out scenes, one scene left out at a time."""
    scenes = sorted({r["scene"] for r in rows})
    out = {}
    for c in cats:
        err = []
        for s in scenes:
            train = [r["h"] for r in rows if r["cat"] == c and r["scene"] != s]
            if not train:
                continue
            med = float(np.median(train))
            err += [abs(med - r["h"]) for r in rows if r["cat"] == c and r["scene"] == s]
        if err:
            e = np.asarray(err)
            out[c] = dict(n=int(e.size), med_err=float(np.median(e)),
                          p90_err=float(np.percentile(e, 90)),
                          hit10=float((e <= 0.10).mean()), hit20=float((e <= 0.20).mean()))
    return out


def loso_conditioned(rows, cats=CATS, bins=3):
    """Same score, but the prior also conditions on footprint tertile and wall contact.

    Both are quantities the IMU pipeline measures, so this is legal; the question
    is only whether the extra conditioning buys accuracy.
    """
    scenes = sorted({r["scene"] for r in rows})
    err = []
    for s in scenes:
        train = [r for r in rows if r["scene"] != s]
        test = [r for r in rows if r["scene"] == s]
        edges = {}
        for c in cats:
            v = sorted(r["area"] for r in train if r["cat"] == c)
            edges[c] = [float(np.quantile(v, i / bins)) for i in range(1, bins)] if len(v) >= bins * 3 else []

        def key(r):
            k = sum(r["area"] > t for t in edges.get(r["cat"], []))
            return (r["cat"], k, r["against_wall"])

        pool = {}
        for r in train:
            pool.setdefault(key(r), []).append(r["h"])
        for r in test:
            v = pool.get(key(r))
            if not v or len(v) < 3:
                v = [x["h"] for x in train if x["cat"] == r["cat"]]
            err.append(abs(float(np.median(v)) - r["h"]) if v else 0.0)
    e = np.asarray(err)
    return dict(n=int(e.size), med_err=float(np.median(e)), p90_err=float(np.percentile(e, 90)),
                hit10=float((e <= 0.10).mean()), hit20=float((e <= 0.20).mean()))


def summary(root):
    rows = load_objects(root)
    return dict(objects=len(rows), scenes=len({r["scene"] for r in rows}),
                table=table(rows), loso=loso(rows), loso_conditioned=loso_conditioned(rows))


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "output/thor"
    s = summary(root)
    print("%d objects over %d scenes" % (s["objects"], s["scenes"]))
    print("%-9s %4s %6s %6s %6s %9s %9s %7s %7s" % ("cat", "n", "med", "p10", "p90",
                                                     "LOSO med", "LOSO p90", "<=10cm", "<=20cm"))
    for c in CATS:
        if c not in s["table"]:
            continue
        t, l = s["table"][c], s["loso"][c]
        print("%-9s %4d %6.2f %6.2f %6.2f %9.3f %9.3f %6.0f%% %6.0f%%"
              % (c, t["n"], t["med"], t["lo"], t["hi"], l["med_err"], l["p90_err"],
                 100 * l["hit10"], 100 * l["hit20"]))
    k = s["loso_conditioned"]
    print("conditioned on footprint tertile + wall contact: med %.3f m, <=10cm %.0f%%"
          % (k["med_err"], 100 * k["hit10"]))
