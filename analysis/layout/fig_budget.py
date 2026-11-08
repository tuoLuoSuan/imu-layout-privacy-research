
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
    ax.set_xlim(-2, 120)
    for o in OBJ:
        ax.annotate(NAMES[o], (96, cur[-1]["hit"][o]), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=6, color=COLORS[o])
    title(ax, "同一批 14 个场景：走得更远，收益因家具而异")
    tw = ax.twinx()
    tw.plot(b, [r["coverage"] for r in cur], "--s", ms=3, lw=1.0, color="#bbbbbb",
            label="占据覆盖率")
    tw.set_ylabel("占据覆盖率（虚线，右轴）", fontproperties=CJK)
    tw.set_ylim(0, 0.65)
    tw.spines["top"].set_visible(False)
    tw.annotate("覆盖面（右轴）", (96, cur[-1]["coverage"]), xytext=(5, -13),
                textcoords="offset points", ha="left", va="center",
                fontsize=6, color="#999999")


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


def panel_c(ax):
    y = D["abstain_yield_TA-U_dispersed"]
    b = [r["budget_m"] for r in y]
    share = [r["allowed_share"] for r in y]
    ax.bar(b, share, width=3.4, color="#8fb3c9", label="允许输出的轴比例（包络 ≤1.0 m）")
    ax.set_xlabel("走过的路程预算（米）", fontproperties=CJK)
    ax.set_ylabel("允许输出的轴比例", fontproperties=CJK)
    ax.set_ylim(0, 1.05)
    ax.set_xlim(-2, 100)
    ax.plot([-2, 100], [1.0, 1.0], ":", color="#bbbbbb")
    for xv, sv in zip(b, share):
        if sv > 0.15:
            ax.annotate("%.0f%%" % (100 * sv), (xv, sv), textcoords="offset points",
                        xytext=(0, 2), ha="center", fontsize=6, fontproperties=CJK)
    title(ax, "弃权规则下真正敢说话的轴：比例不随路程涨")
    ax.text(0.98, 0.92, "允许输出的轴里 100% 都对（各预算一致）", transform=ax.transAxes,
            ha="right", va="top", fontsize=6, fontproperties=CJK, color="#333333")


def main():
    fig, axes = plt.subplots(1, 3, figsize=(10.6, 2.9))
    panel_a(axes[0])
    panel_b(axes[1])
    panel_c(axes[2])
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    save(fig, "../../output/layout-recon/budget-curve.png",
         "活动预算与信息来源：覆盖率高不等于可辨识")


if __name__ == "__main__":
    main()
