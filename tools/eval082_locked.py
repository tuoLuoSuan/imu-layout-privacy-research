"""Hash-bound C/D evaluation; preserves the archived082 scoring logic with failures in the denominator.

Inference receives observation JSONs only; targets are opened by this evaluator.
Confirmation requires groups/fingerprints disjoint from all development rows.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import numpy as np
import torch
from analysis.layout.recovery076_data import read, dump, sha, validate_manifest, check_confirmation
from analysis.layout.recovery076_eval import score, failed_score, aggregate
from analysis.layout.recovery081_runtime import load_models, predict, refine_boxes
from analysis.layout.analytic077 import corrected_static


def paired(rows, candidate, baseline, draws):
    a = {r['id']: r for r in rows if r['arm'] == candidate}
    b = {r['id']: r for r in rows if r['arm'] == baseline}
    if set(a) != set(b):
        raise ValueError('Pairing requires identical requested IDs')
    grouped = defaultdict(lambda: np.zeros(4))
    repaired = broken = 0
    for rid, r in a.items():
        old = b[rid]
        grouped[r['group']] += [r['whole_room']-old['whole_room'],
                                r['whole_footprint']-old['whole_footprint'], r['f1']-old['f1'], 1]
        repaired += int(r['whole_room'] and not old['whole_room'])
        broken += int(old['whole_room'] and not r['whole_room'])
    d = np.stack([grouped[g] for g in sorted(grouped)])
    rng = np.random.default_rng(8101)
    boot = d[rng.integers(len(d), size=(draws, len(d)))].sum(1)
    boot = boot[:, :3]/boot[:, 3:]
    total = d.sum(0)
    return {'candidate': candidate, 'baseline': baseline, 'n_requested_pairs': len(a),
            'independent_condition_groups': len(d), 'centre_repaired': repaired, 'centre_broken': broken,
            'delta_centre_footprint_f1': (total[:3]/total[3]).tolist(),
            'group_bootstrap_ci95': np.quantile(boot, [.025, .975], axis=0).T.tolist()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True); p.add_argument('--out', required=True)
    p.add_argument('--split', choices=('validation', 'test', 'confirmation'), default='validation')
    p.add_argument('--development-manifest', action='append')
    p.add_argument('--k2', required=True); p.add_argument('--k6')
    p.add_argument('--teacher', required=True); p.add_argument('--refiner', required=True)
    p.add_argument('--refiner-k2', default=None, help='optional k=2-specific refiner checkpoint')
    p.add_argument('--refiner-k2-sha256', help='Required expected SHA-256 when a legacy K2 refiner is supplied')
    p.add_argument('--primary', choices=('refine_B', 'refine_k6_C'), default='refine_B')
    p.add_argument('--threads', type=int, default=4); p.add_argument('--draws', type=int, default=4000)
    p.add_argument('--smoke-limit', type=int, help='Validation-only infrastructure smoke; never a full result')
    a = p.parse_args()
    if a.primary == 'refine_k6_C' and not a.k6:
        p.error('Primary C requires the locked K6 checkpoint')
    if a.draws < 100:
        p.error('At least 100 group-bootstrap draws required')
    if a.smoke_limit is not None and (a.split != 'validation' or a.smoke_limit < 1):
        p.error('Smoke subsets are allowed only on development validation')
    torch.set_num_threads(a.threads)
    models = load_models(a.k2, a.teacher, a.refiner, a.k6)
    if getattr(a, 'refiner_k2', None):
        from analysis.layout.recovery080_refine import Refine080
        if not a.refiner_k2_sha256 or sha(a.refiner_k2) != a.refiner_k2_sha256:
            raise ValueError('K2 refiner must match the explicit frozen SHA-256')
        _ck = torch.load(a.refiner_k2, map_location='cpu', weights_only=True)
        _m = Refine080(width=_ck['width'], dim=_ck['dim']); _m.load_state_dict(_ck['state_dict']); _m.eval()
        models['refiner_k2'] = _m
        models['lock']['checkpoint_sha256']['refiner_k2'] = a.refiner_k2_sha256
    base_models = {**models, 'k6': None}
    mp = Path(a.manifest); manifest = validate_manifest(read(mp))
    development = a.development_manifest or ['output/layout-recon/recovery076/main400/manifest.json']
    if a.split == 'confirmation':
        seen_groups = set(models['teacher_saved']['seen_groups'])
        seen_prints = set(models['teacher_saved']['seen_fingerprints'])
        for path in development:
            old = validate_manifest(read(path))
            seen_groups.update(r['group'] for r in old['rows'])
            seen_prints.update(r['fingerprint'] for r in old['rows'])
        check_confirmation(manifest, seen_groups, seen_prints)
    elif sha(mp) != models['teacher_saved']['manifest_sha256']:
        raise ValueError('A new manifest must be explicitly labelled independent confirmation')
    metas = [r for r in manifest['rows'] if r['split'] == a.split]
    if a.smoke_limit is not None:
        metas = metas[:a.smoke_limit]
    if not metas:
        raise ValueError('Empty explicit evaluation split')
    arms = ['coarse_A', 'refine_B'] + (['refine_k6_C'] if a.k6 else []) + ['corrected_static']
    paths = {'manifest': mp, 'k2': Path(a.k2), 'teacher': Path(a.teacher), 'refiner': Path(a.refiner),
             'evaluator': Path(__file__)}
    if a.k6:
        paths['k6'] = Path(a.k6)
    if a.refiner_k2:
        paths['refiner_k2'] = Path(a.refiner_k2)
    for name in (*models['lock']['source_sha256'], 'analytic077.py', 'multi_instance.py',
                 'continuous_regions.py', 'recovery076_eval.py', 'sim_eval.py'):
        paths['source/'+name] = ROOT/'analysis/layout'/name
    for i, path in enumerate(development):
        paths['development_manifest/'+str(i)] = Path(path)
    hashes = {k: sha(v) for k, v in paths.items()}
    out = Path(a.out); out.mkdir(parents=True, exist_ok=False)
    protocol = {'variant': 'D_with_k2_refiner' if a.refiner_k2 else 'C', 'args': vars(a), 'primary_predeclared': a.primary, 'requested_ids': [r['id'] for r in metas],
                'is_smoke_only': a.smoke_limit is not None,
                'frozen_file_sha256': hashes, 'model_lock': models['lock'],
                'failure_policy': 'all requested cells retained, acquisition and decoder failures score zero',
                'inference_policy': 'actual event counts only; zero-contact bypass; no real-room rules',
                'statistical_unit': 'condition group; all layouts/coverage/budget cells remain grouped',
                'scope': 'conditional geometry with declared desk_relation; not raw IMU end to end',
                'fresh_confirmation_claim': a.split == 'confirmation'}
    # Written BEFORE any predictions/scores. A new directory is never overwritten.
    dump(out/'protocol.json', protocol)
    rows = []; started = time.monotonic()
    with (out/'rows.jsonl').open('w', encoding='utf-8') as file:
        for index, meta in enumerate(metas):
            outputs = {}
            if meta['status'] == 'ok':
                ip = mp.parent/meta['input']; tp = mp.parent/meta['target']
                if sha(ip) != meta['input_sha256'] or sha(tp) != meta['target_sha256']:
                    raise ValueError('Frozen input/target hash mismatch: '+meta['id'])
                obs = read(ip); truth = read(tp)['boxes']
                try:
                    pred = predict(obs, base_models, 'none')
                    outputs['coarse_A'] = (pred['boxes'], 'ok', None)
                except Exception as exc:
                    outputs['coarse_A'] = ({}, 'decoder_failed', repr(exc))
                try:
                    if outputs['coarse_A'][1] != 'ok':
                        outputs['refine_B'] = outputs['coarse_A']
                    else:
                        _ref = models['refiner_k2'] if (models.get('refiner_k2') is not None and len(obs['events']) == 2) else models['refiner']
                        b, _ = refine_boxes(obs, outputs['coarse_A'][0], _ref, 'nonzero')
                        outputs['refine_B'] = (b, 'ok', None)
                except Exception as exc:
                    outputs['refine_B'] = ({}, 'decoder_failed', repr(exc))
                if a.k6:
                    try:
                        outputs['refine_k6_C'] = ((predict(obs, models)['boxes'], 'ok', None)
                                                 if len(obs['events']) == 6 else outputs['refine_B'])
                    except Exception as exc:
                        outputs['refine_k6_C'] = ({}, 'decoder_failed', repr(exc))
                try:
                    static = corrected_static(obs)
                    outputs['corrected_static'] = (static.get('boxes', {}), static['status'], None)
                except Exception as exc:
                    outputs['corrected_static'] = ({}, 'decoder_failed', repr(exc))
            for arm in arms:
                if meta['status'] != 'ok':
                    boxes, status, error = {}, 'acquisition_failed', meta.get('error')
                    value = failed_score()
                else:
                    boxes, status, error = outputs[arm]
                    value = score(boxes, truth)
                row = {k: meta[k] for k in ('id', 'group', 'coverage_target', 'contacts_requested')}
                row.update(arm=arm, usable=meta['status'] == 'ok', status=status,
                           error=error, boxes=boxes, **value)
                rows.append(row); file.write(json.dumps(row)+'\n')
            file.flush()
            if (index+1) % 100 == 0:
                print(json.dumps({'done': index+1, 'total': len(metas), 'seconds': time.monotonic()-started}), flush=True)
    if hashes != {k: sha(v) for k, v in paths.items()}:
        raise ValueError('Frozen model/source/manifest changed during evaluation')
    table = {arm: aggregate([r for r in rows if r['arm'] == arm]) for arm in arms}
    cell_table = [{'arm': arm, 'coverage_target': cov, 'contacts_requested': k,
                   **aggregate([r for r in rows if r['arm'] == arm and r['coverage_target'] == cov and r['contacts_requested'] == k])}
                  for arm in arms for cov in sorted({r['coverage_target'] for r in rows})
                  for k in sorted({r['contacts_requested'] for r in rows})]
    contrasts = [paired(rows, arm, baseline, a.draws) for arm in arms if arm != 'corrected_static'
                 for baseline in ('corrected_static', 'coarse_A') if baseline != arm]
    dump(out/'summary.json', {'protocol': protocol, 'table': table, 'surface': cell_table,
                             'paired': contrasts, 'elapsed_seconds': time.monotonic()-started})
    print(json.dumps(table), flush=True)


if __name__ == '__main__':
    main()
