"""Turn the budget x quality grid into a table with intervals and paired tests."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest


def wilson(k, n, z=1.96):
    if n == 0:
        return [0., 1.]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [float((c - h) / d), float((c + h) / d)]


def table(cells):
    rows = []
    for key in sorted(cells, key=lambda k: (cells[k]['visits'], cells[k]['severity'])):
        c = cells[key]
        rows.append({'cell': key, 'visits': c['visits'], 'severity': c['severity'], 'n': c['n'],
                     'whole': c['whole'], 'ok': c['ok'], 'errors': c['errors'],
                     'f1': round(c['f1'], 4), 'wilson': [round(x, 4) for x in wilson(c['whole'], c['n'])],
                     'events_median': c['events_median'], 'coverage_median': c['coverage_median']})
    return rows


def paired(rows, a, b):
    """Exact McNemar on the discordant cells between two grid cells, keyed by room."""
    def hits(key):
        return {r['room']: bool(r['all_instances_hit']) for r in rows
                if f"v{r['visits']}-s{r['severity']}" == key and 'error' not in r}
    A, B = hits(a), hits(b)
    common = sorted(set(A) & set(B))
    if not common:
        return {'a': a, 'b': b, 'n': 0}
    only_a = sum(1 for r in common if A[r] and not B[r])
    only_b = sum(1 for r in common if B[r] and not A[r])
    k = min(only_a, only_b)
    n = only_a + only_b
    p = float(binomtest(k, n, 0.5).pvalue) if n else 1.0
    return {'a': a, 'b': b, 'n': len(common), 'a_only': only_a, 'b_only': only_b,
            'delta_pp': round(100 * (sum(A[r] for r in common) - sum(B[r] for r in common)) / len(common), 2),
            'p': round(p, 5)}


def main(path, out=None):
    payload = json.loads(Path(path).read_text())
    cells, rows = payload['cells'], payload['rows']
    visits = sorted({c['visits'] for c in cells.values()})
    severities = sorted({c['severity'] for c in cells.values()})
    grid = [[next(c for c in cells.values() if c['visits'] == v and c['severity'] == s)['whole'] for s in severities]
            for v in visits]
    tests = []
    for s in severities:
        tests.append(paired(rows, f'v{visits[-1]}-s{s}', f'v{visits[0]}-s{s}'))
    for v in visits:
        tests.append(paired(rows, f'v{v}-s{severities[0]}', f'v{v}-s{severities[-1]}'))
    report = {'grid_whole': grid, 'visits': visits, 'severities': severities, 'cells': table(cells),
              'paired_visits': tests[:len(severities)], 'paired_quality': tests[len(severities):],
              'n_per_cell': max(c['n'] for c in cells.values())}
    if out:
        Path(out).write_text(json.dumps(report, indent=1))
    print(json.dumps({k: report[k] for k in ('visits', 'severities', 'grid_whole', 'n_per_cell')}))
    for r in report['cells']:
        print(f"{r['cell']:>9} whole {r['whole']:>2}/{r['n']} wilson {r['wilson']} f1 {r['f1']:.4f} ok {r['ok']} err {r['errors']} ev {r['events_median']}")
    for t in tests:
        print(json.dumps(t))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--matrix', required=True)
    p.add_argument('--out')
    a = p.parse_args()
    main(a.matrix, a.out)
