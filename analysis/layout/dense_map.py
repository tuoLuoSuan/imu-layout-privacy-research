"""2.5D dense semantic map for one reconstructed room.

Horizontal extent comes from the IMU pipeline (layout_solver boxes).  Height is
not estimated by this pipeline. It is a category prior or an explicitly supplied
reference value. Usage: python -m analysis.layout.dense_map <session>
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family': ['Arial', 'SimSun'], 'pdf.fonttype': 42, 'svg.fonttype': 'none'})
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
# 床高由用户确认；柜高由用户报「比 1.7 m 略高」并经点云竖直面复核（visible 到 1.7 m 与被截断的
# 左墙同高，说明点云在那里看不到顶，不能据此判矮）；桌 0.75 与点云 0.70-0.75 的水平层一致。
ACTUAL = {"s-59d570ee": {"bed": 0.50, "desk": 0.75, "cab": 1.80, "chair": 0.45}}
# 本房间净高：天花板平面 2.09 m（地面在 -0.03 m），仅用于墙的显示高度。
CEILING = {"s-59d570ee": 2.09}


def height_field(pred, heights, grid=0.02):
    """Rasterise the boxes into a height field; every filled cell is prior-filled vertically."""
    W, L = pred["room"]
    nx, ny = int(round(W / grid)), int(round(L / grid))
    H = np.zeros((ny, nx))
    owner = np.full((ny, nx), "", dtype=object)
    for k, b in pred["boxes"].items():
        i0, i1 = np.clip([int(round(b[0] / grid)), int(round(b[2] / grid))], 0, nx)
        j0, j1 = np.clip([int(round(b[1] / grid)), int(round(b[3] / grid))], 0, ny)
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


def render(sess, out_png, actual=None, prior_root=None, use_reference=True):
    with open(os.path.join(sess, "prediction.json"), encoding="utf-8") as fh:
        pred = json.load(fh)
    if pred.get("status") != "ok":
        raise SystemExit("prediction status is %r, nothing to draw" % pred.get("status"))
    prior_path = prior_root or paths.THOR
    prior = HP.table(HP.load_objects(prior_path)) if os.path.isdir(prior_path) else {}
    heights = actual or (ACTUAL.get(pred['session']) if use_reference else None)
    height_source = 'supplied_reference' if heights else 'category_prior'
    if not heights:
        heights = {key: prior[LABEL[key][1]]['med'] for key in pred['boxes']}

    W, L = pred["room"]
    H, owner, grid = height_field(pred, heights)
    traj = np.load(os.path.join(sess, "ronin-xy.npy"))
    # RoNIN 输出在它自己的坐标系里（起点为原点），按求解器同一变换搬进房间系
    a = np.radians(pred["rot_deg"])
    c, s = np.cos(a), np.sin(a)
    P = traj[:, 1:3] @ np.array([[c, s], [-s, c]])
    Q = P - (P[0] - np.array(pred["start_anchored_at"], dtype=float))
    tx, ty = Q[:, 0], Q[:, 1]

    display_max = max(1.0, float(max(heights.values())))
    wall_display_height = CEILING.get(pred["session"]) or max(2.2, display_max * 1.1)
    source_label = '提供的参考高度' if height_source == 'supplied_reference' else '类别先验高度'
    lines = ['底面来自布局预测，当前二维模型未估计高度。图中使用' + source_label,
             '房间净高 %.2f m 由点云天花板平面测得（不是假设）' % wall_display_height]
    for k in ("bed", "desk", "cab", "chair"):
        cn, en = LABEL[k]
        pm = prior.get(en, {}).get("med")
        if height_source == 'category_prior':
            lines.append('%s  %.2f m（类别先验）' % (cn, heights[k]))
            continue
        if k == "chair" and pm is not None:
            lines.append("%s        %.2f → %.2f  (坐面；先验含靠背，两者不可比)" % (cn, pm, heights[k]))
        elif pm is None:
            lines.append("%s        --     → %.2f" % (cn, heights[k]))
        else:
            lines.append("%s        %.2f   → %.2f  (%+.2f)" % (cn, pm, heights[k], heights[k] - pm))
    note = "\n".join(lines)

    fig = plt.figure(figsize=(13.6, 7.7), dpi=300)
    ax3 = fig.add_subplot(1, 2, 1, projection="3d")
    ax2 = fig.add_subplot(1, 2, 2)
    ax3.grid(False)
    ax2.grid(False)

    _walls(ax3, W, L, h=wall_display_height)
    for k, b in pred["boxes"].items():
        dx, dy = b[2] - b[0], b[3] - b[1]
        ax3.bar3d(b[0], b[1], 0, dx, dy, heights[k], color=COLOR[k],
                  alpha=0.88, edgecolor="#333", linewidth=0.6, shade=True)
    ax3.plot(tx, ty, np.full_like(tx, 0.012), color="#111", lw=1.1, alpha=0.75)
    ax3.set_xlim(0, W); ax3.set_ylim(0, L); ax3.set_zlim(0, wall_display_height)
    ax3.set_box_aspect((W, L, 0.95))
    ax3.view_init(elev=28, azim=-62)
    ax3.set_xlabel("x (m)", fontproperties=CJK, fontsize=9)
    ax3.set_ylabel("y (m)", fontproperties=CJK, fontsize=9, labelpad=18)
    ax3.set_zlabel("高度 (m)", fontproperties=CJK, fontsize=9)
    ax3.set_title('立体挤出：底面来自布局预测，' + source_label, fontproperties=CJK, fontsize=11)


    ls = LightSource(azdeg=315, altdeg=45)
    img = ls.shade(H, cmap=plt.get_cmap("viridis"), vert_exag=0.4, blend_mode="soft", vmin=0, vmax=display_max)
    ax2.imshow(img, origin="lower", extent=[0, W, 0, L], alpha=0.9)
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
    ax2.set_title("俯视：类别占地与高度来源，S 为起点", fontproperties=CJK, fontsize=11)

    sm = plt.cm.ScalarMappable(cmap="viridis", norm=plt.Normalize(0, display_max))
    cb = fig.colorbar(sm, ax=ax2, shrink=0.62, pad=0.02)
    cb.set_label("占据高度 (m)", fontproperties=CJK)
    fig.suptitle("稠密语义图（2.5D）— %s，房间 %.2f x %.2f m" % (pred["session"], W, L),
                 fontproperties=CJK, fontsize=13)
    fig.text(0.5, 0.025, note, ha="center", va="bottom", fontproperties=CJK, fontsize=9.6,
             color="#222", bbox=dict(fc="#f6f8fa", ec="#c9d3dc", lw=0.8, pad=7))
    fig.tight_layout(rect=[0, 0.135, 1, 0.95])
    fig.savefig(out_png, facecolor="white")
    fig.savefig(os.path.splitext(out_png)[0] + '.pdf', facecolor='white')
    fig.savefig(os.path.splitext(out_png)[0] + '.svg', facecolor='white')
    plt.close(fig)
    semantic_names = ['unassigned', 'bed', 'desk', 'cab', 'chair']
    semantic = np.zeros(owner.shape, dtype=np.uint8)
    for index, key in enumerate(semantic_names[1:], 1):
        semantic[owner == key] = index
    grid_path = os.path.splitext(out_png)[0] + '.npz'
    np.savez_compressed(grid_path, height_m=H, semantic_id=semantic,
                        semantic_names=np.asarray(semantic_names), resolution_m=grid,
                        room_m=np.asarray([W, L]), height_source=np.asarray(height_source))

    covered = float((H > 0).sum()) * grid * grid
    rows = []
    prior = HP.table(HP.load_objects(prior_root or paths.THOR)) if prior_root or os.path.isdir(paths.THOR) else {}
    for k in ("bed", "desk", "cab", "chair"):
        cn, en = LABEL[k]
        pm = prior.get(en, {}).get("med")
        rows.append(dict(obj=k, name=cn, h=heights[k], prior=pm,
                         err=None if pm is None or height_source == 'category_prior' or k == 'chair' else heights[k] - pm,
                         comparison='seat versus full backrest height: not comparable' if k == 'chair' else 'reference minus category prior'))
    return dict(png=out_png, covered_m2=round(covered, 3), room_m2=round(W * L, 3),
                height_source=height_source, grid_m=grid, semantic_grid=grid_path,
                reference_heights_independently_verified=False,
                unassigned_cells='Unknown occupancy; not verified empty floor',
                rendered_walls='Display scaffold from supplied room footprint; wall height is not reconstructed',
                horizontal_source='layout prediction conditional on supplied room and furniture priors',
                objects=rows, cells=int(H.shape[0] * H.shape[1]))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('session', nargs='?', default='output/layout-recon/s-59d570ee')
    parser.add_argument('--height-source', choices=['prior', 'reference', 'measured'], default='prior',
                        help='measured is a legacy alias for supplied reference, not independent verification')
    parser.add_argument('--output')
    parser.add_argument('--height-json', help='JSON object mapping furniture keys to measured heights in metres')
    args = parser.parse_args()
    sess = args.session
    out = args.output or os.path.join(sess, 'dense-map-' + args.height_source + '.png')
    measured = None
    if args.height_json:
        with open(args.height_json, encoding='utf-8') as handle:
            measured = json.load(handle)
    if args.height_source != 'prior' and measured is None and os.path.basename(sess) not in ACTUAL:
        raise ValueError('Reference heights are not registered for this session')
    if measured and args.height_source == 'prior':
        raise ValueError('Reference height JSON requires --height-source reference')
    r = render(sess, out, actual=measured, use_reference=args.height_source != 'prior')
    with open(os.path.splitext(out)[0] + '.json', 'w', encoding='utf-8') as handle:
        json.dump(r, handle, ensure_ascii=False, indent=2)
    print("已保存", r["png"])
    print("占据 %.2f m2 / 房间 %.2f m2" % (r["covered_m2"], r["room_m2"]))
    print("%-4s %6s %8s %8s" % ("", "图中高度", "先验", "差"))
    for o in r["objects"]:
        print("%-6s %6.2f %6s %8s" % (o["name"], o["h"],
                                      "%.2f" % o["prior"] if o["prior"] is not None else "-",
                                      "%+.2f" % o["err"] if o["err"] is not None else "-"))
