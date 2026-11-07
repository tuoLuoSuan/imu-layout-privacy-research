# 泄露曲线：一个家具参数在「活动跨度 span」之下还剩下多少不确定性。
# 逐轴：朝向墙的法向被墙定死（残余 0）；沿墙方向物体可以在 [0, room-L] 内滑动，
#       而若干次交互给出的锚点只能把位置夹到 L-span 以内。
#       resid = min( room - L , max(0, L - span) )
# 于是「需要多少活动」这件事有了两条上界：房间把它夹住，物体自身把它夹住。
import glob, json, os, sys
import numpy as np

TOL_WALL = 0.10
CATS = ('Bed', 'Desk', 'Cabinet', 'Chair', 'Shelf')


def rooms(root):
    out = []
    for f in sorted(glob.glob(os.path.join(root, 'FloorPlan*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        if 'objects' not in d:
            continue
        fx0, fz0, fx1, fz1 = d['floor']
        out.append((os.path.basename(f)[:-5], (fx0, fx1, fz0, fz1), d['objects']))
    return out


def params(root, cats=CATS):
    """每个 (物件, 轴) 一行：L、房间长、贴墙否、可滑动的空余。"""
    rows = []
    for scene, (fx0, fx1, fz0, fz1), objs in rooms(root):
        for o in objs:
            if o['type'] not in cats:
                continue
            c, s = o['center'], o['size']
            box = (c['x'] - s['x'] / 2, c['z'] - s['z'] / 2, c['x'] + s['x'] / 2, c['z'] + s['z'] / 2)
            room = (fx0, fz0, fx1, fz1)
            for axis in (0, 1):
                lo, hi = box[axis], box[axis + 2]
                L = float(hi - lo)
                room_len = float(room[axis + 2] - room[axis])
                gap = min(lo - room[axis], room[axis + 2] - hi)
                pinned = bool(gap <= TOL_WALL)
                rows.append(dict(scene=scene, cat=o['type'], axis=axis, L=L, room=room_len,
                                 pinned=pinned, gap=float(gap),
                                 slide=0.0 if pinned else max(0.0, room_len - L)))
    return rows


def residual(rows, span_m):
    """span_m 可以是标量（所有参数同一跨度）或按物件类型给的字典。"""
    out = []
    for r in rows:
        if r['pinned']:
            out.append(0.0)
            continue
        s = span_m[r['cat']] if isinstance(span_m, dict) else span_m
        s = min(s, r['L'])                     # 跨度不可能超过物体自身的长度
        out.append(min(r['slide'], max(0.0, r['L'] - s)))
    return np.asarray(out)


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else 'output/thor'
    rows = params(root)
    R = residual(rows, 0.0)
    print('场景 %d，物件参数 %d 条（物件 %d 件）' % (
        len({r['scene'] for r in rows}), len(rows), len(rows) // 2))
    print('贴墙（法向被定死）的比例 %.1f%%' % (100 * np.mean([r['pinned'] for r in rows])))
    print('零活动时残余：中位 %.2f m，>0.5 m 占 %.1f%%，>1.0 m 占 %.1f%%' % (
        np.median(R), 100 * np.mean(R > 0.5), 100 * np.mean(R > 1.0)))
    for tol in (0.3, 0.5, 1.0):
        print('  tol=%.1f m 需要的最小统一跨度：' % tol, end=' ')
        for sp in np.arange(0, 2.61, 0.2):
            if np.mean(residual(rows, float(sp)) > tol) <= 0.05:
                print('%.1f m（残余超限比例降到 5%%）' % sp)
                break
        else:
            print('>2.6 m 仍达不到')
    by = {}
    for r in rows:
        if not r['pinned']:
            by.setdefault(r['cat'], []).append(r['slide'])
    print('不贴墙参数的可滑动空余（中位 m / 条数）：')
    for k, v in sorted(by.items()):
        print('  %-8s %.2f / %d' % (k, np.median(v), len(v)))
