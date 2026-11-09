"""Paired 013 experiment: class-wise measured wall pools on the device chain.

Arms differ in one variable each: frozen011 (reference), wall012 (storage-wall
trajectory repair only), wall013p (candidate-pool wall prior only), wall013
(both). Selection stays on the development recordings; the confirmation ids
are generated fresh and never used to pick a threshold.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import numpy as np
from . import multi_raw010 as X, multi_instance as M
from .displacement011 import replay, load
from .contact_loops011 import refine
from .oriented_raw011 import decode as baseline
from .wall_refine012 import refine as wall_refine
from .wall_priors013 import decode as wall_decode
from .expansion_report import footprint_all

P = Path('output/research-sync/2026-11-09-raw-input-repair-011')
OLD = Path('output/research-sync/2026-11-09-joint-input-and-recovery-010')
ARMS = ['frozen011', 'wall012', 'wall013p', 'wall013']


def case_for(role, out, i):
    out = Path(out)
    if role == 'development8':
        return OLD / 'multi-raw-dev8-v3' / f'multi-{i:05d}'
    if role == 'fresh32':
        return Path('output/research-sync/2026-11-09-paper-and-raw-input-012/wall-fresh32/records') / f'multi-{i:05d}'
    return out / 'records' / f'multi-{i:05d}'


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
        records.append({'arm': 'wall013p', 'prediction': wall_decode(priors_, t, path, R, runs, mask, cap, support_cost_weight=.3, wall=True)})
        records.append({'arm': 'wall013', 'prediction': wall_decode(priors_, t, fixed, R, runs, mask, cap, support_cost_weight=.3, wall=True),
                        'extra_prior_refinement': {'storage_wall': meta, 'pool_wall': 'bed<=0.12 desk<=0.16 cab<=0.16 chair>=0.45 measured on 1000 native rooms'}})
        return records[0]['prediction']

    X.infer(case / 'input', priors, OLD / 'wrist-ensemble-final', trajectory_frontend=front,
            candidate_limit=128, trajectory_refiner=refine, layout_decoder=paired)
    scene = M.load_native(OLD / 'raw-native800/native' / (case.name + '.json'))
    for row in records:
        row['score'] = M.score_instances(row['prediction']['boxes'], scene['gt'])
        row['whole_iou0_5'] = footprint_all(row['prediction']['boxes'], scene['gt'])
    result = {'scene': case.name, 'role': role,
              'input_sha256': {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (case / 'input').glob('*') if f.is_file()},
              'rows': records}
    target.write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(json.dumps({'scene': i, 'scores': [(r['arm'], r['prediction']['status'], r['score']['tp']) for r in records]}), flush=True)
    return result


def summarise(records):
    out = {}
    for arm in ARMS:
        rows = [r for q in records for r in q['rows'] if r['arm'] == arm]
        n = len(rows); whole = sum(r['score']['all_instances_hit'] for r in rows)
        out[arm] = {'n': n, 'whole': whole, 'rate': whole / n, 'f1': float(np.mean([r['score']['f1'] for r in rows])),
                    'ok': sum(r['prediction']['status'] == 'ok' for r in rows),
                    'iou': sum(r['whole_iou0_5'] for r in rows),
                    'per_class': {c: [sum(r['score']['per_class'][c]['tp'] for r in rows), sum(r['score']['per_class'][c]['n_truth'] for r in rows)]
                                  for c in ['bed', 'desk', 'cab', 'chair']}}
    return out


def run(role, out, count, workers=3):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    base = 11000 if role == 'development8' else 11200 if role == 'fresh32' else 11300
    ids = list(range(base, base + count))
    freeze = {'ids': ids, 'role': role, 'arms': ARMS,
              'source_sha256': {f: hashlib.sha256(Path(__file__).with_name(f).read_bytes()).hexdigest()
                                for f in ['wall_priors013.py', 'wall_refine012.py', 'oriented_raw011.py']},
              'hypothesis': 'Bed/desk/cabinet wall adjacency measured on the generator family prunes wrong instances before the joint search.',
              'one_variable': 'class-wise measured wall-gap pool filter (plus the existing storage-wall trajectory repair as a separate arm)',
              'extra_side_information': 'gap<=0.12m bed, <=0.16m desk, <=0.16m cab, >=0.45m chair; measured, not truth',
              'promotion': 'No automatic promotion; development8 then a fresh generated confirmation batch.',
              'motion_sha256': hashlib.sha256((P / 'spectral-training/trees-distance.joblib').read_bytes()).hexdigest()}
    protocol = out / 'protocol.json'
    if protocol.exists():
        if json.loads(protocol.read_text()) != freeze:
            raise ValueError('Do not reuse results after changing the frozen experiment')
    else:
        protocol.write_text(json.dumps(freeze, indent=1), encoding='utf-8')
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        records = list(pool.map(worker, [(i, role, str(out)) for i in ids]))
    summary = summarise(records)
    (out / 'summary.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--role', required=True, choices=['development8', 'fresh32', 'confirm32'])
    ap.add_argument('--out', required=True)
    ap.add_argument('--count', type=int, default=8)
    ap.add_argument('--workers', type=int, default=3)
    a = ap.parse_args(); run(a.role, a.out, a.count, a.workers)
