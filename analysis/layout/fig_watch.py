"""手表通道的两张证据图：跨会话可用性 + 目标房间的逐动作运动量。"""
import sys, os, json, glob
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import watch_channel as WC
from paths import REPO

matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False


def collect(root):
    rows = []
    for S in sorted(glob.glob(os.path.join(root, '*'))):
        if not os.path.exists(os.path.join(S, 'watch.jsonl')):
            continue
        acts = None
        ap = os.path.join(S, 'actions.json')
        if os.path.exists(ap):
            acts = [tuple(r) for r in json.load(open(ap, encoding='utf-8'))['runs']]
        r = WC.summarize(S, acts)
        if r and r.get('status') == 'ok':
            rows.append((os.path.basename(S), r))
    return rows


def main():
    root = os.path.join(REPO, 'output', 'layout-recon')
    rows = collect(root)
    fig, ax = plt.subplots(1, 2, figsize=(13.6, 5.6), gridspec_kw={'width_ratios': [1.35, 1]})

    names = [n for n, _ in rows]
    r0 = [r['r_zero_lag'] for _, r in rows]
    ok = [r['usable'] for _, r in rows]
    x = np.arange(len(rows))
    ax[0].bar(x, r0, color=['#2a9d8f' if u else '#c9ccd1' for u in ok], width=0.78)
    ax[0].axhline(WC.USABLE_R, color='#e76f51', lw=1.4, ls='--', label='可用门槛 r=%.2f' % WC.USABLE_R)
    ax[0].axhline(0, color='#666', lw=0.8)
    ax[0].set_xticks(x)
    ax[0].set_xticklabels(names, rotation=90, fontsize=6.4)
    ax[0].set_ylabel('零滞后相关 r（手机 vs 手表运动包络）')
    ax[0].set_title('33 个联合录音中 16 个手表可用；可用者最佳滞后=0（14/16）', fontsize=11)
    ax[0].legend(fontsize=8, loc='upper left')
    ax[0].grid(axis='y', alpha=0.25)

    S = os.path.join(root, 's-59d570ee')
    acts = [tuple(r) for r in json.load(open(os.path.join(S, 'actions.json'), encoding='utf-8'))['runs']]
    r = WC.summarize(S, acts)
    lv = r['action_level']
    order = ['walk', 'seated', 'cabinet', 'lying']
    vals = [lv[k]['level'] if lv.get(k, {}).get('level') is not None else np.nan for k in order]
    colors = ['#264653', '#e9c46a', '#e76f51', '#2a9d8f']
    b = ax[1].bar(order, vals, color=colors, width=0.62)
    for rect, v in zip(b, vals):
        if not np.isnan(v):
            ax[1].text(rect.get_x() + rect.get_width() / 2, v + 0.03, '%.2f' % v,
                       ha='center', fontsize=10)
    ax[1].set_ylabel('手表运动量  mean|‖a‖-g|')
    ax[1].set_title('目标房间 s-59d570ee：走动/静止 2.6x 可分，\n但开柜 0.60 与坐下 0.60 无法区分', fontsize=11)
    ax[1].grid(axis='y', alpha=0.25)
    ax[1].set_ylim(0, max([v for v in vals if not np.isnan(v)]) * 1.25)

    fig.tight_layout()
    out = os.path.join(root, 'watch-channel.png')
    fig.savefig(out, dpi=150)
    print('wrote', out)
    print(json.dumps({n: {'r0': round(r2['r_zero_lag'], 3), 'lag': r2['best_lag_bins'],
                          'usable': r2['usable'], 'width_ms': round(r2['offset_width_ms'], 1)}
                      for n, r2 in rows}, ensure_ascii=False, indent=0)[:600])


if __name__ == '__main__':
    main()
