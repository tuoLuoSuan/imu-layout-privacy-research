"""Arrival-aware, independently recomputed prefixes of the phone model branch.

No time alignment with a watch, activity classifier, room model, or training is
implemented here. Those are separate parts of the joint-device research.
"""
import argparse,csv,hashlib,io,json,math,zipfile
from pathlib import Path
import numpy as np
from analysis.phone_pdr.session import load_session,validated_output
from analysis.phone_pdr.pdr import CONFIG,validate_stream
from .adapter import (OUTPUT_ROOT,RATE_HZ,WINDOW,prepare_features,make_windows,
    integrate_centers,predict)

def load_arrival_session(path):
    """Validate the existing bundle and recover event/receipt clock differences."""
    a,g,source=load_session(path);path=Path(path)
    names=('accelerometer.csv','gyroscope.csv','metadata.json')
    if path.is_dir():payload={n:(path/n).read_bytes() for n in names}
    else:
        with zipfile.ZipFile(path) as z:payload={n:z.read(n) for n in names}
    native=[]
    for name in names[:2]:
        reader=csv.DictReader(io.StringIO(payload[name].decode('utf-8-sig')))
        if 'received_elapsed_realtime_ns' not in (reader.fieldnames or []):
            raise ValueError('Native callback availability is required')
        rows=[(int(r['sensor_timestamp_ns']),int(r['received_elapsed_realtime_ns'])) for r in reader]
        if any(receipt<event for event,receipt in rows) or any(y[1]<x[1] for x,y in zip(rows,rows[1:])):
            raise ValueError('Invalid event/receipt clock relation')
        native.append(rows)
    origin=min(native[0][0][0],native[1][0][0])
    availability=[[(receipt-origin)/1e9 for event,receipt in rows] for rows in native]
    metadata=json.loads(payload['metadata.json'])
    stop=metadata.get('stop_elapsed_ns')
    source=dict(source,event_origin_ns=origin,
        budget_clock='seconds since first native sensor event; callback receipt uses same elapsedRealtime base',
        callback_clock_alignment='Android API clock-base assumption, not external timing validation',
        recorded_stop_s=(stop-origin)/1e9 if isinstance(stop,int) and not isinstance(stop,bool) else None,
        last_callback_receipt_s=[max(values) for values in availability])
    return a,g,*availability,source

def prefix_inputs(accelerometer,gyroscope,accel_arrivals,gyro_arrivals,budget_s):
    if not math.isfinite(budget_s) or budget_s<=0:raise ValueError('Finite positive budget required')
    selected=[];receipts=[];late=[];gaps=[]
    for stream,available in [(accelerometer,accel_arrivals),(gyroscope,gyro_arrivals)]:
        if len(stream)!=len(available):raise ValueError('Missing native availability rows')
        rows=[];used=[];excluded=0
        for row,arrival in zip(stream,available):
            if not math.isfinite(arrival):raise ValueError('Finite native availability required')
            if row[0]<=budget_s and arrival>budget_s:excluded+=1
            if row[0]<=budget_s and arrival<=budget_s:
                if arrival<row[0]:raise ValueError('Receipt precedes event')
                rows.append(row);used.append(arrival)
        selected.append(rows);receipts.extend(used);late.append(excluded)
        gaps.append(max((y[0]-x[0] for x,y in zip(rows,rows[1:])),default=0.))
    info={'budget_s':float(budget_s),'eligible_accel_rows':len(selected[0]),'eligible_gyro_rows':len(selected[1]),
        'last_raw_arrival_s':float(max(receipts)) if receipts else None,
        'last_raw_event_s':float(max(s[-1][0] for s in selected if s)) if any(selected) else None,
        'selection':'event_time <= budget AND callback_receipt_time <= budget before all preprocessing',
        'excluded_late_rows':dict(zip(('accelerometer','gyroscope'),late)),
        'max_effective_gap_s':float(max(gaps)),
        'per_sensor_max_effective_gap_s':dict(zip(('accelerometer','gyroscope'),map(float,gaps))),
        'resampling_interpolation_used':False,
        'late_row_exclusion_occurred':any(late),
        'raw_unobserved_tail_s':float(max(0.,budget_s-min(s[-1][0] for s in selected))) if all(selected) else None}
    return *selected,info

def eligible_window_mask(timing,budget_s):
    t=np.asarray(timing,dtype=float)
    if t.ndim!=2 or t.shape[1]!=3 or not np.isfinite(t).all() or not math.isfinite(budget_s):
        raise ValueError('Finite start, target-end, center timing required')
    return t[:,1]<=budget_s

def evaluate_prefix(accelerometer,gyroscope,accel_arrivals,gyro_arrivals,budget_s,predictor,*,support_end_s=None):
    """Require recorded stop metadata; array length never establishes support.

    Missing support returns unknown without inference. Explicit metadata remains
    a provenance contract, not a proof against forged source metadata.
    """
    if support_end_s is not None and (isinstance(support_end_s,bool) or not math.isfinite(support_end_s) or support_end_s<0):
        raise ValueError('Finite nonnegative recorded support required')
    a,g,info=prefix_inputs(accelerometer,gyroscope,accel_arrivals,gyro_arrivals,budget_s)
    summary=dict(info,status='insufficient_model_context',prediction_count=0,path_end_m_model=None,
        endpoint_m_model=None,first_center_s=None,last_center_s=None,last_target_end_s=None,
        last_input_grid_sample_s=None,feature_sha256=None,input_sample_span_s=(WINDOW-1)/RATE_HZ,
        target_interval_s=WINDOW/RATE_HZ,accuracy_validated=False,layout=None,
        support_end_s=float(support_end_s) if support_end_s is not None else None,
        support_source='caller_recorded_stop_metadata' if support_end_s is not None else 'unknown')
    empty={'summary':summary,'timing':np.empty((0,3)),'velocities':np.empty((0,2)),
        'positions':np.empty((0,2))}
    if support_end_s is None:
        summary['status']='unknown_support'
        return empty
    if budget_s>support_end_s:
        summary.update(status='outside_recorded_session',support_end_s=float(support_end_s))
        return empty
    if min(len(a),len(g))<2:return empty
    for stream in (a,g):validate_stream(stream)
    if summary['max_effective_gap_s']>CONFIG['maximum_input_gap_s']:
        summary.update(status='input_gap_exceeds_limit',gap_limit_s=CONFIG['maximum_input_gap_s'])
        return empty
    if min(a[-1][0],g[-1][0])-max(a[0][0],g[0][0])<=WINDOW/RATE_HZ:return empty
    grid,features,preparation=prepare_features(a,g)
    summary['resampling_interpolation_used']=True
    windows,timing=make_windows(grid,features)
    mask=eligible_window_mask(timing,budget_s);windows=windows[mask];timing=timing[mask]
    if len(windows)<2:return empty
    velocities=np.asarray(predictor(windows),dtype=np.float64)
    if velocities.shape!=(len(windows),2) or not np.isfinite(velocities).all():raise ValueError('Invalid prefix model velocities')
    positions=integrate_centers(timing[:,2],velocities)
    summary.update(status='adapted_arrival_prefix_only',prediction_count=len(windows),
        path_end_m_model=float(np.linalg.norm(np.diff(positions,axis=0),axis=1).sum()),
        endpoint_m_model=positions[-1].tolist(),first_center_s=float(timing[0,2]),last_center_s=float(timing[-1,2]),
        last_target_end_s=float(timing[-1,1]),last_input_grid_sample_s=float(timing[-1,1]-1/RATE_HZ),
        feature_sha256=hashlib.sha256(windows.tobytes()).hexdigest(),
        preprocessing='independently rerun quaternion/rotation/interpolation on available native prefix',
        budget_endpoint_is_not_trajectory_time=True)
    return {'summary':summary,'timing':timing,'velocities':velocities,'positions':positions}

def path_end(accelerometer,gyroscope,accel_arrivals,gyro_arrivals,budget_s,predictor,*,support_end_s=None):
    """Available modeled path length, not position or completed motion at T."""
    return evaluate_prefix(accelerometer,gyroscope,accel_arrivals,gyro_arrivals,budget_s,predictor,support_end_s=support_end_s)['summary']['path_end_m_model']

def write_prefix_results(output,metadata,results,*,allowed_root=OUTPUT_ROOT):
    output=validated_output(output,allowed_root)
    if output.exists():raise FileExistsError('Prefix output must be fresh')
    output.parent.mkdir(parents=True,exist_ok=True);output.mkdir(exist_ok=False)
    report=dict(metadata,prefixes=[r['summary'] for r in results])
    with (output/'prefixes.json').open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
    for index,result in enumerate(results):
        if result['summary']['prediction_count']==0:continue
        directory=output/('prefix-%03d'%index);directory.mkdir()
        timing=result['timing'];v=result['velocities'];positions=result['positions']
        columns=['window_start_s','target_end_s','center_s','input_last_grid_sample_s','vx_m_s_model','vy_m_s_model']
        with (directory/'velocity.csv').open('x',encoding='utf-8',newline='') as f:
            w=csv.writer(f);w.writerow(columns);w.writerows(np.column_stack((timing,timing[:,1]-1/RATE_HZ,v)).tolist())
        with (directory/'relative-trajectory.csv').open('x',encoding='utf-8',newline='') as f:
            w=csv.writer(f);w.writerow(['center_time_s','x_m_model','y_m_model']);w.writerows(np.column_stack((timing[:,2],positions)).tolist())
    return output

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path);parser.add_argument('--architecture',type=Path,required=True)
    parser.add_argument('--checkpoint',type=Path,required=True);parser.add_argument('--checkpoint-sha256',required=True)
    parser.add_argument('--budget',type=float,action='append',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--yaw-ensemble',type=int,choices=(1,4),default=1,help='Optional fixed C4 frame-control average; no accuracy claim')
    args=parser.parse_args()
    if len(args.budget)!=len(set(args.budget)) or any(not math.isfinite(t) or t<=0 for t in args.budget):
        raise ValueError('Distinct finite positive budgets required')
    output=validated_output(args.output,OUTPUT_ROOT)
    if output.exists():raise FileExistsError('Prefix output must be fresh')
    a,g,aa,ga,source=load_arrival_session(args.input);results=[];model=None
    def single_inference(windows):
        nonlocal model
        velocities,model=predict(windows,args.architecture,args.checkpoint,args.checkpoint_sha256)
        return velocities
    def inference(windows):
        if args.yaw_ensemble==1:return single_inference(windows)
        from .ensemble import c4_predict
        return c4_predict(windows,single_inference)
    support_end=source['recorded_stop_s']
    for budget in args.budget:
        result=evaluate_prefix(a,g,aa,ga,budget,inference,support_end_s=support_end)
        results.append(result);print(json.dumps(result['summary'],ensure_ascii=False),flush=True)
    metadata={'schema_version':1,'source':source,'model':model,'accuracy_validated':False,'joint_device_result':False,
        'yaw_ensemble':args.yaw_ensemble,'ensemble_accuracy_validated':False,
        'time_rule':'event and callback receipt <= budget; preprocess native prefix independently; target_end <= budget',
        'path_end_definition':'trapezoid integration between centers of available predicted average velocities; not position at budget',
        'reference_geometry_used':False,'training_performed':False,
        'limitations':['estimated initial attitude/bias unvalidated; original first-sample attitude initialization retained',
            'receipt times provide logged API availability, not processing completion or external clock validation',
            'whole-bundle integrity validation and provenance are distinct from numerical prefix inputs',
            'phone-only inference branch; watch clock alignment and spatial fusion remain unimplemented']}
    write_prefix_results(output,metadata,results)
    print(json.dumps({'output':str(output),'prefix_count':len(results)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
