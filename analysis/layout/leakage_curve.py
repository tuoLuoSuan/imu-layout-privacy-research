# 泄露曲线：一个家具参数在「活动跨度 span」之下还剩下多少不确定性。
#
# 契约（2026-11-07 修正）：AI2-THOR 场景 JSON 的 floor 是 [中心 x, 中心 z, 宽, 长]，
# 不是边界。历史上本文件的 rooms() 按边界读取，导致家具被判到房外、间隙为负、
# 全部被算成「贴墙定死」。修正后贴墙比例从 70.3% 掉到 0.3%。
#
# 两个先验档（GPT 审核建议的 U / K）：
#   U：只知道房间尺寸，不知道家具贴哪面墙 —— 位置可以在 [L/2, room-L/2] 内任意，
#      先验宽度 = room - L；贴墙这一事实不带来零宽度（可能是四面墙中的任一面）。
#   K：知道它贴着某一面具体墙，且间隙在 [0, GAP_TOL] —— 法向宽度才缩到 GAP_TOL。
#
# 区间按端点求交（不是取 min）：事件区间来自锚点 [max a - L/2 - eps, min a + L/2 + eps]，
# 与先验区间求交后才得到残余宽度；两者位置不对齐时，min 只是上限。
import glob, json, os, sys
import numpy as np

TOL_WALL = 0.10        # 贴墙判定 / K 档允许间隙
EPS = 0.05             # 锚点位置误差（与噪声实验的 5 cm 档一致）
CATS = ('Bed', 'Desk', 'Cabinet', 'Chair', 'Shelf')
N_MC = 200


def rooms(root):
    out = []
    for f in sorted(glob.glob(os.path.join(root, 'FloorPlan*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        if 'objects' not in d:
            continue
        # floor = [中心 x, 中心 z, 宽, 长]（与 sim_eval.load_scene 同一契约）
        fcx, fcz, fw, fl = d['floor']
        bounds = (fcx - fw / 2, fcz - fl / 2, fcx + fw / 2, fcz + fl / 2)
        out.append((os.path.basename(f)[:-5], bounds, d['objects']))
    return out


def params(root, cats=CATS):
    """每个 (物件, 轴) 一行：L、房间长、该轴两侧的间隙、该轴是否贴墙、贴哪一侧。

    contact 必须逐轴判定：旧写法用「两轴里较小的间隙」当对象级 contact 再传给两轴，
    于是 x 方向贴墙的柜子连 y 方向也被当成贴墙（复核用 FloorPlan309 的同一个 Cabinet
    给出了 2 条这样的行）。负间隙超出容差视为几何记录异常，单独标 geom_bad，不计贴墙。"""
    rows = []
    for scene, (x0, z0, x1, z1), objs in rooms(root):
        room = (x0, z0, x1, z1)
        for o in objs:
            if o['type'] not in cats:
                continue
            c, s = o['center'], o['size']
            box = (c['x'] - s['x'] / 2, c['z'] - s['z'] / 2, c['x'] + s['x'] / 2, c['z'] + s['z'] / 2)
            gap_lo = {0: box[0] - x0, 1: box[1] - z0}
            gap_hi = {0: x1 - box[2], 1: z1 - box[3]}
            for axis in (0, 1):
                lo, hi = box[axis], box[axis + 2]
                g = min(gap_lo[axis], gap_hi[axis])
                rows.append(dict(scene=scene, cat=o['type'], axis=axis, L=float(hi - lo),
                                 room=float(room[axis + 2] - room[axis]), gap=float(g),
                                 geom_bad=bool(g < -TOL_WALL),
                                 contact=bool(-TOL_WALL <= g <= TOL_WALL),
                                 side='lo' if gap_lo[axis] <= gap_hi[axis] else 'hi'))
    return rows


def _widths(r, span, regime, n=N_MC, eps=EPS, rng=None):
    """蒙特卡洛（最小坐标 q 参数化，与 identifiability.prior_interval 同一契约）。

    真值 q 在房间先验 [0, room-L] 内均匀；锚点在物体占地上铺开 span 后取首尾，
    事件区间 q in [a_hi - L - eps, a_lo + eps]。U 档先验 [0, room-L]；
    K 档（诊断臂）假设攻击者知道它贴的是哪一面【具体】墙，间隙 0..TOL_WALL。

    返回 (宽度, 是否覆盖真值) 两个数组：K 若把「其实没贴墙」的家具当成贴墙，
    宽度会很小但真值被排除——只看宽度会得出相反结论，必须同时报覆盖率。"""
    rng = np.random.default_rng(7)   # 每次调用同一颗种子：同样的参数给出同样的数
    L, room = r['L'], r['room']
    free_hi = room - L
    if free_hi <= 0:                      # 物体比房间还长：位置被房间钉死
        return np.zeros(n), np.ones(n, bool)
    q = rng.uniform(0.0, free_hi, n)
    s = min(span, L)
    a_lo, a_hi = q + L / 2 - s / 2, q + L / 2 + s / 2
    e_lo, e_hi = a_hi - L - eps, a_lo + eps
    if regime == 'U' or not r['contact']:
        p_lo, p_hi = 0.0, free_hi
    elif r['side'] == 'lo':
        p_lo, p_hi = 0.0, TOL_WALL
    else:
        p_lo, p_hi = free_hi - TOL_WALL, free_hi
    lo = np.maximum(e_lo, p_lo)
    hi = np.minimum(e_hi, p_hi)
    w = np.maximum(0.0, hi - lo)
    covers = (lo - 1e-9 <= q) & (q <= hi + 1e-9)
    return w, covers


def residual(rows, span_m, regime='U', n=N_MC):
    """每个参数返回其期望残余宽度（对真值位置取平均）。"""
    out = []
    for r in rows:
        s = r['L'] if isinstance(span_m, dict) else span_m
        w, _ = _widths(r, float(s), regime, n=n)
        out.append(float(w.mean()))
    return np.asarray(out)


def coverage(rows, span_m, regime='U', n=N_MC):
    """真值落在区间内的比例（对参数、对真值位置同时平均）。

    这是复核里最关键的一条：只报宽度不报覆盖，会奖励「又窄又错」的区间。"""
    hit = total = 0
    for r in rows:
        s = r['L'] if isinstance(span_m, dict) else span_m
        _, cov = _widths(r, float(s), regime, n=n)
        hit += int(cov.sum())
        total += cov.size
    return hit / max(1, total)


def share_exceed(rows, span_m, tol, regime='U', n=N_MC):
    """残余宽度超过 tol 的概率（对参数、对真值位置同时平均）。"""
    hit = total = 0
    for r in rows:
        s = r['L'] if isinstance(span_m, dict) else span_m
        w, _ = _widths(r, float(s), regime, n=n)
        hit += int((w > tol).sum())
        total += w.size
    return hit / max(1, total)


def need_span(rows, tol, regime='U', target=0.05, hi=2.6, step=0.1):
    for sp in np.arange(0, hi + 1e-9, step):
        if share_exceed(rows, float(sp), tol, regime) <= target:
            return float(sp)
    return None


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else 'output/thor'
    rows = params(root)
    n_sc = len({r['scene'] for r in rows})
    print('场景 %d，物件参数 %d 条（物件 %d 件）' % (n_sc, len(rows), len(rows) // 2))
    print('几何异常（负间隙超容差）%d 条' % sum(1 for r in rows if r['geom_bad']))
    print('贴墙（该轴间隙 <= %.2f m）比例 %.1f%%' % (TOL_WALL, 100 * np.mean([r['contact'] for r in rows])))
    for regime, name in (('U', 'U：不知道贴哪面墙'), ('K', 'K：额外知道贴的是哪一面墙（诊断臂）')):
        R0 = residual(rows, 0.0, regime)
        print('%s  零跨度残余：中位 %.2f m，>0.5 m %.1f%%，>1.0 m %.1f%%，真值覆盖 %.1f%%' % (
            name, np.median(R0), 100 * np.mean(R0 > 0.5), 100 * np.mean(R0 > 1.0),
            100 * coverage(rows, 0.0, regime)))
        for tol in (0.3, 0.5, 1.0):
            sp = need_span(rows, tol, regime)
            print('    tol=%.1f m 需要统一跨度：%s' % (tol, ('%.1f m（超限比例降到 5%%）' % sp) if sp is not None else '>%.1f m 仍达不到' % 2.6))
    print('不贴墙参数的可滑动空余（中位 m / 条数）：')
    by = {}
    for r in rows:
        if not r['contact']:
            by.setdefault(r['cat'], []).append(max(0.0, r['room'] - r['L']))
    for k, v in sorted(by.items()):
        print('  %-8s %.2f / %d' % (k, np.median(v), len(v)))
