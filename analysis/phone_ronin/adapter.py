"""Native six-axis adapter for the author's separately supplied RoNIN ResNet18.

Uses existing estimated quaternions, never device Euler yaw as body heading.
The reference model is GPLv3; its weights have a separate research license.
"""
import csv, hashlib, importlib.util, json, math, platform
from pathlib import Path
import numpy as np
from analysis.phone_pdr.carry_diagnostic import orientation_trace
from analysis.phone_pdr.pdr import CONFIG, validate_stream
from analysis.phone_pdr.session import validated_output

AUTHOR_COMMIT='805b7f0f28bb164ce89ada9ac05a9470dbe3d715'
AUTHOR_ARCH_SHA256='24a4859272d2ee469ecaef192dddcaa287d40392de21f6c55b5b9b71c76d8e57'
FEATURE_NAMES=['gyro_x','gyro_y','gyro_z','accel_x','accel_y','accel_z']
RATE_HZ=200
WINDOW=200
STRIDE=10
OUTPUT_ROOT=Path(__file__).resolve().parents[2]/'output/phone-pdr'

def rotate_batch(quaternions,vectors):
    q=np.asarray(quaternions,dtype=np.float64);v=np.asarray(vectors,dtype=np.float64)
    if q.ndim!=2 or q.shape[1]!=4 or v.shape!=(len(q),3) or not np.isfinite(q).all() or not np.isfinite(v).all():
        raise ValueError('Finite matching quaternion/vector arrays required')
    if not np.allclose(np.linalg.norm(q,axis=1),1,rtol=0,atol=1e-7):raise ValueError('Unit quaternions required')
    uv=np.cross(q[:,1:],v)
    return v+2*(q[:,:1]*uv+np.cross(q[:,1:],uv))

def prepare_features(accelerometer,gyroscope):
    for stream in (accelerometer,gyroscope):
        validate_stream(stream)
        if max(b[0]-a[0] for a,b in zip(stream,stream[1:]))>CONFIG['maximum_input_gap_s']:
            raise ValueError('Input gap exceeds diagnostic integration limit')
    a=np.asarray(accelerometer,dtype=np.float64);g=np.asarray(gyroscope,dtype=np.float64)
    start=max(a[0,0],g[0,0]);end=min(a[-1,0],g[-1,0])
    if end<=start:raise ValueError('No sensor overlap')
    trace=orientation_trace(accelerometer,gyroscope)
    q=np.array([r['quaternion'] for r in trace]);mask=(g[:,0]>=start)&(g[:,0]<=end)
    times=g[mask,0]
    if len(times)<2 or times[-1]-times[0]<=1:raise ValueError('Insufficient overlap for 1-second windows')
    accel=np.column_stack([np.interp(times,a[:,0],a[:,i]) for i in (1,2,3)])
    world=np.concatenate([rotate_batch(q[mask],g[mask,1:]),rotate_batch(q[mask],accel)],axis=1)
    grid=times[0]+np.arange(math.floor((times[-1]-times[0])*RATE_HZ)+1,dtype=np.float64)/RATE_HZ
    features=np.column_stack([np.interp(grid,times,world[:,i]) for i in range(6)]).astype(np.float32)
    info={'features':list(FEATURE_NAMES),'input_units':['rad/s']*3+['m/s^2 including gravity']*3,
        'grid_rate_hz':RATE_HZ,'resampling':'linear interpolation after rotation on native gyro timestamps; no extrapolation',
        'source_accel_rows':len(a),'source_gyro_rows':len(g),'native_rotation_rows':len(times),'grid_rows':len(grid),
        'grid_start_s':float(grid[0]),'grid_end_s':float(grid[-1]),
        'native_accel_event_rate_hz':float((len(a)-1)/(a[-1,0]-a[0,0])),
        'native_gyro_event_rate_hz':float((len(g)-1)/(g[-1,0]-g[0,0])),
        'feature_mean':features.mean(axis=0,dtype=np.float64).tolist(),
        'feature_std':features.std(axis=0,dtype=np.float64).tolist(),
        'orientation':'existing offline six-axis gravity-aided quaternion; no Android game rotation vector',
        'frame':'estimated gravity-aligned, arbitrary initial horizontal yaw',
        'attitude_independently_validated':False,'additional_bias_or_scale_calibration':False,
        'resampling_increases_observed_bandwidth':False}
    return grid,features,info

def make_windows(times,features):
    t=np.asarray(times,dtype=np.float64);f=np.asarray(features,dtype=np.float32)
    if t.ndim!=1 or len(t)<=WINDOW or f.shape!=(len(t),6) or not np.isfinite(t).all() or not np.isfinite(f).all():
        raise ValueError('Finite 200 Hz six-channel input longer than 1 second required')
    if not np.allclose(np.diff(t),1/RATE_HZ,rtol=0,atol=1e-9):raise ValueError('200 Hz regular grid required')
    # Exactly the start indices of StridedSequenceDataset with interval=window_size.
    starts=np.arange(0,len(t)-WINDOW,STRIDE)
    windows=np.stack([f[i:i+WINDOW].T for i in starts])
    timing=np.column_stack((t[starts],t[starts+WINDOW],(t[starts]+t[starts+WINDOW])/2))
    return windows,timing

def integrate_centers(times,velocities):
    t=np.asarray(times,dtype=np.float64);v=np.asarray(velocities,dtype=np.float64)
    if t.ndim!=1 or len(t)<2 or v.shape!=(len(t),2) or not np.isfinite(t).all() or not np.isfinite(v).all() or np.any(np.diff(t)<=0):
        raise ValueError('Finite ordered prediction times and XY velocities required')
    result=np.zeros_like(v)
    result[1:]=np.cumsum((v[:-1]+v[1:])/2*np.diff(t)[:,None],axis=0)
    return result

def checked_file(path,expected_sha256):
    p=Path(path)
    if len(expected_sha256)!=64 or any(c not in '0123456789abcdef' for c in expected_sha256):raise ValueError('Lowercase SHA256 required')
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('SHA256 identity mismatch: '+str(p))
    return p

def predict(windows,architecture,checkpoint,checkpoint_sha256):
    import torch
    architecture=checked_file(architecture,AUTHOR_ARCH_SHA256)
    checkpoint=checked_file(checkpoint,checkpoint_sha256)
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    spec=importlib.util.spec_from_file_location('ronin_author_resnet1d',architecture)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    network=module.ResNet1D(6,2,module.BasicBlock1D,[2,2,2,2],base_plane=64,
        output_block=module.FCOutputModule,kernel_size=3,fc_dim=512,in_dim=7,dropout=.5,trans_planes=128)
    state=torch.load(checkpoint,map_location='cpu',weights_only=True)
    if not isinstance(state,dict) or 'model_state_dict' not in state:raise ValueError('Author model_state_dict required')
    network.load_state_dict(state['model_state_dict'],strict=True)
    network.eval()
    with torch.inference_mode():
        values=np.concatenate([network(torch.from_numpy(windows[i:i+32])).cpu().numpy() for i in range(0,len(windows),32)])
    if values.shape!=(len(windows),2) or not np.isfinite(values).all():raise ValueError('Invalid model velocities')
    identity={'architecture_commit':AUTHOR_COMMIT,'architecture_sha256':AUTHOR_ARCH_SHA256,
        'checkpoint_sha256':checkpoint_sha256,'checkpoint_bytes':checkpoint.stat().st_size,
        'epoch':state.get('epoch') if isinstance(state.get('epoch'),int) else None,
        'architecture':'RoNIN ResNet18 (6 input, 2 velocity output)','device':'cpu',
        'loading':'torch.load(weights_only=True), strict state_dict','training_performed':False,
        'torch_version':str(torch.__version__),'numpy_version':np.__version__,'python_version':platform.python_version()}
    return values,identity

def write_result(output,report,times,velocities,positions,*,allowed_root=OUTPUT_ROOT,timing=None,features=None,grid=None):
    output=validated_output(output,allowed_root)
    if output.exists():raise FileExistsError('Output must be fresh')
    output.parent.mkdir(parents=True,exist_ok=True);output.mkdir(exist_ok=False)
    with (output/'inference.json').open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
    with (output/'velocity.csv').open('x',encoding='utf-8',newline='') as f:
        writer=csv.writer(f);writer.writerow(['window_start_s','target_end_s','center_s','vx_m_s_model','vy_m_s_model'])
        if timing is None:timing=np.column_stack((times-.5,times+.5,times))
        writer.writerows(np.column_stack((timing,velocities)).tolist())
    with (output/'relative-trajectory.csv').open('x',encoding='utf-8',newline='') as f:
        writer=csv.writer(f);writer.writerow(['time_s','x_m_model','y_m_model']);writer.writerows(np.column_stack((times,positions)).tolist())
    if features is not None:
        with (output/'features.npz').open('xb') as f:np.savez(f,times=grid,features=features)
    return output
