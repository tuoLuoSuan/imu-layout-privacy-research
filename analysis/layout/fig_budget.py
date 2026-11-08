
"""Two panels: how the layout responds to the walking budget, and what each
information source contributes at a fixed budget."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from figure_style import CJK, NAMES, COLORS, read, title, save

D = read("budget_curve")
OBJ = ("bed", "desk", "cab", "chair")
ARM_LABEL = {"P-U": "先验（不知贴哪面墙）", "T-U": "只给轨迹", "A-U": "只给动作",
             "TA-U": "轨迹+动作", "TA-K": "轨迹+动作+已知贴墙"}
ARMS = ("P-U", "T-U", "A-U", "TA-U", "TA-K")


def panel_a(ax):
    cur = D["curves"]["TA-U/dispersed"]
    b = [r["budget_m"] for r in cur]
    for o in OBJ:
        y = [r["hit"][o] for r in cur]
        ax.plot(b, y, "-o", ms=3, lw=1.2, color=COLORS[o], label=NAMES[o])
    ax.set_xlabel("走过的路程预算（米）", fontproperties=CJK)
    ax.set_ylabel("点估计命中率（中心误差 ≤ 0.5 m）", fontproperties=CJK)
    ax.set_ylim(-0.03, 1.05)
    ax.set_xlim(-2, 100)
    title(ax, "同一批 14 个场景：走得更远，收益因家具而异")
    tw = ax.twinx()
    tw.plot(b, [r["coverage"] for r in cur], "--s", ms=3, lw=1.0, color="#bbbbbb",
            label="占据覆盖率")
    tw.set_ylabel("占据覆盖率（虚线，右轴）", fontproperties=CJK)
    tw.set_ylim(0, 0.65)
    tw.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = tw.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", prop=CJK, fontsize=6, frameon=False,
              handlelength=1.4, borderaxespad=0.2)


def panel_b(ax):
    abl = D["ablation_at_96_dispersed"]
    x = np.arange(len(OBJ))
    w = 0.16
    for i, arm in enumerate(ARMS):
        d = abl[arm]
        vals = [d["hit"][o] for o in OBJ]
        ax.bar(x + (i - 2) * w, vals, w, label=ARM_LABEL[arm],
               color=["#cfd8e3", "#9fb3c8", "#6b8cae", "#2f5d8a", "#c0504d"][i])
    ax.set_xticks(x)
    ax.set_xticklabels([NAMES[o] for o in OBJ], fontproperties=CJK)
    ax.set_ylim(0, 1.34)
    ax.set_ylabel("命中率（96 m，分散策略）", fontproperties=CJK)
    title(ax, "固定 96 m：动作贡献几乎全部增益，先验单独为零")
    ax.legend(prop=CJK, fontsize=6, frameon=False, ncol=2, loc="upper left",
              handlelength=1.4, borderaxespad=0.2, columnspacing=1.0)


def main():
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.9))
    panel_a(axes[0])
    panel_b(axes[1])
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    save(fig, "../../output/layout-recon/budget-curve.png",
         "活动预算与信息来源：覆盖率高不等于可辨识")


if __name__ == "__main__":
    main()
