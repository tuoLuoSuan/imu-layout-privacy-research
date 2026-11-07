"""2.5D dense semantic map for one reconstructed room.

Horizontal extent comes from the IMU pipeline (layout_solver boxes).  Height is
never observed -- it is a category prior, so every object also reports what the
prior alone would have predicted and how far that is from this room's actual
height.  Usage:  python -m analysis.layout.dense_map <session>
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager as fm
from matplotlib.colors import LightSource
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import height_prior as HP
import paths

CJK = fm.FontProperties(fname=r"C:/Windows/Fonts/msyh.ttc")
LABEL = {"bed": ("床", "Bed"), "desk": ("桌", "Desk"), "cab": ("柜", "Cabinet"), "chair": ("椅", "Chair")}
COLOR = {"bed": "#4c9f70", "desk": "#3f7fbf", "cab": "#c98a3a", "chair": "#b35c6b"}
# 本房间的实测/常识高度（用户确认床高 50 cm）。没有这一步，地图只能用类别先验。
ACTUAL = {"s-59d570ee": {"bed": 0.50, "desk": 0.75, "cab": 0.75, "chair": 0.45}}


def height_field(pred, heights, grid=0.02):
    """Rasterise the boxes into a height field; every filled cell is prior-filled vertically."""
    W, L = pred["room"]
    nx, ny = int(round(W / grid)), int(round(L / grid))
    H = np.zeros((ny, nx))
    owner = np.full((ny, nx), "", dtype=object)
    for k, b in pred["boxes"].items():
        i0, i1 = int(round(b[0] / grid)), int(round(b[2] / grid))
        j0, j1 = int(round(b[1] / grid)), int(round(b[3] / grid))
        H[j0:j1, i0:i1] = heights[k]
        owner[j0:j1, i0:i1] = k
    return H, owner, grid


def _walls(ax, W, L, h=2.2):
    """Four translucent walls, so the extrusion reads as a room rather than floating boxes."""
    quads = [((0, 0, 0), (W, 0, 0), (W, 0, h), (0, 0, h)),
             ((0, L, 0), (W, L, 0), (W, L, h), (0, L, h)),
             ((0, 0, 0), (0, L, 0), (0, L, h), (0, 0, h)),
             ((W, 0, 0), (W, L, 0), (W, L, h), (W, 0, h))]
    ax.add_collection3d(Poly3DCollection(quads, facecolor="#dfe6ec", edgecolor="#8c99a6",
                                         linewidths=0.6, alpha=0.10))


def render(sess, out_png, actual=None, prior_root=None):
    with open(os.path.join(sess, "prediction.json"), encoding="utf-8") as fh:
        pred = json.load(fh)
    if pred.get("status") != "ok":
        raise SystemExit("prediction status is %r, nothing to draw" % pred.get("status"))
    heights = actual or ACTUAL.get(pred["session"])
    if not heights:
        raise SystemExit("no measured heights for %r; pass actual=" % pred["session"])

    W, L = pred["room"]
    H, owner, grid = height_field(pred, heights)
    traj = np.load(os.path.join(sess, "ronin-xy.npy"))
    # RoNIN 输出在它自己的坐标系里（起点为原点），按求解器同一变换搬进房间系
    a = np.radians(pred["rot_deg"])
    c, s = np.cos(a), np.sin(a)
    P = traj[:, 1:3] @ np.array([[c, s], [-s, c]])
    Q = P - (P[0] - np.array(pred["start_anchored_at"], dtype=float))
    tx, ty = Q[:, 0], Q[:, 1]

    prior = HP.table(HP.load_objects(paths.THOR)) if os.path.isdir(paths.THOR) else {}
    lines = ["高度这一维 IMU 从未观测，只能用类别先验。  下表：先验中位 → 本房间实际"]
    for k in ("bed", "desk", "cab", "chair"):
        cn, en = LABEL[k]
        pm = prior.get(en, {}).get("med")
        if k == "chair":
            lines.append("%s        %.2f → %.2f  (坐面；先验含靠背，两者不可比)" % (cn, pm, heights[k]))
        elif pm is None:
            lines.append("%s        --     → %.2f" % (cn, heights[k]))
        else:
            lines.append("%s        %.2f   → %.2f  (%+.2f)" % (cn, pm, heights[k], heights[k] - pm))
    note = "\n".join(lines)

    fig = plt.figure(figsize=(13.6, 7.7), dpi=150)
    ax3 = fig.add_subplot(1, 2, 1, projection="3d")
    ax2 = fig.add_subplot(1, 2, 2)

    _walls(ax3, W, L)
    for k, b in pred["boxes"].items():
        dx, dy = b[2] - b[0], b[3] - b[1]
        ax3.bar3d(b[0], b[1], 0, dx, dy, heights[k], color=COLOR[k],
                  alpha=0.88, edgecolor="#333", linewidth=0.6, shade=True)
    ax3.plot(tx, ty, np.full_like(tx, 0.012), color="#111", lw=1.1, alpha=0.75)
    ax3.set_xlim(0, W); ax3.set_ylim(0, L); ax3.set_zlim(0, 2.2)
    ax3.set_box_aspect((W, L, 0.95))
    ax3.view_init(elev=28, azim=-62)
    ax3.set_xlabel("x (m)", fontproperties=CJK, fontsize=9)
    ax3.set_ylabel("y (m)", fontproperties=CJK, fontsize=9)
    ax3.set_zlabel("高度 (m)", fontproperties=CJK, fontsize=9)
    ax3.set_title("立体挤出：底面来自 IMU，高度来自先验/实测", fontproperties=CJK, fontsize=11)


    ls = LightSource(azdeg=315, altdeg=45)
    img = ls.shade(H, cmap=plt.get_cmap("viridis"), vert_exag=0.4, blend_mode="soft", vmin=0, vmax=1.0)
    ax2.imshow(img, origin="lower", extent=[0, W, 0, L], alpha=0.9)
    ax2.plot(tx, ty, color="#fff", lw=1.2, alpha=0.9)
    ax2.plot(tx, ty, color="#111", lw=0.6, alpha=0.9)
    ax2.plot(tx[0], ty[0], "o", ms=8, mfc="#ffd400", mec="#111", mew=1.2, zorder=5)
    ax2.text(tx[0] + 0.07, ty[0] + 0.07, "S", fontproperties=CJK, fontsize=12, weight="bold", zorder=6)
    for k, b in pred["boxes"].items():
        ax2.add_patch(plt.Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1],
                                    fill=False, lw=1.6, ec="#d62728"))
        ax2.text((b[0] + b[2]) / 2, (b[1] + b[3]) / 2 - 0.16,
                 "%s %.2fm" % (LABEL[k][0], heights[k]), ha="center", va="center",
                 fontproperties=CJK, fontsize=10, color="white",
                 bbox=dict(fc="#000", alpha=0.35, lw=0, pad=1.6))
    ax2.set_xlim(0, W); ax2.set_ylim(0, L); ax2.set_aspect("equal")
    ax2.set_xlabel("x (m)", fontproperties=CJK); ax2.set_ylabel("y (m)", fontproperties=CJK)
    ax2.set_title("俯视：白线为 IMU 轨迹，S 为起点", fontproperties=CJK, fontsize=11)

    sm = plt.cm.ScalarMappable(cmap="viridis", norm=plt.Normalize(0, 1.0))
    cb = fig.colorbar(sm, ax=ax2, shrink=0.62, pad=0.02)
    cb.set_label("占据高度 (m)", fontproperties=CJK)
    fig.suptitle("稠密语义图（2.5D）— %s，房间 %.2f x %.2f m" % (pred["session"], W, L),
                 fontproperties=CJK, fontsize=13)
    fig.text(0.5, 0.025, note, ha="center", va="bottom", fontproperties=CJK, fontsize=9.6,
             color="#222", bbox=dict(fc="#f6f8fa", ec="#c9d3dc", lw=0.8, pad=7))
    fig.tight_layout(rect=[0, 0.135, 1, 0.95])
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)

    covered = float((H > 0).sum()) * grid * grid
    rows = []
    prior = HP.table(HP.load_objects(prior_root or paths.THOR)) if prior_root or os.path.isdir(paths.THOR) else {}
    for k in ("bed", "desk", "cab", "chair"):
        cn, en = LABEL[k]
        pm = prior.get(en, {}).get("med")
        rows.append(dict(obj=k, name=cn, h=heights[k], prior=pm,
                         err=None if pm is None else heights[k] - pm))
    return dict(png=out_png, covered_m2=round(covered, 3), room_m2=round(W * L, 3),
                objects=rows, cells=int(H.shape[0] * H.shape[1]))


if __name__ == "__main__":
    sess = sys.argv[1] if len(sys.argv) > 1 else "output/layout-recon/s-59d570ee"
    out = os.path.join(sess, "dense-map.png")
    r = render(sess, out)
    print("已保存", r["png"])
    print("占据 %.2f m2 / 房间 %.2f m2" % (r["covered_m2"], r["room_m2"]))
    print("%-4s %6s %8s %8s" % ("", "本房间", "先验", "差"))
    for o in r["objects"]:
        print("%-6s %6.2f %6s %8s" % (o["name"], o["h"],
                                      "%.2f" % o["prior"] if o["prior"] is not None else "-",
                                      "%+.2f" % o["err"] if o["err"] is not None else "-"))
