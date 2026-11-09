"""Train one reduced-feature candidate on011's original training matrix only.

Removes raw means, endpoint integrals and sub0.5Hz powers; it is a robustness
hypothesis, not a claim of exact bias invariance. No new/evaluation labels used.
"""
import argparse,hashlib,json
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor


def train(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);dest=out/'trees-distance.joblib'
    if dest.exists():raise FileExistsError('Do not overwrite a trained candidate')
    source=Path('output/research-sync/2026-11-09-raw-input-repair-011/spectral-training/matrix.npz')
    z=np.load(source);keys=z['keys'].tolist()
    selected=[k for k in keys if k=='duration' or k.startswith(('raw_acc_std','gyro_std','linear_std')) or any(k==f'{name}_power{b}' for name in ['vertical','horizontal','angular'] for b in range(1,7))]
    ids=[keys.index(k) for k in selected]
    protocol={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'training_room_ids':list(range(20)),
              'training_segments':len(z['features']),'target':'Endpoint distance, existing synthetic training labels only',
              'features':selected,'n_features':len(selected),'hyperparameters':{'n_estimators':300,'min_samples_leaf':2,'random_state':911},
              'hypothesis':'Reduce dependency on bias-sensitive integrals and means. Low-frequency power excluded; no exact invariance or domain-transfer claim.'}
    (out/'training-freeze.json').write_text(json.dumps(protocol,indent=1))
    model=ExtraTreesRegressor(n_estimators=300,min_samples_leaf=2,random_state=911,n_jobs=2)
    model.fit(z['features'][:,ids],z['targets'])
    joblib.dump({'model':model,'keys':selected,'target':'distance','scope':'Reduced-feature same-generator supervised candidate014'},dest,compress=3)
    (out/'trees-distance.json').write_text(json.dumps({'model_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),**protocol},indent=1))
    print(json.dumps({'n':len(z['targets']),'features':len(selected),'model_sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();train(a.out)
