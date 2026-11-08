"""Figure: what a desk channel (bounds from the seated anchors) buys and costs."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
plt.rcParams.update({"font.family": "sans-serif",
                     "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
                     "axes.unicode_minus": False, "font.size": 8,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 9})
REACH_LABEL = {"None": "无桌面通道", "1.0": "1.0 m", "1.5": "1.5 m", "2.0": "2.0 m", "3.0": "3.0 m"}


def main(out):
    data = json.loads((HERE / "desk_channel.json").read_text(encoding="utf-8"))
    keys = [k for k in ("None", "1.0", "1.5", "2.0", "3.0") if k in data["summary"]]
    labels = [REACH_LABEL[k] for k in keys]
    support = [data["summary"][k]["support_median_m"] for k in keys]
    hit = [100 * (data["summary"][k]["hit_rate"] or 0.0) for k in keys]
    error = [data["summary"][k]["error_median_m"] for k in keys]

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.9))
    x = np.arange(len(keys))
    ax = axes[0]
    ax.bar(x, support, 0.55, color="#596ba0")
    for xi, value in zip(x, support):
        ax.text(xi, value + 0.08, "%.2f m" % value, ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_ylabel("桌中心支持包络（米）")
    ax.set_title("加一条「坐在桌前」的通道，歧义确实减半", loc="left", pad=6)
    ax.text(0.0, -0.22, "坐点约束把 5.0 m 压到 2.4 m（reach 1.0 m）", transform=ax.transAxes,
            fontsize=7.2, color="#444444")

    ax = axes[1]
    ax.plot(x, hit, "o-", color="#248a85", label="命中率（≤0.5 m）")
    ax.set_ylim(0, 45)
    ax.set_ylabel("命中率（%）", color="#248a85")
    ax.tick_params(axis="y", labelcolor="#248a85")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_xlabel("坐点到达桌框的最大允许距离")
    ax2 = ax.twinx()
    ax2.plot(x, error, "s--", color="#b03a3a", label="误差中位")
    ax2.set_ylabel("误差中位（米）", color="#b03a3a")
    ax2.tick_params(axis="y", labelcolor="#b03a3a")
    ax2.set_ylim(0, 2.8)
    counts = [int(round(data["summary"][k]["hit_rate"] * data["summary"][k]["n"])) for k in keys]
    for xi, value, count in zip(x, hit, counts):
        ax.text(xi, value + 1.6, "%d/%d" % (count, data["summary"]["None"]["n"]), ha="center",
                fontsize=7, color="#248a85")
    ax.set_title("但点估计没救回来：误差中位仍在 1.2 m 以上", loc="left", pad=6)
    ax.text(0.0, -0.28, "「桌在坐点 2 m 内」只在 12/14 场景成立；成立也救不回精度", transform=ax.transAxes,
            fontsize=7.2, color="#444444")

    fig.suptitle("桌：给它补一条接触通道，能收窄区域，但收不回精度", fontsize=10)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, facecolor="white")
    fig.savefig(Path(out).with_suffix(".pdf"), facecolor="white")
    plt.close(fig)
    print(Path(out).resolve())


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else str(HERE.parents[1] / "output/layout-recon/desk-channel.png"))
