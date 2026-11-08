"""Shared final-size styling for descriptive audit figures."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties

HERE = Path(__file__).resolve().parent
plt.rcParams.update({"font.family": ["Arial", "SimSun"], "font.size": 7,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 8, "pdf.fonttype": 42, "svg.fonttype": "none"})
CJK = FontProperties(family=["Arial", "SimSun"])
NAMES = {"bed": "床", "desk": "桌", "cab": "柜/架", "chair": "椅"}
COLORS = {"bed": "#248a85", "desk": "#cc873f", "cab": "#888888", "chair": "#596ba0"}
def read(name):
    return json.loads((HERE / (name + ".json")).read_text(encoding="utf-8"))
def title(ax, text):
    ax.set_title(text, loc="left", fontproperties=CJK)
def save(fig, path, caption):
    fig.suptitle(caption, fontproperties=CJK, fontsize=8)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, facecolor="white")
    fig.savefig(path.with_suffix(".pdf"), facecolor="white")
    fig.savefig(path.with_suffix(".svg"), facecolor="white")
    plt.close(fig)
    print(path.resolve())
