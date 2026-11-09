"""Paired development experiment. 011 evidence is never overwritten."""
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
from .heading_consensus012 import decode as consensus
from .expansion_report import footprint_all

P = Path('output/research-sync/2026-11-09-raw-input-repair-011')
OLD = Path('output/research-sync/2026-11-09-joint-input-and-recovery-010')


def worker(task):
    i, role, out, experiment = task
    out = Path(out)
    case = (OLD / 'multi-raw-dev8-v3' if role == 'development8' else out / 'records' if role == 'fresh32' else P / 'confirm32') / f'multi-{i:05d}'
    target = out / (case.name + '.json')
    if target.exists():
        return json.loads(target.read_text())
    if role == 'fresh32' and not (case / 'input/known-priors.json').exists():
        from .sim_watch import generate as generate_watch, write as write_watch
        from .joint009 import mount
        from .synthetic_bridge import write_input
        from .displacement011 import generate, retime
        sc = M.load_native(OLD / 'raw-native800/native' / (case.name + '.json'))
        source = json.loads((OLD / 'raw-native800/native' / (case.name + '.json')).read_text())
        start = source['agent_placement']['position']
        sc['S'] = np.array([start['x'], start['z']])
        speed = .65 if i < 11216 else .55 if i < 11224 else .75
        script, _ = X.plan(sc)
        phone = generate(sc, seed=1710000 + i, script_override=retime(script, speed))
        meta = json.loads((OLD / 'wrist-ensemble-final/metadata.json').read_text())
        watch = mount(generate_watch(phone, 1710300 + i), meta['neutral_up_from_development'])
        session = case / 'input'
        write_input(session, phone)
        write_watch(session, watch)
        priors = {'room': [sc['W'], sc['L']], 'start': sc['S'].tolist(),
                  'inventory': [{**e, 'dimensions': np.asarray(e['dimensions']).tolist()} for e in sc['inventory']]}
        (session / 'known-priors.json').write_text(json.dumps(priors))
        np.savez_compressed(case / 'evaluation-truth.npz', time=phone['t'], position=phone['truth']['pos'], rotation=phone['truth']['R'], label=phone['truth']['label'])
    priors = json.loads((case / 'input/known-priors.json').read_text())
    model = load(P / 'spectral-training/trees-distance.joblib')
    records = []

    def front(t, A, G):
        return replay(t, A, G, model, heading_regularization=True)

    def paired(*args):
        records.append({'arm': 'frozen011', 'prediction': baseline(*args, support_cost_weight=.3)})
        if experiment == 'consensus':
            records.append({'arm': 'consensus012', 'prediction': consensus(*args, support_cost_weight=.3)})
        elif experiment == 'wall':
            from .wall_refine012 import refine as wall_refine
            priors, t, path, R, runs, mask, cap = args
            corrected, meta = wall_refine(t, path, R, runs, priors)
            prediction = baseline(priors, t, corrected, R, runs, mask, cap, support_cost_weight=.3)
            records.append({'arm': 'wall012', 'prediction': prediction, 'extra_prior_refinement': meta})
        return records[0]['prediction']

    X.infer(case / 'input', priors, OLD / 'wrist-ensemble-final', trajectory_frontend=front,
            candidate_limit=128, trajectory_refiner=refine, layout_decoder=paired)
    # Reference scene enters only after both predictions are final.
    scene = M.load_native(OLD / 'raw-native800/native' / (case.name + '.json'))
    for row in records:
        row['score'] = M.score_instances(row['prediction']['boxes'], scene['gt'])
        row['whole_iou0_5'] = footprint_all(row['prediction']['boxes'], scene['gt'])
    result = {'scene': case.name, 'role': role, 'input_sha256': {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (case / 'input').glob('*') if f.is_file()}, 'rows': records}
    target.write_text(json.dumps(result, indent=1))
    print(json.dumps({'scene': i, 'scores': [(r['arm'], r['prediction']['status'], r['score']['tp']) for r in records]}), flush=True)
    return result


def run(role, out, workers=3, experiment='consensus'):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ids = list(range(11000, 11008)) if role == 'development8' else list(range(11200, 11232)) if role == 'fresh32' else list(range(11100, 11132))
    freeze = {'ids': ids, 'role': role, 'experiment': experiment, 'source_sha256': hashlib.sha256(Path(__file__).with_name('heading_consensus012.py' if experiment == 'consensus' else 'wall_refine012.py').read_bytes()).hexdigest(),
              'hypothesis': 'Using only the first cabinet heading can amplify its error across the room; pool predicted structural-contact axes instead.' if experiment == 'consensus' else 'Declared storage-wall intervals may correct position drift before finite layout decoding.',
              'one_variable': 'room-frame offset' if experiment == 'consensus' else 'Extra declared cabinet-wall prior for trajectory repair, not a sensor-only improvement',
              'promotion': 'No automatic promotion; development improvement then fresh confirmation required.',
              'new_signal_generation': {'seed_base_phone': 1710000, 'seed_base_watch': 1710300, 'speeds': [ .65 if i < 11216 else .55 if i < 11224 else .75 for i in ids]} if role == 'fresh32' else None,
              'independence': 'New long signal realizations and unused012-selection IDs; same generator family/assets, not cross-domain generalization.',
              'extra_side_information': 'Only wall arm adds storage gap[0,0.15]m along depth normal and reach0.6m. Same priors file, stronger declared inference assumptions.',
              'motion_sha256': hashlib.sha256((P / 'spectral-training/trees-distance.joblib').read_bytes()).hexdigest()}
    protocol = out / 'protocol.json'
    if protocol.exists():
        previous = json.loads(protocol.read_text())
        # Preserve the earlier, smaller development manifest verbatim. Fresh
        # confirmation always requires the complete protocol to match.
        matches = previous == freeze if role == 'fresh32' else all(previous.get(k) == freeze[k] for k in ['ids', 'role', 'source_sha256'])
        if not matches:
            raise ValueError('Do not reuse results after changing frozen experiment')
    else:
        protocol.write_text(json.dumps(freeze, indent=1))
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        records = list(pool.map(worker, [(i, role, str(out), experiment) for i in ids]))
    summary = {a: {'whole': sum(r['score']['all_instances_hit'] for q in records for r in q['rows'] if r['arm'] == a),
                   'ok': sum(r['prediction']['status'] == 'ok' for q in records for r in q['rows'] if r['arm'] == a),
                   'f1': float(np.mean([r['score']['f1'] for q in records for r in q['rows'] if r['arm'] == a])),
                   'iou': sum(r['whole_iou0_5'] for q in records for r in q['rows'] if r['arm'] == a)} for a in ['frozen011', 'consensus012' if experiment == 'consensus' else 'wall012']}
    (out / 'summary.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--role', choices=['development8', 'diagnostic32', 'fresh32'], default='development8')
    parser.add_argument('--out', required=True)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--experiment', choices=['consensus', 'wall'], default='consensus')
    a = parser.parse_args()
    run(a.role, a.out, a.workers, a.experiment)
