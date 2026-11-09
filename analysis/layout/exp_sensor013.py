"""Severity sweep on the sensor side of the frozen chain (experimental 013).

One fixed decoder (the 013 wall-prior arm) and one fixed geometry; only the
handset error model moves. Each severity reuses the same base signal
realization, so the comparison is paired by room.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import numpy as np
from . import multi_raw010 as X, multi_instance as M
from .displacement011 import generate, load, replay, retime
from .sim_watch import generate as generate_watch, write as write_watch
from .joint009 import mount
from .synthetic_bridge import write_input
from .contact_loops011 import refine
from .wall_refine012 import refine as wall_refine
from .wall_priors013 import decode as wall_decode
from .oriented_raw011 import decode as baseline
from .sensor013 import degrade, report
from .expansion_report import footprint_all

P = Path('output/research-sync/2026-11-09-raw-input-repair-011')
OLD = Path('output/research-sync/2026-11-09-joint-input-and-recovery-010')


def worker(task):
    i, severity, out, decoder_name = task
    out = Path(out); case = out / 'records' / f'multi-{i:05d}-s{severity:g}'
    target = out / (case.name + '.json')
    if target.exists():
        return json.loads(target.read_text())
    native = OLD / 'raw-native800/native' / f'multi-{i:05d}.json'
    sc = M.load_native(native); source = json.loads(native.read_text())
    start = source['agent_placement']['position']; sc['S'] = np.array([start['x'], start['z']])
    script, _ = X.plan(sc)
    clean = generate(sc, seed=1750000 + i, script_override=retime(script, .65))
    phone = degrade(clean, severity, seed=7 + i)
    session = case / 'input'; session.mkdir(parents=True, exist_ok=True)
    write_input(session, phone)
    meta = json.loads((OLD / 'wrist-ensemble-final/metadata.json').read_text())
    write_watch(session, mount(generate_watch(phone, 1750300 + i), meta['neutral_up_from_development']))
    priors = {'room': [sc['W'], sc['L']], 'start': sc['S'].tolist(),
              'inventory': [{**e, 'dimensions': np.asarray(e['dimensions']).tolist()} for e in sc['inventory']]}
    (session / 'known-priors.json').write_text(json.dumps(priors))
    model = load(P / 'spectral-training/trees-distance.joblib')

    def front(t, A, G):
        return replay(t, A, G, model, heading_regularization=True)

    plain_refine = refine

    def refine_fn(t, path, R, runs, known):
        if decoder_name == 'plain':
            return plain_refine(t, path, R, runs, known)
        return wall_refine(t, path, R, runs, known)

    captured = []

    def decoder(priors_, t, path, R, runs, mask, cap):
        if decoder_name == 'plain':
            value = baseline(priors_, t, path, R, runs, mask, cap, support_cost_weight=.3)
        else:
            value = wall_decode(priors_, t, path, R, runs, mask, cap, support_cost_weight=.3, wall=True)
        captured.append(value)
        return value

    failure = None
    try:
        X.infer(session, priors, OLD / 'wrist-ensemble-final', trajectory_frontend=front,
                candidate_limit=128, trajectory_refiner=refine_fn, layout_decoder=decoder)
    except ValueError as exc:
        failure = f'{type(exc).__name__}: {exc}'
    result = captured[-1] if (failure is None and captured) else {'status': 'frontend_error', 'boxes': {}}
    score = M.score_instances(result['boxes'], sc['gt'])
    record = {'scene': f'multi-{i:05d}', 'severity': severity, 'decoder': decoder_name, 'status': result['status'],
              'sensor_error': report(clean, phone), 'score': score, 'failure': failure,
              'whole_iou0_5': footprint_all(result['boxes'], sc['gt']),
              'input_sha256': {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in session.glob('*') if f.is_file()}}
    target.write_text(json.dumps(record, indent=1), encoding='utf-8')
    print(json.dumps({'scene': i, 'severity': severity, 'status': result['status'], 'tp': score['tp'], 'whole': score['all_instances_hit']}), flush=True)
    return record


def run(out, count, severities, workers=3, decoder_name='wall'):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    ids = list(range(11400, 11400 + count))
    freeze = {'ids': ids, 'severities': severities, 'decoder': decoder_name,
              'hypothesis': 'The frozen chain degrades with sensor error before the activity budget becomes the limit.',
              'one_variable': 'handset error severity (bias random walk, white noise, scale factor, misalignment, timestamp jitter)',
              'source_sha256': {f: hashlib.sha256(Path(__file__).with_name(f).read_bytes()).hexdigest() for f in ['sensor013.py', 'wall_priors013.py']}}
    protocol = out / 'protocol.json'
    if protocol.exists():
        if json.loads(protocol.read_text()) != freeze:
            raise ValueError('Do not reuse results after changing the frozen experiment')
    else:
        protocol.write_text(json.dumps(freeze, indent=1), encoding='utf-8')
    tasks = [(i, s, str(out), decoder_name) for i in ids for s in severities]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        records = list(pool.map(worker, tasks))
    summary = {}
    for s in severities:
        rows = [r for r in records if r['severity'] == s]
        summary[str(s)] = {'n': len(rows), 'whole': sum(r['score']['all_instances_hit'] for r in rows),
                           'f1': float(np.mean([r['score']['f1'] for r in rows])),
                           'ok': sum(r['status'] == 'ok' for r in rows),
                           'acc_rms_error': float(np.mean([r['sensor_error']['acc_rms_error'] for r in rows])),
                           'per_class': {c: [sum(r['score']['per_class'][c]['tp'] for r in rows), sum(r['score']['per_class'][c]['n_truth'] for r in rows)]
                                         for c in ['bed', 'desk', 'cab', 'chair']}}
    (out / 'summary.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--count', type=int, default=12)
    ap.add_argument('--severities', default='1,2,4')
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--decoder', choices=['wall', 'plain'], default='wall')
    a = ap.parse_args(); run(a.out, a.count, [float(x) for x in a.severities.split(',')], a.workers, a.decoder)
