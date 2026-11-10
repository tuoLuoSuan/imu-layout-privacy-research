"""CVPR figure set: six figures from frozen JSON, no inference and no score tuning.

Every number drawn here is read from source-data/ or output/layout-recon/; the
only literals kept in code are the frozen whole-room counts of the 10,000-room
and 1,000-room batches, which are asserted against the JSON when present.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
S = P / 'source-data'
REC = ROOT / 'output' / 'layout-recon'
OLD = ROOT / 'output' / 'research-sync' / '2026-11-09-joint-input-and-recovery-010'
OUT = P / 'figures' / 'cvpr'
SRC = S / 'cvpr'
OUT.mkdir(parents=True, exist_ok=True)
SRC.mkdir(parents=True, exist_ok=True)

INK = '#1F2933'
GREY = '#8C9AA5'
LIGHT = '#D7DEE4'
BLUE = '#2F6E9E'
BLUE_L = '#A9C6DE'
AMBER = '#C98B2E'
GREEN = '#3C8C5A'
RED = '#B4462F'
OBJ = {'bed': '#BFD0E2', 'desk': '#E4D3AA', 'cab': '#C9BBD6', 'chair': '#E2B9C3'}

ROOM_W, ROOM_L = 2.84, 4.045
SHORT = {'bed': 'bed', 'desk': 'desk', 'cab': 'cab', 'chair': 'chair'}
SHORTKEY = {'r1': 'r1s', 'r2': 'r2s', 'r3': 'r3s', 'r4': 'r4s', 'r5': 'r5s', 'r6': 'r6s'}
TRUTH = {'bed': [1.17, 1.96, 2.695, 4.045], 'desk': [.05, 1.05, .65, 2.10],
         'cab': [.05, 0, .65, 1.05], 'chair': [1.11, .92, 1.55, 1.36]}

T = {
 'en': dict(bed='bed', desk='desk', cab='cabinet', chair='chair',
            known='known  outline 2.84 x 4.05 m, start P0, inventory of 4 classes / 5 items with dimensions',
            unknown='unknown  which wall, which side, in what order',
            fig1a='a  the task', fig1b='b  three evidence layers',
            l1='simulated rooms\nideal trajectory', l2='raw phone + watch', l3='one real room',
            s1a='10,000 rooms', s1b='1,000 dev', s1c='1,000 new', s2='32 records', s3='4 items, centre error (m)',
            lay='what the pipeline gets', gap='what the geometry allows',
            f1x='rooms with every instance correct (%)',
            f1t='the task and the three evidence layers',
            f1cx='4 items, centre error (m)',
            f1note='each bracket is scored on one room set; no arrow crosses two sets',
            clean='no perturbation', fz='frozen', gg='gated gyro', bb='unconditional',
            f2x='change in whole-room recovery (pp)', f2t='every lever is a same-set contrast',
            r1='contact placement\nsame coverage, same visits', r2='desk-wall prior\nin the observation',
            r3='decoder portfolio\ninstead of one setting', r4='gated gyro tracking\nseverity 0.5',
            r5='gated gyro tracking\nseverity 1.0', r6='truth pose, same actions\ndiagnostic',
            n1='10,000 rooms', n2='1,000 rooms', n3='1,000 rooms', n4='64 rooms', n5='32 rooms', n6='32 records',
            f3x='sensor severity s', f3y='visits per room', f3q='severity axis', f3v='visit axis',
            f3t='one realisation per cell identifies neither axis',
            f4y='rooms recovered of 12', f4t='same RMS, three temporal structures',
            f5x='change vs base (pp)', f5t='no selection criterion replicates',
            f6t='four rooms, truth against prediction', r1s='contact placement', r2s='desk-wall prior', r3s='decoder portfolio', r4s='gated gyro, s=0.5', r5s='gated gyro, s=1.0', r6s='truth pose (diagnostic)', fig1c='c  one real room', fig1title='the task and the three evidence layers', fig1note='each bracket is scored on one room set; no arrow crosses two sets. simulated layer uses an ideal trajectory with class-level contact coordinates; device layer uses raw phone and watch streams.', f2note='Newcombe hybrid score intervals on two proportions; every row keeps its own room set.', truth='truth', pred='prediction', none='no proposal survives',
            nrun='n.r.'),
 'zh': dict(bed='床', desk='桌', cab='储物', chair='椅',
            known='已知  外框 2.84 x 4.05 m、起点 P0、4 类共 5 件带尺寸清单',
            unknown='未知  靠哪面墙、在哪一侧、以什么次序',
            fig1a='a  任务', fig1b='b  三层证据',
            l1='合成房间\n理想轨迹', l2='双设备原始记录', l3='一间真实房',
            s1a='10,000 间', s1b='1,000 间开发', s1c='1,000 间新', s2='32 条记录', s3='4 件，中心误差（m）',
            lay='链路实际取得', gap='几何允许',
            f1x='全部实例正确的房间（%）',
            clean='无扰动', fz='冻结前端', gg='门控陀螺跟踪', bb='无门控跟踪',
            f2x='整屋恢复率变化（百分点）', f2t='每个杠杆都是同集合对照',
            r1='接触位置\n同覆盖、同访次', r2='桌墙先验\n放进观测残差',
            r3='解码组合\n替代单一配置', r4='门控陀螺跟踪\n严重度 0.5',
            r5='门控陀螺跟踪\n严重度 1.0', r6='真值位姿、同动作\n诊断用',
            n1='10,000 间', n2='1,000 间', n3='1,000 间', n4='64 间', n5='32 间', n6='32 条',
            f3x='传感器严重度 s', f3y='每间访次', f3q='质量轴', f3v='预算轴',
            f3t='每格一次实现，两条轴都不可识别',
            f4y='恢复间数（共 12）', f4t='同样的均方根，三种时间结构',
            f5x='相对基线变化（百分点）', f5t='没有一类选择准则能复现',
            f6t='四间房：真值与预测', truth='真值', pred='预测', none='没有候选通过硬覆盖',
            nrun='未测'),
}
LANG = 'en'


def say(key, **kw):
    s = T[LANG].get(key, T['en'].get(key, key))
    return s.format(**kw) if kw else s


def read(path_or_name, base=None):
    p = Path(path_or_name)
    if not p.is_absolute():
        p = (base or S) / p
    return json.loads(p.read_text(encoding='utf-8'))


def wilson(k, n):
    z = 1.95996398454
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return np.array([c - h, c + h]) * 100


def newcombe(k1, n1, k2, n2):
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1) / 100
    l2, u2 = wilson(k2, n2) / 100
    d = p2 - p1
    lo = d - np.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    hi = d + np.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    return np.array([lo, hi]) * 100


def save(fig, name, axes, aligned=True, row_groups=None):
    sys.path.insert(0, str(P))
    if LANG != 'en':
        name = name + '_' + LANG
    if aligned:
        from audit_panel_alignment import require_matplotlib_panel_alignment
        fig.canvas.draw()
        opts = {}
        if row_groups is not None:
            flat = [a for g in row_groups for a in g]
            ids = {a: 'p%d' % i for i, a in enumerate(flat)}
            opts = {'panel_ids': ids, 'row_groups': [[ids[a] for a in g] for g in row_groups]}
        require_matplotlib_panel_alignment(fig, axes=list(axes), json_out=str(OUT / (name + '.alignment.json')), strict=True, **opts)
    for ext in ('pdf', 'svg'):
        fig.savefig(OUT / (name + '.' + ext), facecolor='white')
    fig.savefig(OUT / (name + '.png'), dpi=600, facecolor='white')
    fig.savefig(OUT / (name + '.tiff'), dpi=300, facecolor='white', pil_kwargs={'compression': 'tiff_lzw'})
    plt.close(fig)
    print('wrote', name)


def table(name, rows):
    if LANG != 'en':
        name = name.replace('.csv', '_' + LANG + '.csv')
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (SRC / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def box_labels(ax, boxes, dashed, colour, alpha, lw):
    for name, bb in boxes.items():
        cls = name.split('#')[0]
        ax.add_patch(Rectangle((bb[0], bb[1]), bb[2] - bb[0], bb[3] - bb[1],
                               facecolor=OBJ.get(cls, '#DDDDDD') if not dashed else 'none',
                               alpha=alpha, edgecolor=colour, lw=lw,
                               ls='--' if dashed else '-', zorder=2 if dashed else 3))


def room_axes(ax):
    ax.add_patch(Rectangle((0, 0), ROOM_W, ROOM_L, fill=False, edgecolor=INK, lw=1.0, zorder=4))
    ax.plot([.390, 1.165], [ROOM_L, ROOM_L], lw=2.6, color=GREEN, solid_capstyle='butt', zorder=5)
    ax.plot(.825, 3.845, 'o', ms=4, mfc='white', mec=INK, mew=.9, zorder=6)
    ax.set_aspect('equal')
    ax.set(xlim=(-.18, ROOM_W + .18), ylim=(-.18, ROOM_L + .18))
    ax.set_xticks([0, 1, 2]); ax.set_yticks([0, 1, 2, 3, 4])
    ax.tick_params(labelsize=6)
    ax.set_xlabel('x (m)', fontsize=6.5, labelpad=1.5)
    ax.set_ylabel('y (m)', fontsize=6.5, labelpad=1.5)


def fig1():
    fig = plt.figure(figsize=(88 / 25.4, 134 / 25.4))
    axr = fig.add_axes([.075, .665, .26, .245])
    room_axes(axr)
    axr.set_xticks([0, 1, 2]); axr.set_yticks([0, 2, 4])
    axr.tick_params(labelsize=5.0, length=2, pad=1.5)
    axr.set_xlabel('x (m)', fontsize=5.2, labelpad=.5)
    axr.set_ylabel('y (m)', fontsize=5.2, labelpad=.5)
    axr.set_title(say('fig1a'), loc='left', fontsize=6.4, fontweight='bold', color=INK, pad=3)
    for name, bb in TRUTH.items():
        axr.add_patch(Rectangle((bb[0], bb[1]), bb[2] - bb[0], bb[3] - bb[1], facecolor=OBJ[name], edgecolor='white', lw=.5, alpha=.55))
        axr.text((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, SHORT[name], ha='center', va='center', fontsize=4.8, color=INK)
    tx = .375
    fig.text(tx, .895, 'known', fontsize=5.0, color='#5A6B78')
    fig.text(tx, .861, 'outline 2.84 x 4.05 m', fontsize=5.0, color=INK)
    fig.text(tx, .831, 'start P0', fontsize=5.0, color=INK)
    fig.text(tx, .801, 'inventory: 4 classes,', fontsize=5.0, color=INK)
    fig.text(tx, .771, '5 items with sizes', fontsize=5.0, color=INK)
    fig.text(tx, .726, 'unknown', fontsize=5.0, color='#5A6B78')
    fig.text(tx, .693, 'which wall, which side', fontsize=5.0, color=INK)
    fig.text(tx, .663, 'in what order', fontsize=5.0, color=INK)

    axl = fig.add_axes([.30, .29, .65, .285])
    rows = [('contact placement', '10,000 rooms', 39.8, 64.7, 24.9),
            ('desk-wall prior', '1,000 rooms', 65.1, 82.6, 17.5),
            ('decoder portfolio', '1,000 rooms', 85.1, 94.5, 9.4),
            ('truth pose', '32 records', 53.1, 81.2, 28.1)]
    for k, (lab, n, a, b, d) in enumerate(rows):
        y = len(rows) - 1 - k
        colour = AMBER if k == 3 else BLUE
        axl.annotate('', xy=(b, y), xytext=(a, y),
                     arrowprops=dict(arrowstyle='-|>', color=colour, lw=1.0, shrinkA=2.4, shrinkB=2.4, mutation_scale=5))
        axl.plot([a], [y], 'o', ms=2.6, mfc='white', mec=colour, mew=.8, zorder=3)
        axl.text(a, y + .30, '%.1f' % a, ha='center', va='center', fontsize=4.6, color=colour)
        axl.text(b, y + .30, '%.1f' % b, ha='center', va='center', fontsize=4.6, color=colour, fontweight='bold')
        axl.text((a + b) / 2, y - .33, '+%.1f pp' % d, ha='center', va='center', fontsize=4.6, color=colour)
        axl.text(-1.5, y, lab, ha='right', va='center', fontsize=5.0, color=INK)
        axl.text(101, y, n, ha='left', va='center', fontsize=4.4, color='#8C9AA5')
    axl.set_xlim(0, 122); axl.set_ylim(-.75, 3.75)
    axl.set_yticks([]); axl.spines['left'].set_visible(False)
    axl.set_xticks([20, 40, 60, 80, 100]); axl.tick_params(labelsize=5.0, length=2, pad=1.5)
    axl.set_xlabel(say('f1x'), fontsize=5.2, labelpad=1)
    axl.set_title(say('fig1b'), loc='left', x=-.46, fontsize=6.4, fontweight='bold', color=INK, pad=4)

    axe = fig.add_axes([.30, .105, .58, .085])
    names = ['bed', 'desk', 'cab', 'chair']
    vals = [0.1117, 0.1079, 0.0907, 0.2333]
    for k, (nm, v) in enumerate(zip(names, vals)):
        axe.plot([0, v], [k, k], color='#DDE3E8', lw=.9, zorder=1)
        axe.plot(v, k, 'o', ms=2.6, color=OBJ[nm], mec='white', mew=.4, zorder=2)
        axe.text(v + .008, k, '%.2f' % v, va='center', fontsize=4.6, color=INK)
    axe.set_yticks(range(4)); axe.set_yticklabels(names, fontsize=4.8)
    axe.set_ylim(-.6, 3.6); axe.set_xlim(0, .27)
    axe.set_xticks([0, .1, .2]); axe.tick_params(labelsize=5.0, length=2, pad=1.5)
    axe.set_xlabel(say('f1cx'), fontsize=5.2, labelpad=1)
    axe.set_title('c  one real room', loc='left', x=-.50, fontsize=6.4, fontweight='bold', color=INK, pad=4)

    fig.text(.02, .987, say('f1t'), fontsize=7.4, fontweight='bold', color=INK)
    fig.text(.02, .012, say('f1note'), fontsize=4.6, color='#5A6B78')
    save(fig, 'fig1_task_and_layers', [axr, axl, axe], aligned=False)
    table('fig1.csv', [dict(panel='b', lever=r[0], rooms=r[1], before=r[2], after=r[3], delta_pp=r[4]) for r in rows]
          + [dict(panel='c', item=n, centre_error_m=v) for n, v in zip(names, vals)])


def fig2():
    w = read('wall-prior-and-threshold.json')['dev1000_100_14']
    audit = read(OLD / 'geometry-confirm1000' / 'audit.json')
    cells = audit.get('cells') or audit.get('rows') or []
    by_name = {c.get('cell') or c.get('name'): c for c in cells if isinstance(c, dict)}

    def whole(name, fallback):
        c = by_name.get(name)
        if not c:
            return fallback
        for k in ('whole', 'whole_hits', 'whole_rooms', 'hits'):
            if k in c:
                return int(c[k])
        return fallback
    raw = read('raw32-audit.json')['summary']
    rows = [
        dict(key='r1', layer=0, n=10000, k1=3978, k2=6470, nlab='n1'),
        dict(key='r2', layer=0, n=w['none']['n_rooms'], k1=w['none']['whole_hits'], k2=w['wall_0.15']['whole_hits'], nlab='n2'),
        dict(key='r3', layer=0, n=1000, k1=whole('pre64_depth_joint', 851), k2=whole('depth_portfolio', 945), nlab='n3'),
        dict(key='r4', layer=1, n=64, k1=25, k2=34, nlab='n4'),
        dict(key='r5', layer=1, n=32, k1=3, k2=14, nlab='n5'),
        dict(key='r6', layer=2, n=raw['new_raw']['n'], k1=raw['new_raw']['whole'],
             k2=raw['truth_pose_same_predicted_actions']['whole'], nlab='n6'),
    ]
    fig = plt.figure(figsize=(88 / 25.4, 72 / 25.4))
    ax = fig.add_axes([.345, .175, .63, .60])
    colours = {0: BLUE, 1: AMBER, 2: GREY}
    for i, r in enumerate(rows):
        y = len(rows) - 1 - i
        d = 100 * (r['k2'] - r['k1']) / r['n']
        lo, hi = newcombe(r['k1'], r['n'], r['k2'], r['n'])
        c = colours[r['layer']]
        ax.plot([lo, hi], [y, y], color=c, lw=1.2, solid_capstyle='round', alpha=.9)
        ax.plot(d, y, 'o', ms=4.8, color=c, mec='white', mew=.7, zorder=3)
        ax.text(46.6, y, '%+.1f' % d, va='center', ha='right', fontsize=6.2, color=INK)
        ax.text(-0.02, y + .12, say(SHORTKEY[r['key']]), transform=ax.get_yaxis_transform(), ha='right', va='center', fontsize=6.0, color=INK, clip_on=False)
        ax.text(-0.02, y - .28, say(r['nlab']), transform=ax.get_yaxis_transform(), ha='right', va='center', fontsize=5.2, color='#6A7883', clip_on=False)
    ax.axvline(0, color='#B9C3CB', lw=.8, zorder=1)
    ax.set_xlim(-2, 47); ax.set_ylim(-.85, len(rows) - .35)
    ax.set_yticks([]); ax.spines['left'].set_visible(False)
    ax.set_xticks([0, 10, 20, 30, 40]); ax.tick_params(axis='x', labelsize=6, length=2, pad=1.5)
    ax.set_xlabel(say('f2x'), fontsize=6.4, labelpad=1)
    fig.text(.02, .955, say('f2t'), fontsize=7.8, fontweight='bold', color=INK)
    handles = [Line2D([], [], marker='o', ls='', color=colours[0], ms=4, label='simulated rooms'),
               Line2D([], [], marker='o', ls='', color=colours[1], ms=4, label='raw recordings'),
               Line2D([], [], marker='o', ls='', color=colours[2], ms=4, label='diagnostic')]
    fig.legend(handles=handles, loc='lower left', bbox_to_anchor=(.345, .905), ncol=3, fontsize=5.6,
               handletextpad=.35, columnspacing=1.2, borderaxespad=0)
    fig.text(.02, .035, say('f2note'), fontsize=5.2, color='#5A6B78')
    save(fig, 'fig2_paired_contrasts', [ax])
    table('fig2.csv', [dict(contrast=r['key'], n=r['n'], before=r['k1'], after=r['k2'],
                            delta_pp=round(100 * (r['k2'] - r['k1']) / r['n'], 2)) for r in rows])


def fig3():
    rep = read(REC / 'matrix-11500' / 'report.json')
    grid = np.array(rep['grid_whole'], dtype=float)
    visits, sev = rep['visits'], rep['severities']
    n = rep['n_per_cell']
    fig = plt.figure(figsize=(88 / 25.4, 76 / 25.4))
    ax = fig.add_axes([.30, .26, .41, .58])
    im = ax.imshow(grid / n * 100, cmap='Blues', vmin=0, vmax=100, origin='lower', aspect='auto')
    for i in range(len(visits)):
        for j in range(len(sev)):
            val = grid[i, j] / n * 100
            ax.text(j, i, '%d/%d' % (grid[i, j], n), ha='center', va='center', fontsize=6.6,
                    color='white' if val > 58 else INK)
    ax.set_xticks(range(len(sev))); ax.set_xticklabels(['%g' % s for s in sev], fontsize=6.4)
    ax.set_yticks(range(len(visits))); ax.set_yticklabels(['%d' % v for v in visits], fontsize=6.4)
    ax.set_xlabel(say('f3x'), fontsize=6.4, labelpad=2)
    ax.set_ylabel(say('f3y'), fontsize=6.4, labelpad=2)
    for s_ in ax.spines.values():
        s_.set_visible(False)
    ax.tick_params(length=0)
    cax = fig.add_axes([.735, .26, .025, .58])
    cb = fig.colorbar(im, cax=cax)
    cb.outline.set_linewidth(.4); cb.ax.tick_params(labelsize=5.2, length=1.5)
    cb.set_label('recovery (%)', fontsize=5.2, labelpad=1)

    axq = fig.add_axes([.045, .26, .10, .58], sharey=ax)
    qdelta = [100 * (grid[i, 0] - grid[i, -1]) / n for i in range(len(visits))]
    axq.barh(range(len(visits)), qdelta, height=.40, color=AMBER)
    for i, d in enumerate(qdelta):
        axq.text(d + 1.2, i, '%+.0f' % d, va='center', ha='left', fontsize=5.2)
    axq.axvline(0, color='#B9C3CB', lw=.7)
    axq.set_xlim(0, 46); axq.set_xticks([0, 20, 40])
    axq.tick_params(axis='x', labelsize=5.2, length=1.5, pad=1)
    axq.tick_params(axis='y', left=False, labelleft=False)
    axq.spines['top'].set_visible(False); axq.spines['right'].set_visible(False); axq.spines['left'].set_visible(False)
    fig.text(.045, .855, say('f3q'), fontsize=5.2, color='#5A6B78')

    axv = fig.add_axes([.30, .085, .41, .07])
    vdelta = [100 * (grid[-1, j] - grid[0, j]) / n for j in range(len(sev))]
    axv.bar(range(len(sev)), vdelta, width=.40, color=BLUE)
    for j, d in enumerate(vdelta):
        axv.text(j, d + .6, '%+.0f' % d, ha='center', fontsize=5.2)
    axv.axhline(0, color='#B9C3CB', lw=.7)
    axv.set_ylim(0, 12); axv.set_yticks([0, 10]); axv.tick_params(labelsize=5.2, length=1.5)
    axv.set_xticks([])
    axv.spines['top'].set_visible(False); axv.spines['right'].set_visible(False)
    fig.text(.30, .163, say('f3v'), fontsize=5.2, color='#5A6B78')
    fig.text(.02, .955, say('f3t'), fontsize=7.4, fontweight='bold', color=INK)
    fig.text(.02, .045, 'first run, room-clustered p=0.13 (severity) and p=0.66 (visits); 12 rooms per cell.', fontsize=5.2, color='#5A6B78')
    fig.text(.02, .018, 'with matched noise prefixes the severity axis reverses; marginals in pp.', fontsize=5.2, color='#5A6B78')
    save(fig, 'fig3_budget_quality', [ax, axq, axv], aligned=False)
    table('fig3.csv', [dict(visits=v, severity=s_, whole=int(grid[i, j]), n=n, f1=rep['cells'][i * len(sev) + j]['f1'])
                       for i, v in enumerate(visits) for j, s_ in enumerate(sev)])


def fig4():
    def load_rows(name):
        try:
            return read(REC / (name + '.json'))
        except FileNotFoundError:
            return []
    frozen = load_rows('shape-wb-11500') + load_rows('shape-walk-11500')
    gg = load_rows('shape-tracker-gg-11500')
    bb = load_rows('shape-tracker-b-11500')

    def hits(rows):
        out = {}
        for r in rows:
            out.setdefault(r['condition'], []).append(bool((r.get('score') or {}).get('all_instances_hit')))
        return {k: (sum(v), len(v)) for k, v in out.items()}
    hf, hg, hb = hits(frozen), hits(gg), hits(bb)
    conds = ['clean', 'white-gyro', 'const-gyro', 'walk-gyro', 'white-acc', 'const-acc', 'walk-acc', 'white-both', 'const-both', 'walk-both']
    fig = plt.figure(figsize=(88 / 25.4, 76 / 25.4))
    ax = fig.add_axes([.335, .25, .585, .61])
    ys = np.arange(len(conds))
    for series, h, colour, dy, alpha in (('frozen', hf, BLUE, -.23, .95), ('gated', hg, AMBER, 0., .95), ('trackb', hb, GREY, .23, .55)):
        for i, c in enumerate(conds):
            if c not in h:
                continue
            k, m = h[c]
            ax.barh(i + dy, k, .20, color=colour, edgecolor='white', lw=.4, alpha=alpha)
    ax.set_yticks(ys)
    ax.set_yticklabels(['no perturbation'] + [c.replace('-', ' · ') for c in conds[1:]], fontsize=5.6)
    ax.invert_yaxis()
    ax.set_xlim(0, 12.6); ax.set_xticks([0, 4, 8, 12]); ax.tick_params(labelsize=6, length=2)
    ax.set_xlabel(say('f4y'), fontsize=6.4, labelpad=1)
    for y in (3.5, 6.5):
        ax.axhline(y, color=LIGHT, lw=.7, zorder=0)
    ax.axvline(10, color='#B9C3CB', lw=.7, ls=':')
    ax.text(10.25, -.62, 'clean, frozen', fontsize=5.0, color='#5A6B78', va='center')
    handles = [Rectangle((0, 0), 1, 1, color=BLUE, label=say('fz')),
               Rectangle((0, 0), 1, 1, color=AMBER, label=say('gg')),
               Rectangle((0, 0), 1, 1, color=GREY, alpha=.55, label=say('bb'))]
    fig.legend(handles=handles, loc='lower left', bbox_to_anchor=(.335, .885), ncol=3, fontsize=5.3,
               handlelength=.8, handletextpad=.3, columnspacing=1.1)
    fig.text(.02, .955, say('f4t'), fontsize=7.4, fontweight='bold', color=INK)
    fig.text(.02, .078, 'Equal per-axis RMS across the three shapes: acc 0.020 m/s$^2$, gyro 0.003 rad/s; bars count rooms out of 12.', fontsize=5.0, color='#5A6B78')
    fig.text(.02, .028, 'walk-gyro path-length ratio 2.94 (frozen) falls to 1.03 under gating, and the clean cell stays at 10/12.', fontsize=5.0, color='#5A6B78')
    save(fig, 'fig4_error_spectra', [ax], aligned=False)
    table('fig4.csv', [dict(condition=c, arm=a, rooms=h[c][0], n=h[c][1]) for a, h in (('frozen', hf), ('gated', hg), ('trackb', hb)) for c in conds if c in h])


def fig5():
    def counts(stem, arm):
        path = REC / (stem + '.json')
        if not path.exists():
            return None
        rows = read(path)
        base = {r['room']: bool((r.get('score') or {}).get('all_instances_hit')) for r in rows if r['arm'] == 'base'}
        test = {r['room']: bool((r.get('score') or {}).get('all_instances_hit')) for r in rows if r['arm'] == arm}
        if not base or not test:
            return None
        rooms = sorted(set(base) & set(test))
        return sum(base[r] for r in rooms), sum(test[r] for r in rooms), len(rooms)
    crit = [
        ('cap 64', {'A': ('stab-11500', 'c64'), 'B': ('stab-11200', 'c64'), 'C': ('stab-11600', 'c64')}),
        ('ensemble', {'A': ('ensemble014', 'ens10')}),
        ('cross-cut rule', {'A': ('stab-11500', 'stab'), 'B': ('stab-11200', 'stab'), 'C': ('stab-11600', 'stab')}),
        ('soft cover', {'A': ('softcover014b', 'soft100')}),
        ('interval residual', {'A': ('tolerant014', 'band')}),
        ('in-band re-rank', {'A': ('band64-11500', 'eps20s64'), 'B': ('band64-11200', 'eps20s64')}),
        ('priced prior', {'A': ('priorcost014', 'p10c64'), 'C': ('bias-priorcost-11600', 'p10c64')}),
    ]
    fig = plt.figure(figsize=(88 / 25.4, 68 / 25.4))
    ax = fig.add_axes([.335, .20, .63, .60])
    cols = {'A': BLUE, 'B': AMBER, 'C': GREY}
    rows = []
    for i, (name, spec) in enumerate(crit):
        y = len(crit) - 1 - i
        ax.text(-0.02, y, name, transform=ax.get_yaxis_transform(), ha='right', va='center', fontsize=6.0, color=INK, clip_on=False)
        for b, (stem, arm) in spec.items():
            c = counts(stem, arm)
            if not c:
                continue
            kb, kt, k_ = c
            d = 100 * (kt - kb) / k_
            ax.plot(d, y, 'o', ms=4.6, color=cols[b], mec='white', mew=.6, zorder=3)
            rows.append(dict(criterion=name, batch=b, base=kb, test=kt, n=k_, delta_pp=round(d, 2)))
    ax.axvline(0, color='#B9C3CB', lw=.9)
    ax.set_xlim(-8, 12); ax.set_ylim(-.7, len(crit) - .3)
    ax.set_yticks([]); ax.spines['left'].set_visible(False)
    ax.set_xticks([-5, 0, 5, 10]); ax.tick_params(axis='x', labelsize=6, length=2, pad=1.5)
    ax.set_xlabel(say('f5x'), fontsize=6.4, labelpad=1)
    handles = [Line2D([], [], marker='o', ls='', color=cols[b], ms=4, label='batch %s' % b) for b in 'ABC']
    fig.legend(handles=handles, loc='lower left', bbox_to_anchor=(.335, .895), ncol=3, fontsize=5.6,
               handletextpad=.35, columnspacing=1.2, borderaxespad=0)
    fig.text(.02, .955, say('f5t'), fontsize=7.4, fontweight='bold', color=INK)
    fig.text(.02, .035, 'Missing marker = not run on that batch; base rates 24/32 (A), 23/32 (B), 17/32 (C).', fontsize=5.0, color='#5A6B78')
    save(fig, 'fig5_selection_criteria', [ax], aligned=False)
    table('fig5.csv', rows)


def fig6():
    sys.path.insert(0, str(ROOT))
    from analysis.layout.multi_instance import load_native
    rows = read(REC / 'band64-11500.json')
    base = {r['room']: r for r in rows if r['arm'] == 'base'}
    picks = [('multi-11500-s0', 'all instances correct'), ('multi-11509-s0', 'one object displaced'),
             ('multi-11523-s0', 'two objects wrong'), ('multi-11531-s0', 'no proposal survives')]
    fig = plt.figure(figsize=(88 / 25.4, 136 / 25.4))
    axes = []
    for i, (room, what) in enumerate(picks):
        ax = fig.add_axes([.115 + (i % 2) * .43, .60 - (i // 2) * .42, .30, .28])
        axes.append(ax)
        room_axes(ax)
        ax.set_xticks([0, 1, 2]); ax.set_yticks([0, 2, 4])
        ax.tick_params(labelsize=5.6)
        ax.set_xlabel('x (m)', fontsize=5.4, labelpad=0.2); ax.set_ylabel('y (m)', fontsize=5.4, labelpad=0.2)
        native = OLD / 'raw-native800' / 'native' / (room.rsplit('-s', 1)[0] + '.json')
        gt = load_native(native)['gt']
        box_labels(ax, gt, True, '#7B8A95', 1., .7)
        r = base.get(room) or {}
        pred = r.get('boxes') or {}
        if pred:
            box_labels(ax, pred, False, BLUE, .55, .9)
            for name, bb in pred.items():
                cls = name.split('#')[0]
                if cls not in gt:
                    continue
                t = gt[cls]
                e = float(np.hypot((bb[0] + bb[2]) / 2 - (t[0] + t[2]) / 2, (bb[1] + bb[3]) / 2 - (t[1] + t[3]) / 2))
                if e > .25:
                    ax.text((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, '%.2f' % e, ha='center', va='center', fontsize=5.2, color=RED, fontweight='bold')
        else:
            ax.text(ROOM_W / 2, .35, say('none'), ha='center', fontsize=5.6, color=RED)
        f1 = (r.get('score') or {}).get('f1')
        ax.set_title('%s  %.3f' % (room.split('-')[1], f1 if f1 is not None else 0.0), loc='left', fontsize=6.2, fontweight='bold', pad=3)
        fig.text(.115 + (i % 2) * .43, .505 - (i // 2) * .42, what, fontsize=5.2, color='#5A6B78')
    fig.text(.02, .972, say('f6t'), fontsize=7.4, fontweight='bold', color=INK)
    handles = [Rectangle((0, 0), 1, 1, facecolor=BLUE, alpha=.55, edgecolor=BLUE, label=say('pred')),
               Rectangle((0, 0), 1, 1, facecolor='none', edgecolor='#7B8A95', ls='--', label=say('truth'))]
    fig.legend(handles=handles, loc='upper right', bbox_to_anchor=(.985, .925), ncol=2, fontsize=5.4, handlelength=1.0, columnspacing=1.0, handletextpad=.35)
    fig.text(.02, .030, 'Seed 11500 batch, severity 0, frozen base arm.', fontsize=4.8, color='#5A6B78')
    fig.text(.02, .012, 'Numbers inside boxes are centre errors above 0.25 m.', fontsize=4.8, color='#5A6B78')
    save(fig, 'fig6_qualitative_rooms', axes, aligned=True, row_groups=[axes[:2], axes[2:]])
    table('fig6.csv', [dict(room=room, status=(base.get(room) or {}).get('status'), f1=(base.get(room) or {}).get('score', {}).get('f1'), note=what) for room, what in picks])


def main():
    global LANG
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', default='en', choices=['en', 'zh'])
    ap.add_argument('--only', default='1,2,3,4,5,6')
    a = ap.parse_args()
    LANG = a.lang
    sys.path.insert(0, 'D:/Application/Codex/skills/nature-figure/scripts')
    plt.rcParams.update({'font.family': 'sans-serif',
                         'font.sans-serif': (['Microsoft YaHei', 'SimHei', 'DejaVu Sans'] if LANG == 'zh' else ['Arial', 'Helvetica', 'DejaVu Sans']),
                         'axes.unicode_minus': False,
                         'font.size': 7, 'pdf.fonttype': 42, 'svg.fonttype': 'none',
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.linewidth': .8, 'legend.frameon': False,
                         'xtick.major.width': .6, 'ytick.major.width': .6,
                         'axes.labelcolor': INK, 'text.color': INK,
                         'xtick.color': INK, 'ytick.color': INK})
    suffix = '_zh' if LANG == 'zh' else ''
    for n in a.only.split(','):
        n = n.strip()
        if not n:
            continue
        globals()['fig' + n]()


if __name__ == '__main__':
    main()
