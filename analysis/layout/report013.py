"""Summary, Wilson intervals, paired tables and failure anatomy for 013."""
import argparse
import glob
import json
from pathlib import Path
import numpy as np
from scipy.stats import binomtest, norm


def wilson(k, n, z=1.96):
    if not n:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [float((c - r) / d), float((c + r) / d)]


def load(directory):
    out = []
    for f in sorted(glob.glob(str(Path(directory) / 'multi-11*.json'))):
        out.append(json.loads(Path(f).read_text(encoding='utf-8')))
    return out


def paired(records, a, b):
    ra = {q['scene']: r['score']['all_instances_hit'] for q in records for r in q['rows'] if r['arm'] == a}
    rb = {q['scene']: r['score']['all_instances_hit'] for q in records for r in q['rows'] if r['arm'] == b}
    keys = sorted(set(ra) & set(rb))
    both = sum(ra[k] and rb[k] for k in keys); only_a = sum(ra[k] and not rb[k] for k in keys)
    only_b = sum(rb[k] and not ra[k] for k in keys); neither = sum(not ra[k] and not rb[k] for k in keys)
    n = len(keys); disc = only_a + only_b
    p = binomtest(min(only_a, only_b), disc).pvalue if disc else 1.0
    return {'n': n, 'both': both, 'only_' + a: only_a, 'only_' + b: only_b, 'neither': neither,
            'gain_pp': 100.0 * (only_b - only_a) / n if n else None, 'discordant': disc,
            'exact_mcnemar_p': float(p)}


def summarise(records):
    arms = sorted({r['arm'] for q in records for r in q['rows']})
    out = {}
    for arm in arms:
        rows = [r for q in records for r in q['rows'] if r['arm'] == arm]
        n = len(rows); whole = sum(r['score']['all_instances_hit'] for r in rows)
        ok = [r for r in rows if r['prediction']['status'] == 'ok']
        out[arm] = {'n': n, 'whole': whole, 'wilson95': wilson(whole, n), 'f1': float(np.mean([r['score']['f1'] for r in rows])),
                    'ok': len(ok), 'feasible_but_wrong': len([r for r in ok if not r['score']['all_instances_hit']]),
                    'whole_iou0_5': sum(bool(r.get('whole_iou0_5')) for r in rows),
                    'per_class': {c: [int(sum(r['score']['per_class'].get(c, {}).get('tp', 0) for r in rows)),
                                      int(sum(r['score']['per_class'].get(c, {}).get('n_truth', 0) for r in rows))]
                                  for c in ['bed', 'desk', 'cab', 'chair']}}
    return out, arms


def anatomy(records, arm):
    rows = [(q['scene'], r) for q in records for r in q['rows'] if r['arm'] == arm and not r['score']['all_instances_hit']]
    return [{'scene': s, 'status': r['prediction']['status'], 'f1': round(r['score']['f1'], 4),
             'per_class': {c: f"{v['tp']}/{v['n_truth']}" for c, v in r['score']['per_class'].items()},
             'boxes': sorted(r['prediction']['boxes'])} for s, r in rows]


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', required=True); ap.add_argument('--out', default=None)
    a = ap.parse_args(); records = load(a.dir)
    summary, arms = summarise(records)
    table = {f'{b}_vs_frozen011': paired(records, 'frozen011', b) for b in arms if b != 'frozen011'}
    report = {'experiment': str(a.dir), 'n_records': len(records), 'summary': summary, 'paired': table,
              'anatomy_frozen011': anatomy(records, 'frozen011'), 'anatomy_best': anatomy(records, arms[-1])}
    text = json.dumps(report, indent=1, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(text, encoding='utf-8')
    print(text[:6000])
