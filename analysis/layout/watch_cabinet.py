"""Three-axis16.7Hz wrist input for cabinet events in the joint branch.

The untrained rule uses low-frequency gravity-direction variation and motion
energy, never a phone cabinet label or simulator action metadata. Thresholds
are development choices, not calibrated probabilities or a validated S5 model.
"""
import csv
from pathlib import Path
import numpy as np
from scipy.ndimage import uniform_filter1d

SETTINGS={'window_s':3.,'step_s':.5,'direction_dispersion_min':.045,
 'norm_rms_min_m_s2':.10,'minimum_run_s':1.,'watch_axes':3,'watch_gyro':False,
 'scope':'Controlled wrist pulling/pronation protocol; untrained event rule'}


def load(session,origin_ns):
    path=Path(session)/'watch/accelerometer.csv'
    if not path.exists():return None
    with path.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    return np.array([(int(r['sensor_timestamp_ns'])-int(origin_ns))/1e9 for r in rows]),np.array([[float(r[k]) for k in 'xyz'] for r in rows])


def detect(time,acceleration,budget_s=None,phone=None):
    t=np.asarray(time);A=np.asarray(acceleration)
    if len(t)<8 or A.shape!=(len(t),3) or np.any(np.diff(t)<=0):return {'runs':[],'windows':[],'status':'insufficient'}
    budget=t[-1] if budget_s is None else budget_s;keep=t<=budget;t=t[keep];A=A[keep]
    if len(t)<8:return {'runs':[],'windows':[],'status':'insufficient'}
    fs=1/np.median(np.diff(t))
    windows=[];runs=[]
    for end in np.arange(SETTINGS['window_s'],budget+1e-9,SETTINGS['step_s']):
        mask=(t>=end-SETTINGS['window_s'])&(t<end)
        if mask.sum()<10 or end-t[mask][-1]>.15 or t[mask][0]-(end-SETTINGS['window_s'])>.15:continue
        x=uniform_filter1d(A[mask],max(2,int(.20*fs)),axis=0,mode='nearest');norm=np.linalg.norm(x,axis=1);u=x/np.maximum(norm[:,None],1e-9);dispersion=1-float(np.linalg.norm(u.mean(axis=0)))
        dynamic=float(np.sqrt(np.mean((np.linalg.norm(A[mask],axis=1)-9.81)**2)))
        quiet_phone=True
        if phone is not None:
            pt,pa,pg=phone;pm=(pt>=end-SETTINGS['window_s'])&(pt<end)
            quiet_phone=bool(pm.sum()>=10 and np.sqrt(pa[pm].var(axis=0).sum())<.25 and np.sqrt(np.mean(np.sum(pg[pm]**2,axis=1)))<.08)
        cabinet=dispersion>=SETTINGS['direction_dispersion_min'] and dynamic>=SETTINGS['norm_rms_min_m_s2'] and quiet_phone
        centre=end-1.5;windows.append({'center_s':centre,'available_s':float(end),'cabinet':bool(cabinet),'direction_dispersion':dispersion,'norm_rms':dynamic,'quiet_phone_gate':quiet_phone})
        if cabinet:
            if runs and centre-runs[-1][2]<.76:runs[-1][2]=centre
            else:runs.append(['cabinet',centre,centre])
    runs=[r for r in runs if r[2]-r[1]>=SETTINGS['minimum_run_s']]
    return {'status':'ok','runs':runs,'windows':windows,'settings':SETTINGS,'time_sync':'simulated common clock only; real-clock qualification separate'}


def fuse(phone_actions,watch_actions):
    # The wrist is the ONLY cabinet source in this arm. Keeping the phone
    # cabinet event here would hide whether the watch contributes anything.
    runs=[]
    for label,start,end in phone_actions['runs']:
        if label not in ('walk','seated','lying','other'):continue
        pieces=[(start,end)]
        for _,a,b in watch_actions['runs']:
            nextpieces=[]
            for lo,hi in pieces:
                if b<=lo or a>=hi:nextpieces.append((lo,hi));continue
                if lo<a:nextpieces.append((lo,a))
                if b<hi:nextpieces.append((b,hi))
            pieces=nextpieces
        runs.extend([[label,lo,hi] for lo,hi in pieces])
    runs.extend(watch_actions['runs']);return {'runs':sorted(runs,key=lambda r:r[1]),'cabinet_source':'watch_accelerometer','phone_cabinet_used':False}
