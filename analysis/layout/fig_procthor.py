"""Does the frozen activity threshold transfer to another house generator?

The eleven-room boundary was measured on AI2-THOR.  ProcTHOR provides rooms the
decoder never saw.  This figure puts the two side by side on the five
pre-registered cells, then breaks the external result down by object and by the
official split, because a single pooled rate hides where it fails.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130

# Reference cells from the AI2-THOR eleven-room study (RESULTS section 13).
ITHOR = {(0.94, 5): (9, 11), (0.95, 4): (8, 11), (0.95, 5): (11, 11),
         (0.98, 2): (9, 11), (0.95, 6): (11, 11)}
LABELS = {(0.94, 5): "94% / 5", (0.95, 4): "95% / 4", (0.95, 5): "95% / 5",
          (0.98, 2): "98% / 2", (0.95, 6): "95% / 6"}
ORDER = [(0.95, 5), (0.95, 4), (0.95, 6), (0.94, 5), (0.98, 2)]
TOL = 0.5


def per_object(raw_path):
    rows = [r for r in json.load(open(raw_path, encoding="utf-8"))["rows"]
            if r.get("status") != "invalid_geometry" and r["policy"] == "dispersed"]
    out = {}
    for (cov, vis) in ORDER:
        part = [r for r in rows if r.get("executable") and r["visits"] == vis
                and r["coverage_target"] == cov]
        rec = {}
        for obj in ("bed", "desk", "cab", "chair"):
            hits = sum(1 for r in part if r["objects"].get(obj, {}).get("joint_error_m") is not None
                       and r["objects"][obj]["joint_error_m"] <= TOL)
            rec[obj] = (hits, len(part))
        out["%0.2f|%d" % (cov, vis)] = rec
    return out


def by_split(record):
    meta = {m["house_id"]: m for m in record["house_meta"]}
    out = {}
    for name, cells in record["per_house"].items():
        split = meta.get(name.replace("FloorPlan_", ""), {}).get("split", "?")
        out.setdefault(split, []).append(cells)
    return out


def render(data_path, out_png):
    rec = json.load(open(data_path, encoding="utf-8"))
    summ = {(s["coverage"], s["visits"]): s for s in rec["summary"]}
    fig, axes = plt.subplots(1, 3, figsize=(15.6, 4.9), gridspec_kw={"width_ratios": [1.15, 1.0, 0.95]})

    ax = axes[0]
    x = np.arange(len(ORDER))
    ext = [summ[c]["hits"] / max(summ[c]["rooms"], 1) * 100 for c in ORDER]
    ref = [ITHOR[c][0] / ITHOR[c][1] * 100 for c in ORDER]
    ax.bar(x - 0.19, ref, width=0.38, color="#9ecae1", label="AI2-THOR 11 间（开发集）")
    ax.bar(x + 0.19, ext, width=0.38, color="#d62728", label="ProcTHOR 矩形外部房（%d 栋）" % rec["houses"])
    for i, (a, b) in enumerate(zip(ref, ext)):
        ax.text(i - 0.19, a + 2, "%d%%" % round(a), ha="center", fontsize=8)
        ax.text(i + 0.19, b + 2, "%d%%" % round(b), ha="center", fontsize=8, color="#a50f15")
    ax.set_xticks(x)
    ax.set_xticklabels([LABELS[c] for c in ORDER])
    ax.set_ylim(0, 112)
    ax.set_ylabel("四件中心全中率（%）")
    ax.set_xlabel("覆盖 / 分散交互次数")
    ax.set_title("(a) 同一条冻结阈值，换一个生成器就掉一半\n顺序也变了：外部房上 98%/2 反而最高", fontsize=10)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(axis="y", alpha=0.3)

    ax = axes[1]
    obj = per_object(rec["raw_path"])
    keys = ["bed", "desk", "cab", "chair"]
    names = {"bed": "床", "desk": "桌", "cab": "储物", "chair": "椅"}
    w = 0.2
    for j, (cov, vis) in enumerate([(0.95, 5), (0.98, 2)]):
        recs = obj["%0.2f|%d" % (cov, vis)]
        vals = [recs[k][0] / max(recs[k][1], 1) * 100 for k in keys]
        ax.bar(np.arange(len(keys)) + (j - 0.5) * 0.36, vals, width=0.34,
               color=["#3182bd", "#e6550d"][j], label=LABELS[(cov, vis)])
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels([names[k] for k in keys])
    ax.set_ylim(0, 105)
    ax.set_ylabel("该类中心误差 ≤0.5 m 的比例（%）")
    ax.set_title("(b) 掉得最多的是桌：它本来就没有接触通道\n床 / 椅 / 储物都在 93% 以上", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)

    ax = axes[2]
    split = by_split(rec)
    order = [s for s in ("train", "val", "test") if s in split]
    vals = []
    for s in order:
        rows = split[s]
        hits = sum(1 for r in rows if r.get("0.95|5"))
        vals.append(hits / max(len(rows), 1) * 100)
    ax.bar(range(len(order)), vals, color=["#74c476", "#fd8d3c", "#6baed6"][:len(order)])
    for i, v in enumerate(vals):
        ax.text(i, v + 2, "%.0f%% (n=%d)" % (v, len(split[order[i]])), ha="center", fontsize=8)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order)
    ax.set_ylim(0, 105)
    ax.set_ylabel("95%/5 次 的全中率（%）")
    ax.set_title("(c) 按官方 split 拆开：\n三份都远低于开发集的 100%", fontsize=10)
    ax.grid(axis="y", alpha=0.3)

    fig.suptitle("冻结阈值在 ProcTHOR 千房上的外推检验：机制没有原样迁移", fontsize=12)
    fig.tight_layout(rect=(0, 0.02, 1, 0.93))
    fig.savefig(out_png, facecolor="white")
    for ext_ in (".pdf", ".svg"):
        fig.savefig(os.path.splitext(out_png)[0] + ext_, facecolor="white")
    plt.close(fig)
    return out_png


if __name__ == "__main__":
    data = sys.argv[1] if len(sys.argv) > 1 else "output/layout-recon/procthor-threshold-full.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "output/layout-recon/procthor-threshold.png"
    print(render(data, out))
