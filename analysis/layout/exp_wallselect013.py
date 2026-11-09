"""Arm wall013s: wall012 trajectory repair + conditional wall prior (013)."""
import argparse
import concurrent.futures
import json
from pathlib import Path
import numpy as np
from . import multi_raw010 as X, multi_instance as M
from .displacement011 import replay, load
from .contact_loops011 import refine
from .oriented_raw011 import decode as baseline
from .wall_refine012 import refine as wall_refine
from .wall_priors013 import decode as wall_decode
from .wall_select013 import decode_select
from .expansion_report import footprint_all
from .exp_wall013 import case_for

P = Path('output/research-sync/2026-11-09-raw-input-repair-011')
OLD = Path('output/research-sync/2026-11-09-joint-input-and-recovery-010')
ARMS = ['frozen011', 'wall012', 'wall013', 'wall013s']


def worker(task):
    i, role, out = task
    out = Path(out); case = case_for(role, out, i)
    target = out / (case.name + '.json')
    if target.exists():
        return json.loads(target.read_text())
    probe = case / 'input/known-priors.json'
    if not probe.exists():
        from .sim_watch import generate as generate_watch, write as write_watch
        from .joint009 import mount
        from .synthetic_bridge import write_input
        from .displacement011 import generate, retime
        native = OLD / 'raw-native800/native' / (case.name + '.json')
        sc = M.load_native(native); source = json.loads(native.read_text())
        start = source['agent_placement']['position']; sc['S'] = np.array([start['x'], start['z']])
        speed = .65 if (i % 3) == 0 else .55 if (i % 3) == 1 else .75
        script, _ = X.plan(sc)
        phone = generate(sc, seed=1730000 + i, script_override=retime(script, speed))
        meta = json.loads((OLD / 'wrist-ensemble-final/metadata.json').read_text())
        watch = mount(generate_watch(phone, 1730300 + i), meta['neutral_up_from_development'])
        session = case / 'input'; session.mkdir(parents=True, exist_ok=True)
        write_input(session, phone); write_watch(session, watch)
        priors = {'room': [sc['W'], sc['L']], 'start': sc['S'].tolist(),
                  'inventory': [{**e, 'dimensions': np.asarray(e['dimensions']).tolist()} for e in sc['inventory']]}
        (session / 'known-priors.json').write_text(json.dumps(priors))
        np.savez_compressed(case / 'evaluation-truth.npz', time=phone['t'], position=phone['truth']['pos'],
                            rotation=phone['truth']['R'], label=phone['truth']['label'])
    priors = json.loads(probe.read_text())
    model = load(P / 'spectral-training/trees-distance.joblib')
    records = []

    def front(t, A, G):
        return replay(t, A, G, model, heading_regularization=True)

    def paired(*args):
        priors_, t, path, R, runs, mask, cap = args
        records.append({'arm': 'frozen011', 'prediction': baseline(*args, support_cost_weight=.3)})
        fixed, meta = wall_refine(t, path, R, runs, priors_)
        records.append({'arm': 'wall012', 'prediction': baseline(priors_, t, fixed, R, runs, mask, cap, support_cost_weight=.3),
                        'extra_prior_refinement': meta})
        records.append({'arm': 'wall013', 'prediction': wall_decode(priors_, t, fixed, R, runs, mask, cap, support_cost_weight=.3, wall=True)})
        records.append({'arm': 'wall013s', 'prediction': decode_select(priors_, t, fixed, R, runs, mask, cap, support_cost_weight=.3)})
        return records[0]['prediction']

    X.infer(case / 'input', priors, OLD / 'wrist-ensemble-final', trajectory_frontend=front,
            candidate_limit=128, trajectory_refiner=refine, layout_decoder=paired)
    scene = M.load_native(OLD / 'raw-native800/native' / (case.name + '.json'))
    for row in records:
        row['score'] = M.score_instances(row['prediction']['boxes'], scene['gt'])
        row['whole_iou0_5'] = footprint_all(row['prediction']['boxes'], scene['gt'])
    result = {'scene': case.name, 'role': role, 'rows': records}
    target.write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(json.dumps({'scene': i, 'arms': [(r['arm'], r['prediction']['status'], r['score']['tp']) for r in records]}), flush=True)
    return result


def summarise(records):
    out = {}
    for arm in ARMS:
        rows = [r for q in records for r in q['rows'] if r['arm'] == arm]
        n = len(rows); whole = sum(r['score']['all_instances_hit'] for r in rows)
        out[arm] = {'n': n, 'whole': whole, 'rate': whole / n,
                    'f1': float(np.mean([r['score']['f1'] for r in rows])),
                    'ok': sum(r['prediction']['status'] == 'ok' for r in rows),
                    'iou': sum(r['whole_iou0_5'] for r in rows),
                    'per_class': {c: [sum(r['score']['per_class'].get(c, {}).get('tp', 0) for r in rows),
                                      sum(r['score']['per_class'].get(c, {}).get('n_truth', 0) for r in rows)]
                                  for c in ['bed', 'desk', 'cab', 'chair']}}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--role', default='development8')
    ap.add_argument('--ids', default='11000-11007')
    ap.add_argument('--out', required=True)
    ap.add_argument('--jobs', type=int, default=2)
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.ids.split('-'))
    ids = list(range(lo, hi + 1))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    records = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        for res in pool.map(worker, [(i, a.role, a.out) for i in ids]):
            records.append(res)
    summary = summarise(records)
    (Path(a.out) / 'summary.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
