import os, sys, csv, zipfile, hashlib, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import matplotlib.font_manager as fm
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from analysis.phone_ronin.adapter import prepare_features, make_windows, predict, integrate_centers

cjk = fm.FontProperties(fname=r"C:/Windows/Fonts/msyh.ttc")
SRC, OUT = sys.argv[1], sys.argv[2]
ARCH = __import__('paths').RONIN_ARCH
CKPT = __import__('paths').RONIN_CKPT
os.makedirs(OUT, exist_ok=True)
with zipfile.ZipFile(SRC) as f: f.extractall(OUT)
_mp = os.path.join(OUT, "bundle-manifest.json")
man = json.load(open(_mp, encoding="utf-8")) if os.path.exists(_mp) else {"native_sid": os.path.basename(SRC)}
sub = os.path.join(OUT, "phone"); os.makedirs(sub, exist_ok=True)
with zipfile.ZipFile(os.path.join(OUT, "phone.zip")) as f: f.extractall(sub)

def load(name):
    rows = []
    with open(os.path.join(sub, name), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append((int(r["sensor_timestamp_ns"]), float(r["x"]), float(r["y"]), float(r["z"])))
    t0 = rows[0][0]
    return [((t-t0)/1e9, x, y, z) for t, x, y, z in rows]
A = load("accelerometer.csv"); G = load("gyroscope.csv")
times, feats, info = prepare_features(A, G)
windows, wt = make_windows(times, feats)
sha = hashlib.sha256(open(CKPT, "rb").read()).hexdigest()
pred, _ = predict(windows, ARCH, CKPT, sha)
t = np.asarray(wt, dtype=np.float64)[:, 1]
xy = integrate_centers(t, pred)
sp = np.linalg.norm(pred, axis=1)
seg = float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum())
gap = float(np.linalg.norm(xy[-1]-xy[0]))
print("sid", man["native_sid"][:8], "accel %d rows, span %.2f s" % (len(A), A[-1][0]))
print("path %.2f m, span %.2f x %.2f m, end_gap %.2f m (%.3f of path), speed mean %.3f max %.2f"
      % (seg, np.ptp(xy[:,0]), np.ptp(xy[:,1]), gap, gap/seg, sp.mean(), sp.max()))
np.save(os.path.join(OUT, "ronin-xy.npy"), np.column_stack([t, xy, sp]))

fig = plt.figure(figsize=(13.5, 6.4), dpi=150)
ax = fig.add_subplot(1, 2, 1)
sc = ax.scatter(xy[:,0], xy[:,1], c=t, s=6, cmap="viridis")
ax.plot(xy[:,0], xy[:,1], lw=0.6, color="#999", alpha=0.6)
ax.plot(*xy[0], "o", ms=10, color="#2ca02c", label="start")
ax.plot(*xy[-1], "s", ms=9, color="#d62728", label="end")
ax.add_patch(Rectangle((-1.42, -2.02), 2.84, 4.045, fill=False, ec="#bbb", lw=1.2, ls="--"))
ax.text(-1.37, -1.95, "房间外框 2.84 x 4.045（同比例参照）", fontsize=7.5, color="#999", fontproperties=cjk)
ax.set_aspect("equal"); ax.grid(alpha=0.2, lw=0.4); ax.legend(fontsize=8)
ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
ax.set_title("包 %s（自然摆臂）\n路程 %.2f m，跨度 %.2f x %.2f m" % (man["native_sid"][:8], seg, np.ptp(xy[:,0]), np.ptp(xy[:,1])),
             fontsize=10, loc="left", fontproperties=cjk)
plt.colorbar(sc, ax=ax, shrink=0.8).set_label("time (s)")
ax2 = fig.add_subplot(1, 2, 2)
ax2.plot(t, sp, lw=1.0, color="#1f77b4")
ax2.axhline(1.2, color="#d62728", lw=0.8, ls="--", label="normal walking 1.2 m/s")
ax2.set_xlabel("time (s)"); ax2.set_ylabel("speed (m/s)")
ax2.set_title("速度：均值 %.2f、最大 %.2f m/s" % (sp.mean(), sp.max()), fontsize=10, loc="left", fontproperties=cjk)
ax2.legend(fontsize=8); ax2.grid(alpha=0.25)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "ronin-trajectory.png"))
json.dump({"sid": man["native_sid"], "path_m": seg, "end_gap_m": gap,
           "extent": [float(np.ptp(xy[:,0])), float(np.ptp(xy[:,1]))],
           "mean_speed": float(sp.mean()), "max_speed": float(sp.max())},
          open(os.path.join(OUT, "ronin-run.json"), "w"), indent=1)
print("saved", os.path.join(OUT, "ronin-trajectory.png"))