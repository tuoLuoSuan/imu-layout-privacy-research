"""Summarise a replicated visit-by-severity grid from one or more matrix runs.

matrix016.py writes one matrix.json per noise offset.  This module reads any
number of them, aggregates whole-room hits per cell over realisations, keeps the
per-room counts used by the paired tests, and reports the two axis contrasts and
the difference-in-differences interaction with an exact sign-flip test.
"""
import argparse
import json
from itertools import product
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

CELLS = ((6, 0.0), (6, 0.5), (6, 1.0), (10, 0.0), (10, 0.5), (10, 1.0),
         (14, 0.0), (14, 0.5), (14, 1.0))


def load(paths):
    rows = []
    for p in paths:
        payload = json.loads(Path(p).read_text())
        rows.extend(payload["rows"])
    return rows


def per_room(rows, visits, severity):
    out = {}
    for r in rows:
        if int(r["visits"]) != visits or abs(float(r["severity"]) - severity) > 1e-9:
            continue
        if "error" in r:
            continue
        out.setdefault(int(r["room"]), []).append(1 if r["all_instances_hit"] else 0)
    return out


def sign_flip_exact(values):
    d = [v for v in values if v != 0]
    if not d:
        return 1.0
    d = np.asarray(d, float)
    obs = abs(d.sum())
    n = len(d)
    count = 0
    for signs in product((-1.0, 1.0), repeat=n):
        if abs((d * np.asarray(signs)).sum()) >= obs - 1e-12:
            count += 1
    return count / 2 ** n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', nargs='+', required=True)
    ap.add_argument('--rooms', default=None, help='comma list or lo-hi; default all seen')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    rows = load(a.runs)
    rooms = sorted({int(r['room']) for r in rows})
    if a.rooms:
        keep = set()
        for chunk in a.rooms.split(','):
            if '-' in chunk:
                lo, hi = chunk.split('-')
                keep.update(range(int(lo), int(hi) + 1))
            else:
                keep.add(int(chunk))
        rooms = [r for r in rooms if r in keep]
    cells = {}
    per = {}
    for v, s in CELLS:
        p = per_room(rows, v, s)
        p = {r: x for r, x in p.items() if r in rooms}
        per[(v, s)] = p
        hits = sum(sum(x) for x in p.values())
        obs = sum(len(x) for x in p.values())
        cells[f'{v}-{s}'] = {'rooms': len(p), 'observations': obs, 'hits': int(hits),
                             'rate': None if not obs else float(hits) / obs}
    report = {'runs': a.runs, 'rooms': len(rooms), 'cells': cells, 'tests': {}}

    def counts(v, s):
        p = per[(v, s)]
        return np.array([sum(p[r]) for r in sorted(p)], float)

    def wilcox(a_arr, b_arr, label):
        try:
            stat, p = wilcoxon(a_arr, b_arr)
        except ValueError:
            stat, p = float('nan'), 1.0
        return {'label': label, 'n': int(len(a_arr)), 'better': int((a_arr > b_arr).sum()),
                'worse': int((a_arr < b_arr).sum()), 'tie': int((a_arr == b_arr).sum()),
                'p': float(p)}

    for s in (0.0, 0.5, 1.0):
        c6, c14 = counts(6, s), counts(14, s)
        if len(c6) == len(c14) and len(c6):
            report['tests'][f'visits6to14_s{s}'] = wilcox(c14, c6, f'visits 6->14 at severity {s}')
    for v in (6, 10, 14):
        c0, c1 = counts(v, 0.0), counts(v, 1.0)
        if len(c0) == len(c1) and len(c0):
            report['tests'][f'sev0to1_v{v}'] = wilcox(c1, c0, f'severity 0->1 at {v} visits')
    # difference-in-differences per room
    inter = []
    for r in rooms:
        a_ = per[(14, 1.0)].get(r)
        b_ = per[(6, 1.0)].get(r)
        c_ = per[(14, 0.0)].get(r)
        d_ = per[(6, 0.0)].get(r)
        if None in (a_, b_, c_, d_):
            continue
        inter.append((sum(a_) - sum(b_)) - (sum(c_) - sum(d_)))
    report['tests']['interaction'] = {'values': inter, 'mean': float(np.mean(inter)) if inter else None,
                                      'negative': int(sum(1 for x in inter if x < 0)),
                                      'zero': int(sum(1 for x in inter if x == 0)),
                                      'positive': int(sum(1 for x in inter if x > 0)),
                                      'sign_flip_exact_p': sign_flip_exact(inter)}
    Path(a.out).write_text(json.dumps(report, indent=1))
    print(json.dumps({'cells': cells, 'tests': {k: v for k, v in report['tests'].items()}}, indent=1)[:2400])


if __name__ == '__main__':
    main()
