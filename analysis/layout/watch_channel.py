"""手表通道：三轴加速度的时钟对齐、可用性判定与逐动作旁证。

手表 S5 只给三轴加速度（无陀螺），采样 16.7 Hz，因此不能参与轨迹与朝向，
但可以在「活动」这一维独立核对手机判出的动作。

两个可检验的量：
  1. 时钟：每轮握手给一个恒定 offset 的条件区间 [P3-1000*W4, P2-1000*W1]。
     全体交集非空只说明「恒定 offset 假设相容」，不是独立验证。
  2. 数据自证：两路运动包络（|‖a‖-g| 的分箱均值）在零滞后处的相关系数。
     若偏移估错，最佳滞后会明显偏离 0。
"""
import json, io, csv, os, zipfile
import numpy as np

G = 9.81
USABLE_R = 0.35        # 零滞后相关的可用门槛；低于此值两路不跟踪同一运动
BIN_S = 0.5            # 包络分箱


def read_watch(path):
    """读 watch.jsonl：返回 (时间 ms 浮点数组, 加速度 N×3, 时钟观测列表)。"""
    t, a, obs = [], [], []
    with io.open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            k = d.get('kind')
            if k == 'watch_data':
                for r in json.loads(d['packet']['payload']):
                    t.append(float(r[1])); a.append([float(r[2]), float(r[3]), float(r[4])])
            elif k == 'watch_clock_observation':
                obs.append(d['observation'])
    o = np.argsort(np.asarray(t))
    return np.asarray(t)[o], np.asarray(a, float)[o], obs


def clock_interval(obs, q_us=0.0):
    """恒定 offset (手机-手表, µs) 的条件区间交集。q_us 为每轮附加不确定度。"""
    lo, hi = -1e18, 1e18
    for o in obs:
        lo = max(lo, float(o['p3_us']) - 1000.0 * float(o['w4_ms']) - q_us)
        hi = min(hi, float(o['p2_us']) - 1000.0 * float(o['w1_ms']) + q_us)
    return lo, hi


def _phone_rows(sess):
    """取手机加速度首行时间戳与 metadata；优先已解包目录，否则读 zip。"""
    if os.path.exists(os.path.join(sess, 'phone')):
        p = os.path.join(sess, 'phone')
        with io.open(os.path.join(p, 'metadata.json'), encoding='utf-8') as fh:
            meta = json.load(fh)
        with io.open(os.path.join(p, 'accelerometer.csv'), encoding='utf-8') as fh:
            first = next(csv.DictReader(fh))
        return meta, int(first['sensor_timestamp_ns'])
    with zipfile.ZipFile(os.path.join(sess, 'phone.zip')) as z:
        meta = json.loads(z.read('metadata.json'))
        first = next(csv.DictReader(io.StringIO(z.read('accelerometer.csv').decode('utf-8'))))
    return meta, int(first['sensor_timestamp_ns'])


def zero_wall_ms(sess):
    """手机加速度 t=0 对应的墙钟（ms）。"""
    meta, t0 = _phone_rows(sess)
    return meta['start_wall_ms'] + (t0 - meta['collection_start_elapsed_ns']) / 1e6


def envelope(t, a, bin_s=BIN_S):
    """|‖a‖-g| 的分箱均值，作为运动量包络。"""
    if len(t) < 2:
        return np.zeros(0)
    n = int(np.ceil(t[-1] / bin_s)) + 1
    acc = np.zeros(n); cnt = np.zeros(n)
    idx = np.clip((t / bin_s).astype(int), 0, n - 1)
    np.add.at(acc, idx, np.abs(np.linalg.norm(a, axis=1) - G)); np.add.at(cnt, idx, 1)
    return acc / np.maximum(cnt, 1)


def best_lag(ep, ew, span=20):
    """在 ±span 分箱内搜最佳滞后，返回 (lag, r)。"""
    k = len(ew)
    c0 = 0.0 if np.std(ep) < 1e-9 or np.std(ew) < 1e-9 else float(np.corrcoef(ep, ew)[0, 1])
    best = (0, c0)
    for lag in range(-span, span + 1):
        if lag >= 0:
            x, y = ep[lag:], ew[:k - lag]
        else:
            x, y = ep[:k + lag], ew[-lag:]
        if len(x) < 15 or np.std(x) < 1e-9 or np.std(y) < 1e-9:
            continue
        c = float(np.corrcoef(x, y)[0, 1])
        if c > best[1]:
            best = (lag, c)
    return best


def _level(t, a, s0, s1):
    m = (t >= s0) & (t < s1)
    if int(m.sum()) < 4:
        return None, 0
    return float(np.mean(np.abs(np.linalg.norm(a[m], axis=1) - G))), int(m.sum())


def summarize(sess, actions=None):
    """给一个会话的手表通道结论；无手表数据时返回 None。"""
    wp = os.path.join(sess, 'watch.jsonl')
    if not os.path.exists(wp):
        return None
    t, a, obs = read_watch(wp)
    if len(t) < 50 or not obs:
        return {'status': 'insufficient', 'samples': int(len(t)), 'clock_obs': len(obs)}
    try:
        lo, hi = clock_interval(obs)
    except Exception:
        lo, hi = 0.0, 0.0
    if hi <= lo:
        return {'status': 'clock_inconsistent', 'samples': int(len(t)), 'clock_obs': len(obs)}
    off = (lo + hi) / 2.0 / 1000.0
    try:
        t0w = zero_wall_ms(sess)
    except Exception as e:
        return {'status': 'no_phone', 'error': str(e)[:80]}
    tr = (t + off - t0w) / 1000.0

    out = {'status': 'ok', 'samples': int(len(t)), 'clock_obs': len(obs),
           'offset_ms': float(off), 'offset_width_ms': float((hi - lo) / 1000.0),
           'signal_span_s': [float(tr[0]), float(tr[-1])]}

    # 与手机的运动包络比对：零滞后相关 + 最佳滞后
    try:
        with zipfile.ZipFile(os.path.join(sess, 'phone.zip')) as z:
            rows = list(csv.DictReader(io.StringIO(z.read('accelerometer.csv').decode('utf-8'))))
        tp0 = int(rows[0]['sensor_timestamp_ns'])
        tp = np.array([(int(r['sensor_timestamp_ns']) - tp0) / 1e9 for r in rows])
        ap = np.array([[float(r['x']), float(r['y']), float(r['z'])] for r in rows])
        ep, ew = envelope(tp, ap), envelope(tr, a)
        k = min(len(ep), len(ew))
        r0 = float(np.corrcoef(ep[:k], ew[:k])[0, 1]) if k > 5 else float('nan')
        lag, rb = best_lag(ep[:k], ew[:k])
        out.update({'r_zero_lag': r0, 'best_lag_bins': int(lag), 'r_best': float(rb),
                    'usable': bool(r0 >= USABLE_R and abs(lag) <= 1)})
    except Exception as e:
        out.update({'usable': False, 'compare_error': str(e)[:80]})

    if actions:
        # 同类动作可能有多段（如四次走动），逐段测后取均值，不能后段覆盖前段
        acc = {}
        for name, s0, s1 in actions:
            v, n = _level(tr, a, s0, s1)
            if v is None:
                continue
            acc.setdefault(name, []).append(v)
        lv = {k: {'level': float(np.mean(v)), 'n_segments': len(v)} for k, v in acc.items()}
        out['action_level'] = lv
        walk = [d['level'] for k2, d in lv.items() if k2 == 'walk' and d['level'] is not None]
        rest = [d['level'] for k2, d in lv.items() if k2 in ('lying', 'seated') and d['level'] is not None]
        if walk and rest:
            wm, rm = float(np.median(walk)), float(np.median(rest))
            out['walk_level'] = wm; out['rest_level'] = rm
            out['walk_over_rest'] = float(wm / rm) if rm > 1e-9 else None
        cab = lv.get('cabinet', {}).get('level')
        if cab is not None and walk and rest:
            out['cabinet_vs_rest'] = float(cab / rm) if rm > 1e-9 else None
            out['cabinet_vs_walk'] = float(cab / wm) if wm > 1e-9 else None
    return out
