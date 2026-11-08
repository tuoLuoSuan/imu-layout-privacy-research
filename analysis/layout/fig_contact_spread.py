"""Figure: the same spread manipulation helps, does nothing, or hurts, by contact type."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import rcParams
from matplotlib.font_manager import FontProperties

rcParams["font.family"] = "sans-serif"
rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
rcParams["axes.unicode_minus"] = False
CJK = FontProperties(family=["Microsoft YaHei", "SimHei"])
NAMES = {"bed": "床", "cab": "柜/架", "chair": "椅"}
COLORS = {"bed": "#248a85", "cab": "#888888", "chair": "#596ba0"}
FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)


def run(data="analysis/layout/contact_spread.json", out="output/layout-recon/contact-spread.png"):
    d = json.loads(Path(data).read_text(encoding="utf-8"))
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.3))
    for obj, label in NAMES.items():
        hits, sups = [], []
        for f in FRACTIONS:
            s = d["summary"].get("%s:f%g" % (obj, f))
            hits.append(np.nan if s is None else s["hit_rate"])
            sups.append(np.nan if s is None or s["support_median_m"] is None else s["support_median_m"])
        for ax, series in ((axes[0], hits), (axes[1], sups)):
            ax.plot(FRACTIONS, series, "o-", color=COLORS[obj], label=label, lw=1.8, ms=5)
    for ax in axes:
        ax.set_xlabel("三个接触点沿物体自身长轴摊开的比例", fontproperties=CJK, fontsize=10)
        ax.grid(alpha=.25)
        ax.set_xticks(list(FRACTIONS))
        ax.set_xticklabels(["0（重复）", "25%", "50%", "75%", "100%"], fontproperties=CJK, fontsize=8.5)
        ax.legend(prop=CJK, fontsize=9, loc="center right")
    axes[0].set_ylabel("点命中率（中心≤0.5 m）", fontproperties=CJK, fontsize=10)
    axes[0].set_ylim(-0.05, 1.05)
    axes[0].set_xlim(-0.04, 1.16)
    axes[0].set_title("命中率：床随摊开变好，椅随摊开变坏", fontproperties=CJK, fontsize=11)
    axes[0].annotate("椅 75% 起整批冲突（无输出）", xy=(0.75, 0.0), xytext=(0.36, 0.12),
                     fontproperties=CJK, fontsize=8.5, color=COLORS["chair"],
                     arrowprops=dict(arrowstyle="->", color=COLORS["chair"], lw=0.8))
    axes[0].annotate("13/14 只是选对了，包络仍 1.38 m", xy=(1.0, 0.93), xytext=(0.55, 1.0),
                     fontproperties=CJK, fontsize=8.5, color=COLORS["bed"],
                     arrowprops=dict(arrowstyle="->", color=COLORS["bed"], lw=0.8))
    axes[1].set_ylabel("支撑包络中位（米）", fontproperties=CJK, fontsize=10)
    axes[1].set_title("歧义：床/柜收窄，椅在 75% 处整批冲突", fontproperties=CJK, fontsize=11)
    fig.text(0.5, 0.005,
             "同一条路线、同一覆盖、每类固定 3 个接触点，只有摊开程度变化；桌没有任何接触事件，"
             "这条干预对它无从施加（14 个开发几何场景，非原始 IMU）",
             ha="center", fontproperties=CJK, fontsize=8, color="#555")
    fig.suptitle("接触证据的形状，而不是走多远：同一个干预在三种接触类型上符号相反",
                 fontproperties=CJK, fontsize=12)
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, facecolor="white")
    fig.savefig(path.with_suffix(".pdf"), facecolor="white")
    print(path.resolve())
    plt.close(fig)


if __name__ == "__main__":
    run()
