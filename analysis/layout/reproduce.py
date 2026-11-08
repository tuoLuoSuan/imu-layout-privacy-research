"""Run the reviewed experiments with explicit data paths and one frozen model."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

from . import paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--session', type=Path, default=Path(paths.SESSION))
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--skip-noise', action='store_true')
    args = parser.parse_args()
    root = Path(paths.REPO)
    session = args.session.resolve()
    for required in (Path(paths.THOR), Path(paths.RONIN_ARCH), Path(paths.RONIN_CKPT)):
        if not required.exists():
            parser.error('Missing external input: ' + str(required))
    environment = dict(os.environ, IMU_LAYOUT_SESSION=str(session), PYTHONIOENCODING='utf-8')
    commands = []
    if args.bundle:
        commands.append(['analyze.py', str(args.bundle.resolve()), str(session)])
    commands.extend([
        ['pred_vs_actual.py'], ['exp_robust.py'], ['exp_modes.py'],
        ['exp_evidence.py', str(session)], ['exp_partial.py'], ['exp_ideal.py'],
        ['exp_prefix.py'], ['exp_average.py', str(session)], ['attribution.py', str(session)],
        ['identifiability.py', str(session)], ['exp_consistency.py'],
    ])
    if not args.skip_noise:
        commands.extend([['exp_noise_flip.py'], ['exp_drift.py']])
    for command in commands:
        print('Running', command[0], flush=True)
        subprocess.run([sys.executable, '-X', 'utf8', str(root / 'analysis/layout' / command[0]), *command[1:]],
                       cwd=root, env=environment, check=True)
    inventory = {}
    for pattern in ('*.py', '*.json'):
        for path in (root / 'analysis/layout').glob(pattern):
            if path.name != 'current-run.json':
                inventory[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    results = ['pred_vs_actual.json', 'robust.json', 'modes.json', 'evidence_accum.json',
               'partial.json', 'ideal_vs_raw.json', 'prefix.json', 'exp_average.json',
               'attribution.json', 'exp_consistency.json']
    if not args.skip_noise:
        results += ['noise_flip.json', 'drift_flip.json']
    def digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    metadata = {'schema_version': 1, 'session': session.name, 'source_and_result_sha256': inventory,
                'completed_utc': datetime.now(timezone.utc).isoformat(),
                'commands': [command[0] for command in commands],
                'recomputed_result_files': results,
                'external_input_sha256': {'ronin_architecture': digest(paths.RONIN_ARCH),
                                          'ronin_checkpoint': digest(paths.RONIN_CKPT),
                                          **({'raw_bundle': digest(args.bundle)} if args.bundle else {})},
                'scene_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in Path(paths.THOR).glob('FloorPlan*.json')},
                'model_sha256': hashlib.sha256((root / 'analysis/layout/models/phone-five-class.joblib').read_bytes()).hexdigest(),
                'noise_recomputed': not args.skip_noise,
                'scope': 'Development replay; synthetic inputs are geometric trajectories and anchors'}
    (root / 'analysis/layout/current-run.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
