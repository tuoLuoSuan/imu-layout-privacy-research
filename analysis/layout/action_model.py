"""Frozen five-class model and prefix-safe inference on native phone samples."""

import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path

import joblib
import numpy as np

try:
    from .action_features import features_at
    from . import paths
except ImportError:
    from action_features import features_at
    import paths


WINDOW_S = 3.0
STEP_S = 0.5
A_SEG = [(0, 6, 'other'), (6, 12, 'walk'), (12, 20, 'cabinet'),
         (20, 26, 'walk'), (26, 39, 'lying'), (39, 43, 'walk'),
         (43, 48, 'walk'), (48, 56, 'seated'), (56, 60, 'walk'), (60, 66, 'walk')]
B_SEG = [(0, 6, 'other'), (6, 12, 'walk'), (12, 24, 'seated'),
         (24, 28, 'walk'), (28, 34, 'walk'), (34, 47, 'lying'),
         (47, 51, 'walk'), (51, 57, 'walk'), (57, 63, 'cabinet'), (63, 69, 'walk')]
MODEL_PATH = Path(paths.REPO) / 'analysis' / 'layout' / 'models' / 'phone-five-class.joblib'


def load_phone(session, require_receipts=False):
    phone = Path(session) / 'phone'
    channels = {}
    origin = None
    for name in ('accelerometer', 'gyroscope'):
        with (phone / (name + '.csv')).open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise ValueError('Empty phone sensor channel')
        if require_receipts and 'received_elapsed_realtime_ns' not in rows[0]:
            raise ValueError('Native callback receipt timestamps are required for causal-prefix evaluation')
        if origin is None:
            origin = int(rows[0]['sensor_timestamp_ns'])
        time = np.array([(int(row['sensor_timestamp_ns']) - origin) / 1e9 for row in rows])
        xyz = np.array([[float(row[axis]) for axis in 'xyz'] for row in rows])
        arrival = np.array([(int(row.get('received_elapsed_realtime_ns') or row['sensor_timestamp_ns']) - origin) / 1e9
                            for row in rows])
        channels[name] = (time, xyz, arrival)
    return channels


def predict_timeline(model, ta, acceleration, tg, gyro, budget_s=None,
                     accel_arrivals=None, gyro_arrivals=None):
    budget = min(float(ta[-1]), float(tg[-1])) if budget_s is None else float(budget_s)
    selected = []
    for time, xyz, arrivals in ((ta, acceleration, accel_arrivals), (tg, gyro, gyro_arrivals)):
        time, xyz = np.asarray(time), np.asarray(xyz)
        keep = time <= budget
        if arrivals is not None:
            keep &= np.asarray(arrivals) <= budget
        receipt = time if arrivals is None else np.asarray(arrivals)
        selected.append((time[keep], xyz[keep], receipt[keep]))
    (ta, acceleration, aa), (tg, gyro, ga) = selected
    if len(ta) < 4 or len(tg) < 4:
        return {'runs': [], 'windows': [], 'budget_s': budget}
    last_start = min(budget, float(ta[-1]), float(tg[-1])) - WINDOW_S
    windows = []
    matrix = []
    for start in np.arange(1.0, last_start + 1e-9, STEP_S):
        features = features_at(ta, acceleration, tg, gyro, float(start))
        if features is None:
            continue
        matrix.append([features[key] for key in model['keys']])
        received = [float(arrival[(time >= start) & (time < start + WINDOW_S)].max())
                    for time, arrival in ((ta, aa), (tg, ga))]
        windows.append({'start_s': float(start), 'end_s': float(start + WINDOW_S),
                        'center_s': float(start + WINDOW_S / 2),
                        'available_s': max(float(start + WINDOW_S), *received)})
    if matrix:
        for window, label in zip(windows, model['classifier'].predict(np.asarray(matrix, float))):
            window['label'] = str(label)
    runs = []
    for window in windows:
        center, label = window['center_s'], window['label']
        if runs and runs[-1][0] == label and center - runs[-1][2] < 1.2:
            runs[-1][2] = center
        else:
            runs.append([label, center, center])
    return {'runs': runs, 'windows': windows, 'budget_s': budget,
            'time_definition': 'Window centers; predictions use only samples and arrivals within budget'}


def train(rounds_root, output=MODEL_PATH):
    from sklearn.ensemble import RandomForestClassifier

    features, labels, keys, sources = [], [], None, []
    for tag, segments in (('r1', A_SEG), ('r2', A_SEG), ('r3', B_SEG), ('r4', B_SEG)):
        session = Path(rounds_root) / ('2026-11-06-round-' + tag)
        channels = load_phone(session)
        ta, acceleration, _ = channels['accelerometer']
        tg, gyro, _ = channels['gyroscope']
        offset = json.loads((session / 'cue-sync.json').read_text(encoding='utf-8'))['t0']
        hashes = {name: hashlib.sha256((session / 'phone' / (name + '.csv')).read_bytes()).hexdigest()
                  for name in ('accelerometer', 'gyroscope')}
        sources.append({'round': tag, 'sensor_sha256': hashes, 'cue_offset_s': offset})
        for begin, end, label in segments:
            for start in np.arange(begin + offset, end + offset - WINDOW_S + 1e-6, STEP_S):
                row = features_at(ta, acceleration, tg, gyro, float(start))
                if row is None:
                    continue
                if keys is None:
                    keys = sorted(row)
                features.append([row[key] for key in keys])
                labels.append(label)
    classifier = RandomForestClassifier(n_estimators=400, random_state=0,
                                        max_features='sqrt', n_jobs=1)
    classifier.fit(np.asarray(features, float), np.asarray(labels))
    model = {'classifier': classifier, 'keys': keys, 'window_s': WINDOW_S, 'step_s': STEP_S}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output, compress=3)
    metadata = {'schema_version': 1, 'training_windows': len(labels), 'rounds': sources,
                'labels': sorted(set(labels)), 'feature_count': len(keys),
                'model_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                'label_source': 'Cue-aligned protocol segments; four same-person development rounds',
                'generalization_accuracy_validated': False,
                'package_versions': {package: importlib.metadata.version(package) for package in
                                     ('numpy', 'scipy', 'scikit-learn', 'torch', 'matplotlib', 'joblib')},
                'feature_code_sha256': hashlib.sha256(Path(features_at.__code__.co_filename).read_bytes()).hexdigest()}
    output.with_suffix('.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return metadata


def load_model(path=MODEL_PATH):
    path = Path(path)
    metadata = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata['model_sha256']:
        raise ValueError('Frozen action model hash mismatch')
    return joblib.load(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['train'])
    parser.add_argument('--rounds-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=MODEL_PATH)
    args = parser.parse_args()
    print(json.dumps(train(args.rounds_root, args.output), ensure_ascii=False, indent=2))
