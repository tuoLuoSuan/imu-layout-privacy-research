"""Figure: what actually determines whether an interaction pins a furniture axis."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import exp_span as EX

HERE = Path(__file__).resolve().parent
plt.rcParams.update({"font.family": "sans-serif",
                     "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
                     "axes.unicode_minus": False, "font.size": 8,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 9})
OBJECTS = ("bed", "desk", "cab", "chair")
NAMES = {"bed": "床", "desk": "桌", "cab": "柜", "chair": "椅"}
COLORS = {"bed": "#248a85", "desk": "#cc873f", "cab": "#8a8a8a", "chair": "#596ba0"}
ARMS = [("full", "完整证据", "#3b5b92"), ("single", "只留一个锚点", "#7f97c4"),
        ("collapse", "锚点收成一点（次数不变）", "#d9a24a"), ("drop", "整类证据删掉", "#b03a3a")]


def ablation():
    data = json.loads((HERE / "span_ablation.json").read_text(encoding="utf-8"))
    summary = data["summary"]
    rows = {}
    for obj in OBJECTS:
        # summary keys are "<arm>:<edited class>:<object>"; full/single carry no edited class
        keys = {"full": "full:" + obj, "single": "single:" + obj,
                "collapse": "collapse:%s:%s" % (obj, obj), "drop": "drop:%s:%s" % (obj, obj)}
        rows[obj] = {arm: (summary.get(keys[arm]) or {}).get("hit_rate") for arm, _, _ in ARMS}
    return rows, summary


def sweep():
    return json.loads((HERE / "span_sweep.json").read_text(encoding="utf-8"))["summary"]


def main(out):
    fig, axes = plt.subplots(1, 3, figsize=(13.4, 4.3))
    rows, summary = ablation()

    ax = axes[0]
    height = 0.19
    base = np.arange(len(OBJECTS))
    for k, (key, label, color) in enumerate(ARMS):
        position = base + (1.5 - k) * height
        values = [rows[o][key] for o in OBJECTS]
        drawn = [(y, v) for y, v in zip(position, values) if v is not None]
        ax.barh([y for y, _ in drawn], [v for _, v in drawn], height, label=label, color=color)
        for y, value in drawn:
            ax.text(value + 0.015, y, "%.2f" % value, va="center", fontsize=6.2, color="#333333")
        for y, value in zip(position, values):
            if value is None:
                ax.text(0.02, y, "不适用", va="center", fontsize=6.0, color="#777777")
    ax.set_yticks(base)
    ax.set_yticklabels([NAMES[o] for o in OBJECTS])
    ax.set_xlim(0, 1.55)
    ax.set_xlabel("点估计命中率（中心误差 ≤ 0.5 m）")
    ax.legend(fontsize=6.6, loc="center right", frameon=False)
    ax.set_title("同一条路线、同一覆盖率，只改一类证据", loc="left", pad=6)
    ax.text(0.0, -0.20, "删掉整类→0.00；收成一点不变（床 0.75→0.74，柜 0.32→0.19）",
            transform=ax.transAxes, fontsize=7.2, color="#444444")

    ax = axes[1]
    sw = sweep()
    spans = sorted({float(k.split(":")[1]) for k in sw})
    for obj in ("bed", "cab"):
        xs = [s for s in spans if "%s:%.2f" % (obj, s) in sw]
        ys = [sw["%s:%.2f" % (obj, s)]["median_max_envelope_m"] for s in xs]
        ax.plot(xs, ys, "o-", color=COLORS[obj], label=NAMES[obj] + "（实测支撑包络）")
        extent = {"bed": 2.08, "cab": 1.05}[obj]
        grid = np.linspace(0, max(spans), 60)
        ax.plot(grid, np.maximum(0.0, extent + 2 * 0.20 - grid), "--",
                color=COLORS[obj], alpha=0.55, linewidth=1.1, label=NAMES[obj] + " 闭式 L+2p−span")
    ax.axhline(1.0, color="#b03a3a", linestyle=":", linewidth=1.1)
    ax.text(max(spans) * 0.99, 1.03, "包络 ≤ 1.0 m 才保证 0.5 m", color="#b03a3a",
            fontsize=6.8, ha="right")
    ax.set_xlabel("人为放置的锚点跨度（米）")
    ax.set_ylabel("支撑包络最大边长（米）")
    ax.set_title("反事实：跨度真的能收窄歧义", loc="left", pad=6)
    ax.legend(fontsize=6.4, frameon=False, loc="upper right")
    ax.text(0.0, -0.20, "这是「需要多少证据」的曲线，不是这些路线实际达到的跨度",
            transform=ax.transAxes, fontsize=7.2, color="#444444")

    ax = axes[2]
    req = EX.requirement_report(str(HERE.parents[1] /
        "output/research-sync/2026-11-08-activity-frontier-001/frontier-development.json"))  # padding=0.20
    classes = [o for o in OBJECTS if o in req["classes"]]
    values, notes = [], []
    for obj in classes:
        row = req["classes"][obj]
        share = row["share_meeting_where_requirement_positive"]
        values.append(0.0 if share is None else share)
        notes.append("%.0f%%（%d/%d 条轴）" % (100 * (share or 0.0),
                     row["axes_meeting_where_requirement_positive"],
                     row["axes_with_positive_requirement"]))
    ax.barh(np.arange(len(classes)), values, 0.5, color=[COLORS[o] for o in classes])
    for i, (value, note) in enumerate(zip(values, notes)):
        ax.text(value + 0.012, i, note, va="center", fontsize=6.8, color="#333333")
    ax.set_yticks(np.arange(len(classes)))
    ax.set_yticklabels([NAMES[o] for o in classes])
    ax.invert_yaxis()
    ax.set_xlim(0, 0.55)
    ax.set_xlabel("满足跨度要求的轴比例（只看需求 > 0 的轴）")
    ax.set_title("走满 96 m 时，需要跨度的那条轴达标了吗", loc="left", pad=6)
    ax.text(0.0, -0.20, "床 7%、柜 19%、椅 0%：不是走得不够远，是没人沿物体自己的轴跨过去",
            transform=ax.transAxes, fontsize=7.2, color="#444444")

    fig.suptitle("活动是怎么泄露布局的：接触类型与锚点跨度，而覆盖率不是自变量", fontsize=10)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, facecolor="white")
    fig.savefig(Path(out).with_suffix(".pdf"), facecolor="white")
    fig.savefig(Path(out).with_suffix(".svg"), facecolor="white")
    plt.close(fig)
    print(Path(out).resolve())


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else str(HERE.parents[1] / "output/layout-recon/span-evidence.png"))
