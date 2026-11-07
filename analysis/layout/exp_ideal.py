# -*- coding: utf-8 -*-
"""理想观测链 vs 真实前端链：同一房间、同一求解器，只换锚点来源。
理想锚点由雷达真值框反推（坐=椅心、开柜=柜面外 0.60 m、躺=床尾内 0.05 m）。"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
import analysis.layout.layout_solver as LS

SESS = os.path.join(ROOT, 'output', 'layout-recon', 's-59d570ee')
REF = {'bed': (1.17, 1.96, 2.695, 4.045), 'desk': (0.05, 1.05, 0.65, 2.10),
       'cab': (0.05, 0.0, 0.65, 1.05), 'chair': (1.11, 0.92, 1.55, 1.36)}
C = {k: np.array([(v[0] + v[2]) / 2, (v[1] + v[3]) / 2]) for k, v in REF.items()}

IDEAL = {'seated': C['chair'],
         'cabinet': np.array([REF['cab'][2] + 0.60, (REF['cab'][1] + REF['cab'][3]) / 2]),
         'lying': np.array([C['bed'][0], REF['bed'][1] + 0.05])}
_pj = json.load(open(os.path.join(SESS, 'prediction.json'), encoding='utf-8'))
REAL = _pj['anchors']
# 求解器期望的锚点在「轨迹帧」：room = A @ R - off，故 A = (room + off) @ R^T
_a = np.radians(_pj['rot_deg']); _R = np.array([[np.cos(_a), np.sin(_a)], [-np.sin(_a), np.cos(_a)]])
_P = np.load(os.path.join(SESS, 'ronin-xy.npy'))[:, 1:3]
_off = (_P @ _R)[0] - np.array(LS.S_PT)
IDEAL = {k: (v + _off) @ _R.T for k, v in IDEAL.items()}
REAL = {k: (np.array(v) + _off) @ _R.T for k, v in REAL.items()}

def errs(pred):
    out = {}
    for k, b in pred['boxes'].items():
        r = REF[k]
        out[k] = float(np.hypot((b[0] + b[2]) / 2 - (r[0] + r[2]) / 2, (b[1] + b[3]) / 2 - (r[1] + r[3]) / 2))
    return out

rows = []
for name, A in (('ideal', IDEAL), ('real', {k: np.array(v) for k, v in REAL.items()})):
    pred = LS.solve(SESS, save=False, anchors=dict(A))[0]
    rows.append({'arm': name, 'status': pred['status'], 'err': errs(pred),
                 'anchors': {k: [float(x) for x in v] for k, v in A.items()}})
    print('%-6s %-8s %s' % (name, pred['status'], ' '.join('%s %.3f' % kv for kv in rows[-1]['err'].items())))

# 锚点本身的偏差（真实前端 vs 理想）
dev = {k: float(np.linalg.norm(np.array(REAL[k]) - IDEAL[k])) for k in IDEAL}
print('anchor deviation:', ' '.join('%s %.3f' % kv for kv in dev.items()))
out = os.path.join(HERE, 'ideal_vs_raw.json')
json.dump({'rows': rows, 'anchor_dev_m': dev}, open(out, 'w', encoding='utf-8'), indent=1)
print('written', out)
