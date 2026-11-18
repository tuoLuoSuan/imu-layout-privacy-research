"""Render the public quantitative panels and matched synthetic layouts as PDFs."""

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "reproducibility"
PRIMARY = ROOT / "output/layout-recon/recovery088/confirmation50-98001"
ARMS = {
    "spatial_zero088": ("RoomTrace", "#147971"),
    "corrected_static": ("Geometry-only", "#626973"),
}
REFERENCE = "#ad671c"


def read_csv(name):
    with (DATA / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def finish(fig, path):
    fig.savefig(path)
    plt.close(fig)


def surface(name, metric, out, ci=None):
    rows = read_csv(name)
    values = {(r["arm"], float(r["coverage"]), int(r["contacts"])): float(r["mean_percent"])
              for r in rows}
    coverages = sorted({float(row["coverage"]) for row in rows if float(row["coverage"]) > 0})
    contacts = sorted({int(row["contacts"]) for row in rows})
    x, y = np.meshgrid(np.array(coverages) * 100, contacts)
    fig = plt.figure(figsize=(10, 3.1), layout="constrained")
    fig.get_layout_engine().set(wspace=0.07)
    ax = fig.add_subplot(1, 3, 1, projection="3d")
    heat = fig.add_subplot(1, 3, 2)
    slice_ax = fig.add_subplot(1, 3, 3)
    layers = {}
    for arm, (label, color) in ARMS.items():
        z = np.array([[values[arm, c, k] for c in coverages] for k in contacts])
        layers[arm] = z
        ax.plot_wireframe(x, y, z, color=color, linewidth=0.85)
        if (arm, 0, 0) in values:
            ax.scatter(0, 0, values[arm, 0, 0], marker="D", color=color, s=15)
        slice_ax.plot(contacts, z[:, -1], "o-", color=color, label=label)
        if ci:
            ordered = sorted((r for r in ci if r["arm"] == arm), key=lambda r: r["contacts"])
            slice_ax.fill_between(contacts, [r["low"] for r in ordered],
                                  [r["high"] for r in ordered], color=color, alpha=0.12)
    ax.set(xlabel="Walking coverage (%)", ylabel="Contacts", title=metric, zlim=(0, 100),
           xlim=(-6, 106), yticks=contacts)
    ax.set_xticks([0, *[int(100*c) for c in coverages]])
    ax.tick_params(axis="x", labelsize=6 if len(coverages) > 5 else 8, pad=0)
    ax.view_init(elev=24, azim=-58)
    ax.grid(False)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_visible(False)
    delta = (layers["spatial_zero088"] - layers["corrected_static"]).T
    color_min = min(0, float(delta.min()))
    image = heat.imshow(delta, cmap="YlGnBu", aspect="auto", origin="lower", vmin=color_min)
    fig.colorbar(image, ax=heat, label="RoomTrace gain (pp)", shrink=0.8)
    heat.set(xlabel="Contacts", ylabel="Walking coverage (%)", xticks=range(len(contacts)),
             xticklabels=contacts, yticks=range(len(coverages)),
             yticklabels=[int(c*100) for c in coverages])
    for i, row in enumerate(delta):
        for j, value in enumerate(row):
            heat.text(j, i, f"{value:+.1f}", ha="center", va="center",
                      fontsize=7, color="white" if value > 0.66 * delta.max() else "#192b37")
    slice_ax.set(xlabel="Contacts at full coverage", ylabel=metric, ylim=(0, 100), xticks=contacts)
    slice_ax.legend(frameon=False, loc="lower right")
    finish(fig, out)


def layout_panel(out):
    manifest = {r["id"]: r for r in read_json(PRIMARY / "manifest.json")["rows"]}
    ids = read_json(DATA / "case-selection.json")["ids"]
    rows_path = PRIMARY.with_name(PRIMARY.name + "-eval") / "rows.jsonl"
    predictions = {}
    with rows_path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["id"] in ids and row["arm"] in ARMS:
                predictions[row["id"], row["arm"]] = row["boxes"]
    fig, axes = plt.subplots(len(ids), 3, figsize=(8.5, 7), layout="constrained")
    columns = ["Reference and evidence", "corrected_static", "spatial_zero088"]
    for ix, id in enumerate(ids):
        entry = manifest[id]
        obs = read_json(PRIMARY / entry["input"])
        truth = read_json(PRIMARY / entry["target"])["boxes"]
        width, height = obs["room"]
        labels = {"bed": "B", "desk": "D", "cab": "C", "chair": "Ch"}
        for j, arm in enumerate(columns):
            ax = axes[ix, j]
            ax.set(xlim=(0, width), ylim=(0, height), aspect="equal", xticks=[], yticks=[])
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_linewidth(0.6)
            if ix == 0:
                ax.set_title(ARMS[arm][0] if arm in ARMS else arm)
            if j == 0:
                ax.set_ylabel(f'{entry["coverage_target"]:.0%} · {entry["contacts_requested"]} contacts')
                walk = np.asarray(obs["walk"])
                if len(walk):
                    ax.scatter(*walk.T, color="#889199", s=3, alpha=0.55)
                for event in obs["events"]:
                    ax.plot(*event["pos"], ".", color=REFERENCE, ms=7, zorder=4)
            boxes = truth if j == 0 else predictions[id, arm]
            color = REFERENCE if j == 0 else ARMS[arm][1]
            for key, (x0, y0, x1, y1) in boxes.items():
                ax.add_patch(Rectangle((x0, y0), x1-x0, y1-y0, ec=color, fc=color, alpha=0.18))
                ax.add_patch(Rectangle((x0, y0), x1-x0, y1-y0, ec=color, fill=False))
                ax.text((x0+x1)/2, (y0+y1)/2, labels[key.split("#")[0]],
                        ha="center", va="center", fontsize=7)
    fig.supxlabel("B  bed      D  desk      C  cabinet      Ch  chair", fontsize=8)
    finish(fig, out)


def bar_panel(out, rows, labels, value, ylabel, limit, mean=False):
    fig, ax = plt.subplots(figsize=(5.2, 2.7), layout="constrained")
    values = [float(r[value]) for r in rows]
    bars = ax.bar(range(len(values)), values, color="#147971", width=0.65)
    ax.bar_label(bars, fmt="%.3f" if mean else "%.2f", padding=3)
    ax.set(xticks=range(len(values)), xticklabels=labels, ylim=(0, limit), ylabel=ylabel)
    if mean:
        ax.axhline(np.mean(values), color="#626973", linestyle="-.", linewidth=1.0,
                   label=f"Mean {np.mean(values):.3f} m")
        ax.legend(frameon=False)
    finish(fig, out)


def class_panel(out):
    rows = read_csv("class-localisation-by-coverage058.csv")
    classes = list(dict.fromkeys(r["class"] for r in rows))
    fig, axes = plt.subplots(1, len(classes), figsize=(9, 2.8), sharey=True, layout="constrained")
    for ax, key in zip(axes, classes):
        ax.set(title=key, xlabel="Coverage (%)", ylim=(0, 1))
        for arm, (_, color) in ARMS.items():
            block = sorted((r for r in rows if r["arm"] == arm and r["class"] == key),
                           key=lambda r: float(r["coverage"]))
            x = [100*float(r["coverage"]) for r in block]
            ax.plot(x, [float(r["miss_rate"]) for r in block], "o-", color=color)
            ax.fill_between(x, [float(r["ci_low"]) for r in block],
                            [float(r["ci_high"]) for r in block], color=color, alpha=0.15)
    axes[0].set_ylabel("Localization miss rate")
    handles = [Line2D([0], [0], color=color, label=label) for label, color in ARMS.values()]
    axes[-1].legend(handles=handles, frameon=False, fontsize=8)
    finish(fig, out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    plt.rcParams.update({"pdf.fonttype": 42, "font.size": 8, "axes.spines.top": False,
                        "axes.spines.right": False})
    surface("quarter-f1-surface.csv", "Position F1 (%)", args.out / "fig3-position-f1.pdf",
            read_json(DATA / "full-coverage-ci059.json"))
    surface("quarter-whole_room-surface.csv", "Complete room (%)", args.out / "supp-centers.pdf")
    surface("quarter-whole_footprint-surface.csv", "Complete footprint (%)", args.out / "supp-footprints.pdf")
    surface("dense-eight-f1-surface.csv", "Position F1 (%)", args.out / "supp-dense-f1.pdf")
    layout_panel(args.out / "fig4-matched-layouts.pdf")
    rows = read_csv("real-dorm-errors.csv")
    bar_panel(args.out / "fig5-dorm-errors.pdf", rows, [r["object"] for r in rows],
              "error_m", "Center error (m)", 0.5, mean=True)
    activity = read_csv("activity-development.csv")
    labels = [f'{r["direction"]}\n{r["class"]}' for r in activity]
    bar_panel(args.out / "supp-activity.pdf", activity, labels, "f1", "Class F1", 1.12)
    class_panel(args.out / "supp-class-localization.pdf")


if __name__ == "__main__":
    main()
