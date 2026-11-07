# 一条命令：zip -> 轨迹 + 动作时间线 + 由动作反推的平面图。
# 时间基准：轨迹用 RoNIN 窗口中心（原始 IMU 秒），动作窗同样用原始 IMU 秒，两者同源，不再减起点。
# 朝向：六轴无磁力计，绝对朝向不可知；用「轨迹装进房间 + 床长接近实测 2.085 m + 走路点不穿床」联合选角。
import sys, os, csv, json, io, subprocess, importlib.util
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
import matplotlib.font_manager as fm
from sklearn.ensemble import RandomForestClassifier

cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = __import__('paths').REPO
sys.path.insert(0, ROOT)
from analysis.phone_ronin.adapter import RATE_HZ, WINDOW
HALF = WINDOW / RATE_HZ / 2.0

W, H = 2.84, 4.045
S = np.array([0.825, 3.845])
BED_W, BED_L = 1.525, 2.085
DESK_D, CAB_T = 0.60, 0.95
REF = {'bed': (1.17, 1.96, 2.695, 4.045), 'desk': (0.05, 1.05, 0.65, 2.10), 'cab': (0.05, 0.0, 0.65, 1.05)}
CHAIR = np.array([1.33, 1.14])

EXT = os.path.join(ROOT, 'output/action-recognition/2026-11-02-accuracy-rebuild-001/dataset_ext.py')
spec = importlib.util.spec_from_file_location('dataset_ext', EXT)
ext = importlib.util.module_from_spec(spec); spec.loader.exec_module(ext)
A_SEG = [(0,6,'other'),(6,12,'walk'),(12,20,'cabinet'),(20,26,'walk'),(26,39,'lying'),(39,43,'walk'),(43,48,'walk'),(48,56,'seated'),(56,60,'walk'),(60,66,'walk')]
B_SEG = [(0,6,'other'),(6,12,'walk'),(12,24,'seated'),(24,28,'walk'),(28,34,'walk'),(34,47,'lying'),(47,51,'walk'),(51,57,'walk'),(57,63,'cabinet'),(63,69,'walk')]

def load(sess, name):
    rows = []
    with open(os.path.join(sess, 'phone', name), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            rows.append((int(r['sensor_timestamp_ns']), float(r['x']), float(r['y']), float(r['z'])))
    t0 = rows[0][0]
    return np.array([(a-t0)/1e9 for a, *_ in rows]), np.array([[b, c, d] for _, b, c, d in rows])

def feats_at(ta, A, tg, G, s0):
    f, sgs = {}, {}
    for nm, (t, x), pre, norm in (('acc', (ta, A), 'acc', True), ('gyro', (tg, G), 'gyro', False)):
        if not ext.assess(t, s0, s0+3)['valid']: return None
        f.update({pre+'_'+k: v for k, v in ext.pipe.event_features(t, x, s0, s0+3, normalize=norm).items()})
        sgs['phone_'+pre] = ext.select(t, x, s0, s0+3)
    f.update(ext.temporal(sgs, 'phone'))
    return f

X, y, keys = [], [], None
for tag, seg in (('r1', A_SEG), ('r2', A_SEG), ('r3', B_SEG), ('r4', B_SEG)):
    s = os.path.join(ROOT, 'output/layout-recon', '2026-11-06-round-'+tag)
    ta, A = load(s, 'accelerometer.csv'); tg, G = load(s, 'gyroscope.csv')
    off = json.load(open(os.path.join(s, 'cue-sync.json')))['t0']
    for a, b, lab in seg:
        for s0 in np.arange(a+off, b+off-3.0+1e-6, 0.5):
            f = feats_at(ta, A, tg, G, s0)
            if f is None: continue
            if keys is None: keys = sorted(f.keys())
            X.append([f[k] for k in keys]); y.append(lab)
clf = RandomForestClassifier(n_estimators=400, random_state=0, max_features='sqrt', n_jobs=1).fit(np.array(X, float), np.array(y))
print('模型就绪（%d 窗）' % len(X))

if len(sys.argv) < 2:
    print('usage: python analyze.py <zip> [outdir]'); sys.exit(1)
zip_path = sys.argv[1]
sid = os.path.splitext(os.path.basename(zip_path))[0].replace('IMU_', '')[:8]
outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'output/layout-recon', 'a-'+sid)
if not os.path.exists(os.path.join(outdir, 'ronin-xy.npy')):
    r = subprocess.run([sys.executable, os.path.join(HERE, 'run_any_bundle.py'), zip_path, outdir], capture_output=True, text=True)
    _lines = (r.stdout or '').strip().splitlines()
    print(_lines[-1] if _lines else '(run_any_bundle 无输出)')
    if r.returncode != 0:
        print((r.stderr or '')[-800:]); sys.exit(2)

d = np.load(os.path.join(outdir, 'ronin-xy.npy'))
t = d[:, 0] - HALF
P = np.column_stack([d[:, 1], d[:, 2]])
sp = d[:, 3]
i0 = int(np.argmax(sp > 0.12))

ta, A = load(outdir, 'accelerometer.csv'); tg, G = load(outdir, 'gyroscope.csv')
rows = []
for s0 in np.arange(1.0, max(2.0, t[-1]-3.0), 0.5):
    f = feats_at(ta, A, tg, G, s0)
    if f is None: continue
    rows.append((float(s0+1.5), str(clf.predict(np.array([[f[k] for k in keys]], float))[0])))
runs = []
for tt, lab in rows:
    if runs and runs[-1][0] == lab and tt - runs[-1][2] < 1.2: runs[-1][2] = tt
    else: runs.append([lab, tt, tt])
labarr = np.array(['']*len(t), dtype=object)
for lab, a1, b1 in runs: labarr[(t >= a1) & (t <= b1)] = lab
walkmask = labarr == 'walk'

json.dump({'runs': runs}, io.open(os.path.join(outdir, 'actions.json'), 'w', encoding='utf-8'), indent=1)

sys.path.insert(0, HERE)
import layout_solver as LS

res = LS.solve(outdir)
pred, Q = res if isinstance(res, tuple) else (res, None)

gap = float(np.linalg.norm(P[-1] - P[0]))
path = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
print('')
print('时长 %.1f s，路程 %.2f m，首尾 %.2f m（%.1f%%）' % (t[-1], path, gap, 100 * gap / path))
print('')
print('动作时间线（位置用 layout_solver 的坐标系，与家具同一框架）：')
nm = {'seated': '坐', 'cabinet': '开柜', 'lying': '躺', 'walk': '走', 'other': '站立'}
for lab, a1, b1 in runs:
    if b1 - a1 < 1.0: continue
    m = (t >= a1) & (t <= b1)
    if Q is None or m.sum() == 0:
        print('  %5.1f - %5.1f s  %-4s  (未解出布局，无坐标)' % (a1, b1, nm.get(lab, lab)))
    else:
        print('  %5.1f - %5.1f s  %-4s  (%.2f, %.2f)' % (a1, b1, nm.get(lab, lab), Q[m, 0].mean(), Q[m, 1].mean()))

if pred.get('status') != 'ok':
    print('')
    print('布局未解出：%s %s' % (pred.get('status'), pred.get('missing', '')))
    print('轨迹与动作已保存：%s / %s' % (os.path.join(outdir, 'ronin-xy.npy'), os.path.join(outdir, 'actions.json')))
    sys.exit(4)

print('')
print('布局（%s）：旋转 %.0f 度，柜墙 %s（支持 %.2f），桌柜穿越 %.3f'
      % (pred['version'], pred['rot_deg'], pred['cabinet_wall'], pred['wall_support'], pred['desk_cab_pass_through']))
NL = {'bed': '床', 'desk': '桌', 'cab': '柜', 'chair': '椅'}
for k in ('bed', 'desk', 'cab', 'chair'):
    b = pred['boxes'][k]
    print('  %s x %.2f-%.2f (%.2f)  y %.2f-%.2f (%.2f)' % (NL[k], b[0], b[2], b[2]-b[0], b[1], b[3], b[3]-b[1]))

fig, axes = plt.subplots(1, 2, figsize=(13.6, 8.2), dpi=150)
for ax, which in ((axes[0], 'imu'), (axes[1], 'ref')):
    ax.add_patch(Rectangle((0, 0), W, H, fill=False, ec='#111', lw=2.4))
    ax.add_patch(Rectangle((0.395, H-0.05), 0.775, 0.10, fc='#4caf50', alpha=0.75, ec='none'))
    if which == 'imu':
        ax.plot(Q[:, 0], Q[:, 1], '-', lw=1.4, color='#333333', zorder=6)
        boxes = pred['boxes']
        for k, col, ec in (('bed', '#a8c4e6', '#4167a0'), ('desk', '#ffe08a', '#d99b00'),
                           ('cab', '#c9b6e4', '#7a5aa8'), ('chair', '#f6a6bc', '#c2185b')):
            b = boxes[k]
            ax.add_patch(Rectangle((b[0], b[1]), b[2]-b[0], b[3]-b[1], fc=col, ec=ec, lw=1.8, alpha=0.95, zorder=2))
            ax.text((b[0]+b[2])/2, (b[1]+b[3])/2, NL[k], ha='center', va='center', fontsize=14, fontproperties=cjk, zorder=3)
        ax.plot(*LS.S_PT, 'o', ms=10, color='#2ca02c', zorder=7)
        ax.set_title('IMU 重建（layout_solver）', fontsize=10.5, loc='left', fontproperties=cjk)
    else:
        for k, col, ec, lab in (('bed', '#a8c4e6', '#4167a0', '床'), ('desk', '#ffe08a', '#d99b00', '桌'), ('cab', '#c9b6e4', '#7a5aa8', '柜')):
            r0, r1, r2, r3 = REF[k]
            ax.add_patch(Rectangle((r0, r1), r2-r0, r3-r1, fc=col, ec=ec, lw=1.8, alpha=0.85))
            ax.text((r0+r2)/2, (r1+r3)/2, lab, ha='center', va='center', fontsize=14, fontproperties=cjk)
        ax.add_patch(Rectangle((CHAIR[0]-0.22, CHAIR[1]-0.22), 0.44, 0.44, fc='#f6a6bc', ec='#c2185b', lw=1.8))
        ax.set_title('雷达实测参考', fontsize=10.5, loc='left', fontproperties=cjk)
    ax.set_aspect('equal'); ax.set_xlim(-0.2, W+0.2); ax.set_ylim(-0.2, H+0.2)
    ax.set_xticks(np.arange(0, W+0.01, 0.5)); ax.set_yticks(np.arange(0, H+0.01, 0.5)); ax.grid(alpha=0.2, lw=0.4)
fig.suptitle('%s：旋转 %.0f 度，柜墙 %s' % (sid, pred['rot_deg'], pred['cabinet_wall']), fontsize=11, x=0.012, ha='left', fontproperties=cjk)
fig.tight_layout(rect=[0, 0, 1, 0.94])
o = os.path.join(outdir, 'floorplan.png')
fig.savefig(o)
print('')
print('图：', o)
print('预测：', os.path.join(outdir, 'prediction.json'))