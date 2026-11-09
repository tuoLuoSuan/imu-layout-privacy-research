"""Independent evaluation and one-case input firewall for experimental012."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
from scipy.stats import binomtest
from .audit_input011 import independent_score, bootstrap, wilson
from . import multi_instance as M


def audit(root, native, model, wrist):
    root, native, model, wrist = map(Path, (root, native, model, wrist))
    protocol = json.loads((root / 'protocol.json').read_text())
    assert protocol['source_sha256'] == hashlib.sha256(Path(__file__).with_name('wall_refine012.py').read_bytes()).hexdigest()
    assert protocol['motion_sha256'] == hashlib.sha256(model.read_bytes()).hexdigest()
    rows, input_hashes, durations = [], {}, []
    first_seven = None
    for i in protocol['ids']:
        folder = root / 'records' / f'multi-{i:05d}'
        saved = json.loads((root / f'multi-{i:05d}.json').read_text())
        truth = M.load_native(native / f'multi-{i:05d}.json')['gt']
        if first_seven is None and len(truth) == 7:
            first_seven = i
        input_hashes[str(i)] = {f.relative_to(folder / 'input').as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in (folder / 'input').rglob('*') if f.is_file()}
        durations.append(float(np.load(folder / 'evaluation-truth.npz')['time'][-1]))
        for r in saved['rows']:
            score = independent_score(r['prediction']['boxes'], truth)
            assert score['tp'] == r['score']['tp'] and score['whole'] == r['score']['all_instances_hit']
            assert abs(score['f1'] - r['score']['f1']) < 1e-12
            assert score['whole_iou0_5'] == r['whole_iou0_5']
            rows.append({'scene': saved['scene'], 'arm': r['arm'], 'status': r['prediction']['status'], **score})
    summary = {}
    for arm in ['frozen011', 'wall012']:
        group = [r for r in rows if r['arm'] == arm]; k = sum(r['whole'] for r in group)
        summary[arm] = {'n': len(group), 'whole': k, 'wilson95': wilson(k, len(group)),
                        'f1': float(np.mean([r['f1'] for r in group])),
                        'f1_bootstrap95': bootstrap([r['f1'] for r in group]),
                        'ok': sum(r['status'] == 'ok' for r in group),
                        'whole_iou0_5': sum(r['whole_iou0_5'] for r in group),
                        'per_class': {c: {'tp': sum(r['per_class'][c]['tp'] for r in group), 'n_truth': sum(r['per_class'][c]['n_truth'] for r in group)} for c in ['bed','desk','cab','chair']}}
    old, new = [[r for r in rows if r['arm'] == a] for a in ['frozen011', 'wall012']]
    delta = np.array([b['whole'] - a['whole'] for a, b in zip(old, new)], int)
    plus, minus = int(sum(delta > 0)), int(sum(delta < 0))
    fd = np.array([b['f1'] - a['f1'] for a, b in zip(old, new)])
    paired = {'both_hit': sum(a['whole'] and b['whole'] for a,b in zip(old,new)), 'new_only': plus, 'old_only': minus,
              'both_miss': sum(not a['whole'] and not b['whole'] for a,b in zip(old,new)),
              'gain_pp': float(100*delta.mean()), 'paired_bootstrap95_pp': [100*x for x in bootstrap(delta)],
              'exact_mcnemar_p': float(binomtest(plus, plus+minus, .5).pvalue) if plus+minus else 1.,
              'f1_gain': float(fd.mean()), 'f1_gain_paired_bootstrap95': bootstrap(fd)}
    out = {'n': len(protocol['ids']), 'independent_scores': len(rows), 'summary': summary, 'paired': paired,
           'duration_s_range': [min(durations), max(durations)], 'input_sha256': input_hashes,
           'source': 'New012 long raw signals, same generator family; stronger declared storage-wall side information. No raw-input activity threshold established.'}
    (root / 'audit.json').write_text(json.dumps(out, indent=1))
    # Choose the first seven-object input by inventory, independently of score.
    source = root / 'records' / f'multi-{first_seven:05d}' / 'input'
    isolated = root / 'input-firewall'; isolated.mkdir(exist_ok=True)
    for name in ['phone/accelerometer.csv','phone/gyroscope.csv','watch/accelerometer.csv','known-priors.json']:
        dest = isolated / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source/name, dest)
    for name in ['evaluation-truth.npz','native-scene.json','cue-script.json']:
        (isolated/name).write_text('FORBIDDEN_EVALUATION_CANARY')
    argv = ['analysis.layout.joint_input012', '--session', str(isolated), '--priors', str(isolated/'known-priors.json'),
            '--model', str(model), '--wrist', str(wrist), '--out', str(isolated/'prediction.json')]
    script = """import sys,runpy,json
def guard(event,args):
 if event=='open':
  p=str(args[0]).replace(chr(92),'/')
  if any(w in p for w in ('evaluation-truth','native-scene','cue-script','raw-native800')): raise RuntimeError('Forbidden reference read: '+p)
sys.addaudithook(guard)
sys.argv=json.loads(sys.argv[1]); runpy.run_module(sys.argv[0],run_name='__main__')
"""
    subprocess.run([sys.executable, '-X', 'utf8', '-c', script, json.dumps(argv)], check=True, env={**os.environ,'OMP_NUM_THREADS':'1'})
    actual = json.loads((isolated/'prediction.json').read_text())
    expected = next(r['prediction'] for r in json.loads((root/f'multi-{first_seven:05d}.json').read_text())['rows'] if r['arm']=='wall012')
    assert actual['boxes'].keys() == expected['boxes'].keys()
    maximum = max(float(np.max(abs(np.asarray(b)-expected['boxes'][k]))) for k,b in actual['boxes'].items())
    assert maximum <= 1e-9 and actual['status'] == expected['status']
    verify = {'scene': first_seven, 'selection': 'First seven-object inventory, independent of outcome', 'status_matches': True,
              'max_box_delta_m': maximum, 'reference_reads_blocked_in_fresh_process': True, 'raw_phone_axes':6,
              'raw_watch_axes':3, 'cabinet_source':'watch_only', 'scope':'One representative input; not formal noninterference proof.'}
    (root/'input-firewall.json').write_text(json.dumps(verify, indent=1))
    print(json.dumps({'summary':summary, 'paired':paired, 'input_firewall':verify, 'duration':out['duration_s_range']},indent=1))


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    for key in ['root','native','model','wrist']: p.add_argument('--'+key,required=True)
    a=p.parse_args(); audit(a.root,a.native,a.model,a.wrist)
