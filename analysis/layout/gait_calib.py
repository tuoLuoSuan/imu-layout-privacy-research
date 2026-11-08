"""步态标定：真实录音的竖直起伏频率/幅度 vs 合成流，用同一套估计器量。

合成流之前被判 synthetic-domain-mismatch（前端路程比 1.27）：路径长度对，但前端以为走得更快。
这里先量「真实走路的竖直起伏」到底是多少，再看生成器给的摆动是不是比它大。
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim_motion as SM

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SESS = os.path.join(ROOT, "output", "layout-recon", "s-59d570ee")


def read_accel(path):
    d = np.genfromtxt(path, delimiter=",", skip_header=1, usecols=(1, 4, 5, 6))
    t = (d[:, 0] - d[0, 0]) / 1e9
    return t, d[:, 1:]


def segment_stats(t, a, t0, t1, fs_nominal=120.0, trim=0.6):
    # 段首尾含姿态过渡（坐下/躺下时身体下降），会盖住步态本身，两边各裁掉 trim 秒
    t0, t1 = t0 + trim, t1 - trim
    m = (t >= t0) & (t <= t1)
    if m.sum() < 60:
        return None
    tt, aa = t[m], a[m]
    up = aa.mean(axis=0)
    up = up / np.linalg.norm(up)
    u = aa @ up
    u = u - u.mean()
    # 频率：抛物线插值的谱峰
    n = len(u)
    win = np.hanning(n)
    spec = np.abs(np.fft.rfft(u * win))
    fr = np.fft.rfftfreq(n, d=1.0 / fs_nominal)
    band = (fr > 0.8) & (fr < 4.5)
    if not band.any():
        return None
    idx = np.argmax(spec * band)
    f = float(fr[idx])
    return dict(f=round(f, 3), amp=round(float(u.std()), 4),
                span_s=round(float(tt[-1] - tt[0]), 2),
                n=int(n), up=[round(float(v), 3) for v in up])


def real_segments():
    t, a = read_accel(os.path.join(SESS, "phone", "accelerometer.csv"))
    with open(os.path.join(SESS, "actions.json"), encoding="utf-8") as fh:
        runs = json.load(fh)["runs"]
    out = []
    for lab, s, e in runs:
        if lab != "walk":
            continue
        st = segment_stats(t, a, s, e)
        if st:
            st.update(dict(start=s, end=e))
            out.append(st)
    return out


def synth_segments(fs=120.0):
    g = SM.generate(fs=fs, seed=7)
    t = g["t"]
    a = g["acc"]
    lab = g["truth"]["label"]
    out = []
    for name in ("walk",):
        idx = np.where(np.array(lab) == name)[0]
        if len(idx) == 0:
            continue
        # 连续段
        breaks = np.where(np.diff(idx) > 1)[0]
        starts = np.r_[idx[0], idx[breaks + 1]]
        ends = np.r_[idx[breaks], idx[-1]]
        for s, e in zip(starts, ends):
            if e - s < 60:
                continue
            st = segment_stats(t, a, t[s], t[e])
            if st:
                st.update(dict(start=round(float(t[s]), 2), end=round(float(t[e]), 2)))
                out.append(st)
    return out


def summarize(rows, name):
    if not rows:
        print(name, "no segments")
        return None
    f = float(np.median([r["f"] for r in rows]))
    amp = float(np.median([r["amp"] for r in rows]))
    print("%s: n=%d, 竖直起伏频率中位 %.3f Hz, 幅度(std)中位 %.4f m/s^2" % (name, len(rows), f, amp))
    return dict(f=round(f, 3), amp=round(amp, 4), n=len(rows), rows=rows)


if __name__ == "__main__":
    r = summarize(real_segments(), "真实 walk")
    s = summarize(synth_segments(), "合成 walk")
    out = dict(real=r, synth=s, f_step=SM.F_STEP)
    with open(os.path.join(ROOT, "analysis", "layout", "gait_calib.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("生成器 F_STEP =", SM.F_STEP)
