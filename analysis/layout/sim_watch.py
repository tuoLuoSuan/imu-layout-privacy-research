"""Left-wrist kinematics sampled as three-axis acceleration at16.7Hz.

Only acceleration is exported. Wrist pose and activity truth stay in the
evaluator. Cabinet pull/pronation occurs on this wrist, not the right phone.
"""
import csv
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from .contact_contract import body_axis
from .simulation_validation import physical_report
from .sim_handset import s5


def generate(phone,seed,fs=16.7):
    t=phone['t'];p=phone['truth']['pos'].copy();R=phone['truth']['R'].copy();labels=phone['truth']['label'];dt=1/phone['fs']
    for seg in phone['script']:
        mask=(t>=seg['start'])&(t<seg['end']);ids=np.flatnonzero(mask);local=t[ids]-seg['start'];duration=seg['end']-seg['start'];gate=s5(local/.8)*s5((duration-local)/.8)
        forward=np.asarray(seg['heading']);side=np.array([-forward[1],forward[0]])
        if seg['label']=='cabinet':
            phase=2*np.pi*.55*local
            p[ids,:2]+=(.25*gate+.10*gate*np.sin(phase))[:,None]*forward
            p[ids,2]+=.03*gate*np.sin(phase+.3)
            R[ids]=R[ids]@Rotation.from_euler('xyz',np.c_[.75*gate*np.sin(phase),.25*gate*np.sin(phase+.4),.30*gate*np.sin(phase+.8)]).as_matrix()
        elif seg['label']=='walk':
            u=local/duration;gate=np.sin(np.pi*u)**2;phase=2*np.pi*1.1*local
            p[ids,:2]+=.08*gate[:,None]*np.sin(phase)[:,None]*forward+.025*gate[:,None]*np.cos(phase)[:,None]*side
            R[ids]=R[ids]@Rotation.from_euler('x',(.18*gate*np.sin(phase))[:,None]).as_matrix()
    velocity=np.gradient(p,dt,axis=0,edge_order=2);acceleration=np.gradient(velocity,dt,axis=0,edge_order=2)
    clean=np.einsum('nji,nj->ni',R,acceleration+[0,0,9.81]);grid=np.arange(0,t[-1],1/fs)
    acc=np.column_stack([np.interp(grid,t,clean[:,j]) for j in range(3)]);rng=np.random.default_rng(seed)
    pos=np.column_stack([np.interp(grid,t,p[:,j]) for j in range(3)]);rot=Slerp(t,Rotation.from_matrix(R))(grid).as_matrix()
    return {'t':grid,'acc':acc+rng.normal(0,.06,acc.shape),'clean_acc':acc,'truth':{'pos':pos,'R':rot},'fs':fs,'shared_clock':True,'source':'independent left wrist motion, only accel exported'}


def write(session,watch):
    dst=Path(session)/'watch';dst.mkdir(exist_ok=True)
    with (dst/'accelerometer.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['sequence','sensor_timestamp_ns','x','y','z'])
        for i,(t,a) in enumerate(zip(watch['t'],watch['acc']),1):w.writerow([i,1700000000000000000+int(round(t*1e9)),*map(float,a)])
