"""Turn the budget x quality grid into a table with intervals and paired tests."""
import argparse
import json
import itertools
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


def outcomes(rows, key):
    """Keep exceptions as failures and reject duplicated room-condition rows."""
    selected = [r for r in rows if f"v{r['visits']}-s{r['severity']}" == key]
    hits = {r['room']: 'error' not in r and bool(r['all_instances_hit']) for r in selected}
    if len(hits) != len(selected):
        raise ValueError(f'Duplicate room-condition rows in {key}')
    return hits


def paired(rows, a, b):
    """Exact McNemar with exceptions scored as failures on the same planned rooms."""
    A, B = outcomes(rows, a), outcomes(rows, b)
    if set(A) != set(B):
        raise ValueError(f'Unmatched planned rooms for {a} and {b}')
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


def clustered_axis(rows, pairs, bootstrap_samples=50000, seed=17017):
    """Average contrasts within room, then resample or sign-flip entire rooms.

    The exact sign-flip test assumes room-level contrast symmetry under the null.
    It is a sensitivity analysis of these repeated conditions, not a randomised
    treatment test. Zero contrasts do not change its permutation distribution.
    """
    contrasts = []
    rooms = None
    for a, b in pairs:
        A, B = outcomes(rows, a), outcomes(rows, b)
        current = sorted(A)
        if set(A) != set(B) or (rooms is not None and current != rooms):
            raise ValueError('All axis contrasts must contain the same planned rooms')
        rooms = current
        contrasts.append([int(A[r]) - int(B[r]) for r in rooms])
    if not contrasts or not rooms:
        raise ValueError('At least one contrast and one room are required')
    differences = np.asarray(contrasts, float).T
    room_means = differences.mean(axis=1)
    nonzero = room_means[np.abs(room_means) > 1e-12]
    if len(nonzero) > 20:
        raise ValueError('Exact sign-flip enumeration supports at most 20 nonzero rooms')
    observed = abs(nonzero.sum())
    extreme = sum(abs(np.dot(signs, nonzero)) >= observed - 1e-12
                  for signs in itertools.product((-1., 1.), repeat=len(nonzero)))
    p = extreme / (2 ** len(nonzero))
    rng = np.random.default_rng(seed)
    samples = rng.choice(room_means, size=(bootstrap_samples, len(rooms))).mean(axis=1)
    return {'n_rooms': len(rooms), 'n_contrasts_per_room': len(pairs),
            'pairs': pairs, 'rooms': rooms, 'within_room_differences': differences.tolist(),
            'delta_pp': float(100 * room_means.mean()), 'p_sign_flip': float(p),
            'bootstrap95_pp': (100 * np.quantile(samples, [.025, .975])).tolist(),
            'bootstrap_samples': bootstrap_samples, 'seed': seed,
            'unit': 'room', 'test': 'exact room-cluster sign flip, two sided',
            'test_assumption': 'independent rooms and symmetric room-level contrasts under the null',
            'exception_policy': 'failure', 'missing_pair_policy': 'raise'}


def main(path, out=None):
    payload = json.loads(Path(path).read_text())
    from .matrix016 import summarise
    rows = payload['rows']
    cells = summarise(rows)
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
              'n_per_cell': max(c['n'] for c in cells.values()),
              'clustered_quality': clustered_axis(rows, [(f'v{v}-s{severities[0]}', f'v{v}-s{severities[-1]}') for v in visits]),
              'clustered_visits': clustered_axis(rows, [(f'v{visits[-1]}-s{s}', f'v{visits[0]}-s{s}') for s in severities])}
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
