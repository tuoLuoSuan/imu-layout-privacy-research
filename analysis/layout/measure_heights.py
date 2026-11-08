"""从静态点云量房间净高与家具高度，并把「哪些高度看不到」显式写进输出。

点云只能扫到竖直面的下半段：本房间左半边的可见上限约 1.8 m（控制组是左墙——它已知
通到天花板，但 1.8 m 以上一个点都没有）。所以「点云里没有更高处」不等于「物体只有这么高」。
这个脚本同时给出两件事：能测的（天花板平面、物体顶面的水平面覆盖率）与测不到的（竖直面
被截断的高度），后者用左右两面墙做对照。
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

CLOUD = "fuse3-merged-clean.npy"
BIN = 0.1
SLAB = 0.05
CELL = 0.05
# 家具投影（与 layout_solver 输出一致，只用来取点，不参与定位）
FOOT = {"cab": (0.06, 0.02, 0.60, 1.00),
        "desk": (0.06, 1.07, 0.60, 2.05),
        "bed": (1.20, 2.02, 2.65, 4.00)}
# 正面带（法向一侧），用来量竖直面被截断的高度
FACE = {"cab": (0.55, 0.02, 0.75, 1.03),
        "desk": (0.55, 1.07, 0.75, 2.05)}
WALL_LO = (0.00, 0.30, 0.05, 3.70)   # 左墙（近端），已知通到天花板
WALL_HI = (2.78, 0.30, 2.85, 3.70)   # 右墙（远端）


def load(root=None):
    return np.load(os.path.join(root or paths.DATA, CLOUD)).reshape(-1, 3)[:, :3]


def planes(P):
    """天花板与地面：两片水平面的稳健高度。"""
    z = P[:, 2]
    out = {}
    for name, m in (("ceiling", z > 2.0), ("floor", z < 0.06)):
        q = z[m]
        out[name] = {"n": int(m.sum()), "p01": float(np.percentile(q, 1)),
                     "p50": float(np.percentile(q, 50)), "p99": float(np.percentile(q, 99))}
    out["room_height_m"] = out["ceiling"]["p50"] - out["floor"]["p50"]
    return out


def density(P, box):
    """0.1 m 分箱的竖直面相对密度（以 0.2-1.0 m 为 1），用来看点云在哪个高度断掉。"""
    x0, y0, x1, y1 = box
    m = (P[:, 0] > x0) & (P[:, 0] < x1) & (P[:, 1] > y0) & (P[:, 1] < y1)
    h, edges = np.histogram(P[m & (P[:, 2] < 1.98), 2], bins=np.arange(0.0, 2.1, BIN))
    base = h[2:10].sum() / 8.0
    return {"n": int(m.sum()),
            "rel": [round(float(v / base), 2) if base else None for v in h],
            "bin_m": [round(float(e), 1) for e in edges[:-1]]}


def top_plane(P, foot, zmax=1.98):
    """投影内最像「水平顶面」的高度：按 5 cm 薄层算平面覆盖率，取覆盖率最高的一层。"""
    x0, y0, x1, y1 = foot
    m = (P[:, 0] > x0) & (P[:, 0] < x1) & (P[:, 1] > y0) & (P[:, 1] < y1)
    Q = P[m]
    nx, ny = max(1, int((x1 - x0) / CELL)), max(1, int((y1 - y0) / CELL))
    rows = []
    for z0 in np.arange(0.15, zmax, CELL):
        s = Q[(Q[:, 2] >= z0) & (Q[:, 2] < z0 + SLAB)]
        if len(s) < 20:
            continue
        cells = {((px - x0) // CELL, (py - y0) // CELL) for px, py in s[:, :2]}
        rows.append({"z_m": round(float(z0), 2), "n": int(len(s)),
                     "coverage": round(len(cells) / float(nx * ny), 3)})
    return {"footprint_m2": round((x1 - x0) * (y1 - y0), 2), "planes": rows}


def survey(root=None):
    P = load(root)
    out = {"cloud": CLOUD, "points": int(len(P)), "planes": planes(P)}
    out["faces"] = {k: density(P, b) for k, b in FACE.items()}
    out["wall_control"] = {"near_wall": density(P, WALL_LO), "far_wall": density(P, WALL_HI)}
    out["tops"] = {}
    for k, b in FOOT.items():
        t = top_plane(P, b)
        ranked = sorted(t["planes"], key=lambda r: -r["coverage"])[:3]
        out["tops"][k] = dict(t, ranked=ranked)
    return out


def report(out):
    p = out["planes"]
    print("点云 %s  %d 点" % (out["cloud"], out["points"]))
    print("天花板 p50 %.3f m（p01 %.3f / p99 %.3f，n=%d）；地面 p50 %.3f；净高 %.3f m"
          % (p["ceiling"]["p50"], p["ceiling"]["p01"], p["ceiling"]["p99"], p["ceiling"]["n"],
             p["floor"]["p50"], p["room_height_m"]))
    print()
    print("可见上限（0.1 m 分箱相对密度，1.0 = 0.2-1.0 m 的水平）：")
    for k, d in list(out["faces"].items()) + list(out["wall_control"].items()):
        rel = d["rel"]
        top = max((i for i, v in enumerate(rel) if v and v >= 0.25), default=-1)
        print("  %-11s n=%6d  最后一个 >=0.25 的分箱: %.1f m" % (k, d["n"], d["bin_m"][top]))
    print()
    print("投影内覆盖率最高的三层（5 cm 薄层，能否读到顶面就看它）：")
    for k, t in out["tops"].items():
        cells = "  ".join("z=%.2f 覆盖 %.0f%% (n=%d)" % (r["z_m"], 100 * r["coverage"], r["n"]) for r in t["ranked"])
        print("  %-5s 面积 %.2f m²  %s" % (k, t["footprint_m2"], cells or "无候选"))


if __name__ == "__main__":
    res = survey()
    report(res)
    dst = os.path.join(paths.REPO, "output", "layout-recon", "height-survey.json")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    print()
    print("saved", dst)