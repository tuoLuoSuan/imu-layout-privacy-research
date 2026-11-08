
"""Frontier figure: what contact span buys (ideal geometry) next to what walking
budgets deliver in generated geometric routes, not a frozen IMU frontend."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import cm
from matplotlib.colors import Normalize

from analysis.layout.figure_style import CJK, NAMES, COLORS, title, save
from analysis.layout import evidence_space as ES, sim_eval as SE, paths

FRACTIONS = (0.0, 0.25, 0.5, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0)
TARGETS = (0.30, 0.40, 0.50, 0.60, 0.75, 0.90, 1.20)
OBJECTS = ("bed", "desk", "cab", "chair")
BUDGETS = (0.0, 8.0, 20.0, 32.0, 48.0, 64.0, 96.0)
STAGE2 = Path(__file__).resolve().with_name('stage2-results.json')
SEED = 18031


def bed_radii():
    """Per-room conditional radius for each contact-spread fraction."""
    out = {}
    scenes = [s for f in sorted(Path(paths.THOR).glob("FloorPlan*.json"))
              if (s := SE.load_scene(str(f)))]
    for index, scene in enumerate(scenes):
        b = np.asarray(scene["gt"]["bed"])
        extent = b[2:] - b[:2]
        fractions = np.random.default_rng(
            np.random.SeedSequence([SEED, index, 31])).uniform(0.1, 0.9, 2)
        for spread in FRACTIONS:
            span = spread * extent
            lower = b[:2] + fractions * (extent - span)
            anchors = lower + np.linspace(0, 1, 3)[:, None] * span
            res = ES.bed_position_envelope([scene["W"], scene["L"]], extent, anchors, 0.20)
            bounds = np.asarray(res["bounds"])
            point = (bounds[:2] + bounds[2:]) / 2
            out.setdefault(spread, []).append(float(ES.envelope_certificate(bounds, point, 0.5)["radius_upper_m"]))
    return out


def panel_a(ax):
    radii = bed_radii()
    X, Y = np.meshgrid(np.array(FRACTIONS) * 100, np.array(TARGETS))
    Z = np.zeros_like(X)
    for j, frac in enumerate(FRACTIONS):
        r = np.array(radii[frac])
        for i, tgt in enumerate(TARGETS):
            Z[i, j] = float(np.mean(r <= tgt))
    cmap = cm.viridis
    norm = Normalize(min(TARGETS), max(TARGETS))
    xs = np.array(FRACTIONS) * 100
    for i, tgt in enumerate(TARGETS):
        hot = abs(tgt - 0.5) < 1e-9
        ax.plot(xs, np.full_like(xs, tgt), Z[i], color="#d62728" if hot else cmap(norm(tgt)),
                lw=1.9 if hot else 1.1, zorder=6 if hot else 3,
                marker="o" if hot else None, ms=2.4)
        ax.plot(xs, np.full_like(xs, tgt), np.zeros_like(xs), color="0.82", lw=0.5, zorder=1)
        if hot:
            for xv, zv in ((75.0, 0.07), (90.0, 0.93), (100.0, 1.0)):
                ax.text(xv, tgt + 0.06, zv + 0.04, "%.2f" % zv, fontproperties=CJK,
                        fontsize=6, color="#d62728", ha="center")
    ax.set_xlabel("三次接触的跨度 / 床在该轴的尺寸（%）", fontproperties=CJK, labelpad=3)
    ax.set_ylabel("愿意接受的中心误差（米）", fontproperties=CJK, labelpad=3)
    ax.set_yticks(list(TARGETS))
    ax.set_yticklabels(["%g" % t for t in TARGETS], fontproperties=CJK, fontsize=6)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlim(0, 100)
    ax.set_ylim(min(TARGETS), max(TARGETS))
    ax.set_zlabel("14 个场景里达标的房间比例", fontproperties=CJK, labelpad=3)
    ax.set_zlim(0, 1)
    ax.view_init(elev=24, azim=-60)
    ax.tick_params(labelsize=6)
    title(ax, "机制：跨度换分辨率（理想几何、只有床）")
    ax.text2D(0.00, 0.92, "红线 = 目标 0.5 m：跨度 75% 起才抬头（0.07→0.93 在 90%）。",
              transform=ax.transAxes, fontproperties=CJK, fontsize=6, color="#333333")


def panel_b(ax):
    data = json.load(open(STAGE2, encoding="utf-8"))["budget_curves"]["curves"]["TA-U/dispersed"]
    by_budget = {float(row["budget_m"]): row for row in data}
    cmap = cm.viridis
    norm = Normalize(0, 1)
    for yi, obj in enumerate(OBJECTS):
        for xi, bud in enumerate(BUDGETS):
            row = by_budget.get(bud)
            if row is None:
                continue
            v = float(row["hit"][obj])
            ax.bar3d(xi + 0.1, yi + 0.1, 0, 0.8, 0.8, v,
                     color=cmap(norm(v)), edgecolor="0.3", linewidth=0.3, shade=True)
    ax.set_xticks(np.arange(len(BUDGETS)) + 0.5)
    ax.set_xticklabels(["%g" % b for b in BUDGETS], fontproperties=CJK, fontsize=6)
    ax.set_yticks(np.arange(len(OBJECTS)) + 0.5)
    ax.set_yticklabels([NAMES.get(o, o) for o in OBJECTS], fontproperties=CJK, fontsize=6)
    ax.set_xlabel("走过的路程预算（米）", fontproperties=CJK, labelpad=3)
    ax.set_ylabel("家具", fontproperties=CJK, labelpad=3)
    ax.set_zlabel("命中率（中心误差 ≤0.5 m）", fontproperties=CJK, labelpad=3)
    ax.set_zlim(0, 1)
    ax.view_init(elev=24, azim=-60)
    ax.tick_params(axis="z", labelsize=6)
    title(ax, "几何模拟：路程与点命中（14 开发场景，TA-U）")
    ax.text2D(0.00, 0.92, "床 0.07→0.93（32 m 起）、椅 0→1.00（12 m 起）、柜 0→0.50、桌 0.07→0.14。",
              transform=ax.transAxes, fontproperties=CJK, fontsize=6, color="#333333")


def main():
    fig = plt.figure(figsize=(7.8, 3.4))
    ax1 = fig.add_subplot(1, 2, 1, projection="3d")
    ax2 = fig.add_subplot(1, 2, 2, projection="3d")
    panel_a(ax1)
    panel_b(ax2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.90))
    save(fig, Path(paths.REPO)/'output/layout-recon/frontier-3d-audited.png',
         "几何开发诊断：条件中心半径（左）与点命中率（右），两者判据不同")


if __name__ == "__main__":
    main()
