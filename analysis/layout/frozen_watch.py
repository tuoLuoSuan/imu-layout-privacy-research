"""Existing Nov4 eight-class wrist RF, reused without fitting or new weights.

Three-axis acceleration only. The original artifact stays local; its hash and
feature order are checked. Cabinet is the model's merged open/close class.
"""
import hashlib,json,os
from pathlib import Path
import joblib,numpy as np
from . import paths
from .action_features import event_features,temporal

MODEL_SHA256='0a2e3b6fbccfa737f5c1bea16e4c63f7d6bfdbe702f9330d400aba251e93156b'


def load_model():
    source=Path(os.environ.get('IMU_LAYOUT_WATCH_MODEL',str(Path(paths.REPO)/'output/action-recognition/2026-11-04-t3-freeze-001/model-8-watch.joblib')))
    if hashlib.sha256(source.read_bytes()).hexdigest()!=MODEL_SHA256:raise ValueError('Frozen wrist model identity mismatch')
    model=joblib.load(source);model['model'].n_jobs=1;return model


def predict(time,acceleration,budget_s=None,model=None):
    model=load_model() if model is None else model;t=np.asarray(time);A=np.asarray(acceleration);budget=t[-1] if budget_s is None else budget_s;windows=[];matrix=[]
    for end in np.arange(3.,budget+1e-9,.5):
        mask=(t>=end-3)&(t<end)
        if mask.sum()<8 or end-t[mask][-1]>.2 or t[mask][0]-(end-3)>.2:continue
        feature=event_features(t,A,end-3,end,normalize=True);feature.update(temporal({'watch_acc':(t[mask]-(end-3),A[mask])},'watch'))
        matrix.append([feature[key] for device,key in model['columns']]);windows.append({'start_s':float(end-3),'end_s':float(end),'center_s':float(end-1.5),'available_s':float(end)})
    runs=[]
    if matrix:
        probs=model['model'].predict_proba(np.array(matrix));classes=list(model['model'].classes_)
        for w,p in zip(windows,probs):
            w.update(label=str(classes[int(p.argmax())]),cabinet_probability=float(p[classes.index('cabinet')]))
            if w['label']=='cabinet':
                # The support is a3s event interval, not a zero-length state
                # at the window centre. This retains short door gestures.
                if runs and w['start_s']<=runs[-1][2]:runs[-1][2]=w['end_s']
                else:runs.append(['cabinet',w['start_s'],w['end_s']])
    return {'runs':runs,'windows':windows,'model_sha256':MODEL_SHA256,'training_performed':False,'probabilities_calibrated':False,'scope':'Old frozen wrist model; this window-support adapter is separate from the development rule'}
