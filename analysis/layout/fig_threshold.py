"""Two-dimensional replacement for the 3D activity surface.

The 3D surface hid its own numbers: the boundary cell could not be read off the
projection, the two axes are unequal-interval samples plotted as if continuous,
and a censored cell was drawn exactly like a cell that was evaluated and failed.
This figure puts the same data on a grid with the counts printed in every cell,
plus the marginal curves that show which axis is actually binding.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

from analysis.layout.exp_threshold_fine import COVERAGES, VISITS, NORMAL

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _rate(rec, cov, vis, policy="dispersed", scope="grid_normal"):
    cell = rec[scope]["%s|%.2f|%d" % (policy, cov, vis)]
    return cell["hits"], cell["rooms"]


def panel_grid(ax, rec):
    hits = np.array([[rec["grid_normal"]["dispersed|%.2f|%d" % (c, v)]["hits"] for c in COVERAGES] for v in VISITS])
    rooms = np.array([[rec["grid_normal"]["dispersed|%.2f|%d" % (c, v)]["rooms"] for c in COVERAGES] for v in VISITS])
    rate = hits / np.maximum(rooms, 1)
    im = ax.imshow(rate, cmap="viridis", vmin=0, vmax=1, origin="lower", aspect="auto")
    for i in range(len(VISITS)):
        for j in range(len(COVERAGES)):
            ax.text(j, i, "%d/%d" % (hits[i, j], rooms[i, j]), ha="center", va="center",
                    color="white" if rate[i, j] < 0.72 else "black", fontsize=9)
    ax.set_xticks(range(len(COVERAGES)))
    ax.set_xticklabels(["%.0f%%" % (c * 100) for c in COVERAGES], fontsize=8)
    ax.set_yticks(range(len(VISITS)))
    ax.set_yticklabels([str(v) for v in VISITS])
    ax.set_xlabel("行走覆盖目标（占全部可行走空地）")
    ax.set_ylabel("独立交互次数")
    ax.set_title("(a) 11 间受限普通单间，四件中心均 ≤0.5 m\n格内为命中/分母，分母恒为 11", fontsize=10)
    j95 = COVERAGES.index(0.95)
    i5 = VISITS.index(5)
    ax.add_patch(Rectangle((j95 - 0.5, i5 - 0.5), 1, 1, fill=False, ec="#d62728", lw=2.4))
    ax.plot([j95], [i5], marker="o", ms=4, color="#d62728")
    j98 = COVERAGES.index(0.98)
    i2 = VISITS.index(2)
    ax.add_patch(Rectangle((j98 - 0.5, i2 - 0.5), 1, 1, fill=False, ec="#ff7f0e", lw=1.6, ls="--"))
    j94 = COVERAGES.index(0.94)
    ax.add_patch(Rectangle((j94 - 0.5, i5 - 0.5), 1, 1, fill=False, ec="#ff7f0e", lw=1.6, ls="--"))
    cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label("命中率", fontsize=8)
    cb.ax.tick_params(labelsize=7)


def panel_curves(ax, rec):
    cov = np.array(COVERAGES) * 100
    series = [
        (2, "dispersed", "分散交互 2 次", "#1f77b4", "-"),
        (5, "dispersed", "分散交互 5 次", "#2ca02c", "-"),
        (6, "repeat", "同点重复 6 次", "#d62728", "--"),
    ]
    for vis, policy, label, color, ls in series:
        y = np.array([_rate(rec, c, vis, policy)[0] / 11 for c in COVERAGES])
        ax.plot(cov, y * 100, ls, color=color, lw=2, marker="o", ms=4, label=label)
    ax.axhline(80, color="gray", lw=1, ls=":")
    ax.text(cov[0], 82, "80% 判据", fontsize=8, color="gray")
    for x, y, txt in [(95, 100, "95% / 5 次"), (98, 81.8, "98% / 2 次")]:
        ax.plot([x], [y], marker="*", ms=12, color="#d62728")
        ax.annotate(txt, (x, y), textcoords="offset points", xytext=(-6, 8), fontsize=8, color="#d62728")
    ax.set_xlabel("行走覆盖目标（%）")
    ax.set_ylabel("四件全中率的房间比例（%）")
    ax.set_ylim(-3, 108)
    ax.set_title("(b) 覆盖率是主要约束，访次在 2–4 次之间完全饱和\n同点重复在测过的每一格都到不了 11/11", fontsize=10)
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3)


def panel_rooms(ax, rec):
    rows = rec["cabinet_at_4_vs_5_visits"]
    names = [r["scene"].replace("FloorPlan", "FP") for r in rows]
    e4 = [r["4"]["cab_error_m"] if r.get("4") and r["4"]["cab_error_m"] is not None else np.nan for r in rows]
    e5 = [r["5"]["cab_error_m"] if r.get("5") and r["5"]["cab_error_m"] is not None else np.nan for r in rows]
    x = np.arange(len(rows))
    ax.plot([x - 0.08, x + 0.08], [e4, e5], color="gray", lw=1, zorder=1)
    ax.scatter(x - 0.08, e4, s=38, color="#1f77b4", label="4 次交互", zorder=3)
    ax.scatter(x + 0.08, e5, s=38, color="#2ca02c", label="5 次交互", zorder=3)
    ax.axhline(0.5, color="#d62728", lw=1.2, ls="--")
    ax.text(0.02, 0.52, "0.5 m 判据", fontsize=8, color="#d62728")
    for i, r in enumerate(rows):
        if r.get("4") and r.get("5") and r["4"]["cab_error_m"] and r["4"]["cab_error_m"] > 0.5 >= (r["5"]["cab_error_m"] or 0):
            ax.annotate("第 2 个柜面接触\n间距 %d cm" % round(100 * max(r["5"]["cab_contact_span_m"] or [0, 0])),
                        (i + 0.08, r["5"]["cab_error_m"]), textcoords="offset points",
                        xytext=(8, 14), fontsize=7.5, color="#2ca02c")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("柜中心误差（m）")
    ax.set_title("(c) 第 5 次交互只对 3 间房起作用，且全部来自柜\n那 3 间的柜面两点相距 12–25 cm", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)


def render(data_path, out_png):
    rec = load(data_path)
    fig, axes = plt.subplots(1, 3, figsize=(15.4, 4.8), gridspec_kw={"width_ratios": [1.15, 1.15, 1.3]})
    panel_grid(axes[0], rec)
    panel_curves(axes[1], rec)
    panel_rooms(axes[2], rec)
    fig.suptitle("活动阈值在细网格上的重测：覆盖率是台阶，访次只在特定房间起作用", fontsize=12)
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    fig.savefig(out_png, facecolor="white")
    for ext in (".pdf", ".svg"):
        fig.savefig(os.path.splitext(out_png)[0] + ext, facecolor="white")
    plt.close(fig)
    return out_png


if __name__ == "__main__":
    data = sys.argv[1] if len(sys.argv) > 1 else "analysis/layout/threshold_fine.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "output/layout-recon/threshold-fine.png"
    print(render(data, out))
