
"""Aggregate repeated realisations of the twelve-room visit-by-severity grid.

The 021 figure reported one realisation per cell, so a single 4/12 in the
fourteen-visit, severity-1 cell could come from the noise draw rather than from
the sensor level.  This module reads the three independently seeded runs and
reports, per cell, the hit count over 36 observations and the per-room paired
counts used by the axis tests.
"""
import json
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path('D:/Project/imu环境重建/output/layout-recon/matrix023')


def load(offsets=(0, 1000, 2000)):
    rows = []
    for off in offsets:
        path = ROOT / f'off{off}' / 'matrix.json'
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        for r in payload['rows']:
            if 'error' in r and r['error']:
                continue
            rows.append({'offset': off, 'room': r['room'], 'visits': r['visits'],
                         'severity': r['severity'], 'hit': bool(r['all_instances_hit']),
                         'f1': float(r['f1']), 'status': r['status']})
    return rows


def summarise(rows):
    cells = {}
    for r in rows:
        key = (r['visits'], r['severity'])
        cells.setdefault(key, []).append(r)
    out = {}
    for key, group in sorted(cells.items()):
        out[f'v{key[0]}-s{key[1]}'] = {
            'visits': key[0], 'severity': key[1], 'n': len(group),
            'hits': int(sum(g['hit'] for g in group)),
            'rate': float(np.mean([g['hit'] for g in group])),
            'f1': float(np.mean([g['f1'] for g in group]))}
    return out


def per_room(rows, visits, severity):
    counts = {}
    for r in rows:
        if r['visits'] == visits and r['severity'] == severity:
            counts.setdefault(r['room'], []).append(int(r['hit']))
    return {k: sum(v) for k, v in counts.items()}


def axis(rows, fixed, levels, axis):
    """axis='visits': compare levels of visits at fixed severity; else the reverse."""
    a, b = levels
    if axis == 'visits':
        ca, cb = per_room(rows, a, fixed), per_room(rows, b, fixed)
    else:
        ca, cb = per_room(rows, fixed, a), per_room(rows, fixed, b)
    rooms = sorted(set(ca) & set(cb))
    x = np.array([ca[r] for r in rooms]); y = np.array([cb[r] for r in rooms])
    diff = y - x
    test = stats.wilcoxon(y, x, zero_method='wilcox') if np.any(diff) else None
    return {'levels': [a, b], 'fixed': fixed, 'axis': axis, 'rooms': len(rooms),
            'per_room_low': x.tolist(), 'per_room_high': y.tolist(),
            'sum_low': int(x.sum()), 'sum_high': int(y.sum()),
            'n_obs': int(3 * len(rooms)),
            'mean_delta': float(diff.mean()),
            'p_wilcoxon': float(test.pvalue) if test else 1.0,
            'up': int((diff > 0).sum()), 'down': int((diff < 0).sum()),
            'tie': int((diff == 0).sum())}


def main():
    rows = load()
    cells = summarise(rows)
    report = {'cells': cells, 'n_rows': len(rows),
              'severity_axis': [axis(rows, 6, (0, 1), 'severity'),
                                axis(rows, 10, (0, 1), 'severity'),
                                axis(rows, 14, (0, 1), 'severity')],
              'visit_axis': [axis(rows, 0.0, (6, 14), 'visits'),
                             axis(rows, 0.5, (6, 14), 'visits'),
                             axis(rows, 1.0, (6, 14), 'visits')]}
    (ROOT / 'grid023.json').write_text(json.dumps(report, indent=1))
    for k, v in cells.items():
        print('%-10s %2d/%2d  %.3f' % (k, v['hits'], v['n'], v['rate']))
    for grp in ('severity_axis', 'visit_axis'):
        for a in report[grp]:
            print(grp, a['axis'], a['fixed'], a['levels'], '%d->%d of %d' % (a['sum_low'], a['sum_high'], a['n_obs']),
                  'up/down/tie %d/%d/%d' % (a['up'], a['down'], a['tie']), 'p=%.4f' % a['p_wilcoxon'])


if __name__ == '__main__':
    main()
