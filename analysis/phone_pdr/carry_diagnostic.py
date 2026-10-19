"""Exploratory device-rotation/PCA diagnostics, never a body trajectory."""
import argparse,bisect,csv,hashlib,io,json,math
from pathlib import Path
from .pdr import CONFIG,G,_multiply,_normalize,_yaw,validate_stream,diagnose
from .session import load_session,validated_output

PARAMETERS={'window_s':1.0,'transverse_rotation_rms_rad_s':.35,'yaw_rotation_rms_rad_s':.35,
    'high_rotation_peak_rad_s':4.0,'minimum_horizontal_variance_m2_s4':.05,'minimum_axis_energy_fraction':.75}

def rotate_vector(q,v):
    w,x,y,z=q
    return _multiply(_multiply(q,(0,*v)),(w,-x,-y,-z))[1:]

def orientation_trace(accelerometer,gyroscope):
    """Same update as the original relative_yaw, with quaternion states retained."""
    validate_stream(accelerometer);validate_stream(gyroscope)
    for stream in (accelerometer,gyroscope):
        if max(b[0]-a[0] for a,b in zip(stream,stream[1:]))>CONFIG['maximum_input_gap_s']:
            raise ValueError('Input gap exceeds diagnostic integration limit')
    ax,ay,az=_normalize(accelerometer[0][1:])
    q=_normalize((1+az,ay,-ax,0)) if az>-.999999 else (0,1,0,0)
    previous_yaw=_yaw(q);unwrapped=0.0;ai=0
    result=[{'time_s':gyroscope[0][0],'quaternion':q,'device_yaw_rad':0.0}]
    for before,now in zip(gyroscope,gyroscope[1:]):
        dt=now[0]-before[0]
        while ai+1<len(accelerometer) and accelerometer[ai+1][0]<=before[0]:ai+=1
        omega=[(before[j]+now[j])/2 for j in (1,2,3)]
        a=accelerometer[ai][1:];mag=math.sqrt(sum(v*v for v in a))
        if abs(mag-G)<=CONFIG['gravity_magnitude_tolerance_m_s2'] and mag>0:
            measured=[v/mag for v in a];w,x,y,z=q
            predicted=(2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y))
            error=(measured[1]*predicted[2]-measured[2]*predicted[1],
                measured[2]*predicted[0]-measured[0]*predicted[2],
                measured[0]*predicted[1]-measured[1]*predicted[0])
            omega=[v+CONFIG['gravity_feedback_gain_s_inv']*e for v,e in zip(omega,error)]
        speed=math.sqrt(sum(v*v for v in omega));angle=speed*dt
        dq=(math.cos(angle/2),*(v/speed*math.sin(angle/2) for v in omega)) if speed>1e-12 else (1,0,0,0)
        q=_normalize(_multiply(q,dq));angle_now=_yaw(q)
        unwrapped+=math.atan2(math.sin(angle_now-previous_yaw),math.cos(angle_now-previous_yaw))
        previous_yaw=angle_now
        result.append({'time_s':now[0],'quaternion':q,'device_yaw_rad':unwrapped})
    return result

def principal_axis(vectors):
    if any(len(v)!=2 or not all(math.isfinite(x) for x in v) for v in vectors):raise ValueError('Finite XY vectors required')
    empty={'samples':len(vectors),'axis_mod_pi_rad':None,'axis_candidates_rad':None,
        'signed_walking_heading_rad':None,'body_forward_direction_validated':False,
        'interpretation':'horizontal acceleration variability axis, not guaranteed walking direction'}
    if len(vectors)<4:return dict(empty,status='insufficient_samples',variance=0.0,dominant_energy_fraction=None)
    mx=sum(v[0] for v in vectors)/len(vectors);my=sum(v[1] for v in vectors)/len(vectors)
    xx=sum((x-mx)**2 for x,y in vectors)/len(vectors);yy=sum((y-my)**2 for x,y in vectors)/len(vectors)
    xy=sum((x-mx)*(y-my) for x,y in vectors)/len(vectors);total=xx+yy
    dominant=(total+math.sqrt((xx-yy)**2+4*xy*xy))/2
    fraction=dominant/total if total>1e-15 else None
    result=dict(empty,variance=total,dominant_energy_fraction=fraction,covariance_xx_xy_yy=[xx,xy,yy])
    if total<PARAMETERS['minimum_horizontal_variance_m2_s4'] or fraction is None:return dict(result,status='weak_signal')
    if fraction<PARAMETERS['minimum_axis_energy_fraction']:return dict(result,status='near_isotropic')
    axis=(.5*math.atan2(2*xy,xx-yy))%math.pi
    return dict(result,status='axis_only_sign_unknown',axis_mod_pi_rad=axis,axis_candidates_rad=[axis,axis+math.pi])

def diagnose_carry(accelerometer,gyroscope):
    baseline=diagnose(accelerometer,gyroscope)
    start=baseline['overlap_start_s'];end=baseline['overlap_end_s']
    a=[r for r in accelerometer if start<=r[0]<=end];g=[r for r in gyroscope if start<=r[0]<=end]
    trace=orientation_trace(a,g);times=[r['time_s'] for r in trace]
    bins={i:{'g':[],'a':[]} for i in range(math.floor(start),math.floor(end)+1)}
    for row,item in zip(g,trace):
        world=rotate_vector(item['quaternion'],row[1:])
        bins[math.floor(row[0])]['g'].append((row[0],*world))
    skipped=0;max_age=0.0
    for row in a:
        j=bisect.bisect_right(times,row[0])-1
        if j<0:skipped+=1;continue
        world=rotate_vector(trace[j]['quaternion'],row[1:])
        max_age=max(max_age,row[0]-times[j]);bins[math.floor(row[0])]['a'].append((world[0],world[1]))
    windows=[]
    for i,values in bins.items():
        gyro=values['g']
        if not gyro:continue
        transverse=math.sqrt(sum(r[1]**2+r[2]**2 for r in gyro)/len(gyro))
        vertical=math.sqrt(sum(r[3]**2 for r in gyro)/len(gyro))
        peak=max(math.sqrt(sum(v*v for v in r[1:])) for r in gyro)
        if transverse>PARAMETERS['transverse_rotation_rms_rad_s'] or peak>PARAMETERS['high_rotation_peak_rad_s']:
            flag='device_rotation_risk'
        elif vertical>PARAMETERS['yaw_rotation_rms_rad_s']:flag='yaw_rotation_ambiguous'
        else:flag='quiet_device_rotation'
        windows.append({'window_index':i,'start_s':max(start,float(i)),'end_s':min(end,float(i+1)),
            'gyro_samples':len(gyro),'transverse_rms_rad_s':transverse,'vertical_rms_rad_s':vertical,'gyro_peak_rad_s':peak,
            'rotation_flag':flag,'stable_carry_validated':False,'body_heading_observable':False,
            'horizontal_acceleration_axis':principal_axis(values['a'])})
    by_index={w['window_index']:w for w in windows};candidates=[]
    for index,step in enumerate(baseline['step_candidates'],1):
        i=math.floor(step['time_s']);window=by_index.get(i)
        candidates.append({'candidate_index':index,'time_s':step['time_s'],'window_index':i,
            'rotation_flag':window['rotation_flag'] if window else 'no_window',
            'body_heading_rad':None,'candidate_retained':True})
    return {'schema_version':1,'status':'exploratory_device_diagnostic_only','research_validated':False,
        'parameters':dict(PARAMETERS),'body_heading_observable':False,'global_trajectory':None,
        'time_basis':'seconds_since_first_sensor_event','world_axes':'estimated gravity-aligned arbitrary-yaw frame, not independently validated',
        'overlap_start_s':start,'overlap_end_s':end,'accel_without_preceding_trace':skipped,'max_trace_age_s':max_age,
        'windows':windows,'window_links':[{'from':x['window_index'],'to':y['window_index'],'relative_body_angle_rad':None} for x,y in zip(windows,windows[1:])],
        'step_candidates':candidates,'candidate_count':len(candidates),
        'limitations':['thresholds are exploratory engineering flags, not stable-carry labels',
            'pure vertical phone regrip can match a body turn; gyro alone cannot guarantee separation',
            'PCA axis has 180-degree sign ambiguity and may follow lateral sway',
            'initial gravity, attitude feedback and gyro bias remain unvalidated',
            'no segment stitching, distance scale, direction correction, wall or map inference']}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    out=validated_output(args.output,root/'output/phone-pdr')
    if out.exists():raise FileExistsError('Output must be fresh')
    a,g,source=load_session(args.session);report=diagnose_carry(a,g);report['source']=source
    report['implementation_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('pdr.py'),Path(__file__).with_name('session.py')]}
    payload=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
    summary=io.StringIO(newline='');writer=csv.writer(summary)
    writer.writerow(['window_index','start_s','end_s','rotation_flag','transverse_rms_rad_s','vertical_rms_rad_s','horizontal_axis_mod_pi_rad','axis_status'])
    for w in report['windows']:
        axis=w['horizontal_acceleration_axis'];writer.writerow([w[k] for k in ['window_index','start_s','end_s','rotation_flag','transverse_rms_rad_s','vertical_rms_rad_s']]+[axis['axis_mod_pi_rad'],axis['status']])
    out.parent.mkdir(parents=True,exist_ok=True);out.mkdir(exist_ok=False)
    for name,data in [('carry-diagnostic.json',payload),('window-metrics.csv',summary.getvalue().encode('utf-8'))]:
        with (out/name).open('xb') as s:s.write(data)
    print(json.dumps({'output':str(out),'windows':len(report['windows']),'candidates_retained':report['candidate_count'],'body_heading_observable':False},ensure_ascii=True))

if __name__=='__main__':main()
