"""Classical inertial diagnostics, with explicit calibration and heading limits.

No map, loop closure, learned weights, or ground-truth corrections are used.
Peak detector defaults are engineering starting values, not research gates.
"""
import bisect
import math

G=9.80665
CONFIG={'fast_tau_s':0.08,'baseline_tau_s':0.7,'peak_threshold_m_s2':0.6,
        'minimum_step_interval_s':0.3,'gravity_feedback_gain_s_inv':0.5,
        'gravity_magnitude_tolerance_m_s2':1.5,'maximum_input_gap_s':1.0}

def validate_stream(rows):
    if len(rows)<2:raise ValueError('At least two samples required')
    previous=None
    for row in rows:
        if len(row)!=4 or not all(math.isfinite(v) for v in row):raise ValueError('Samples must be finite t,x,y,z')
        if previous is not None and row[0]<=previous:raise ValueError('Non-increasing timestamp')
        previous=row[0]

def weinberg_stride(amplitude, coefficient):
    if not all(math.isfinite(x) and x>0 for x in (amplitude,coefficient)):
        raise ValueError('Positive finite amplitude and coefficient required')
    return coefficient*amplitude**0.25

def _multiply(q,r):
    w,x,y,z=q;a,b,c,d=r
    return (w*a-x*b-y*c-z*d,w*b+x*a+y*d-z*c,w*c-x*d+y*a+z*b,w*d+x*c-y*b+z*a)

def _normalize(v):
    n=math.sqrt(sum(x*x for x in v))
    if n<1e-12:raise ValueError('Zero vector cannot define orientation')
    return tuple(x/n for x in v)

def _yaw(q):
    w,x,y,z=q
    return math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))

def relative_yaw(accelerometer, gyroscope):
    validate_stream(accelerometer);validate_stream(gyroscope)
    ax,ay,az=_normalize(accelerometer[0][1:])
    # Minimal rotation mapping the first measured gravity direction to world +Z.
    q=_normalize((1+az,ay,-ax,0)) if az>-0.999999 else (0,1,0,0)
    previous_yaw=_yaw(q);unwrapped=0.0;result=[(gyroscope[0][0],0.0)];ai=0
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
        previous_yaw=angle_now;result.append((now[0],unwrapped))
    return result

def detect_steps(accelerometer):
    validate_stream(accelerometer)
    first=math.sqrt(sum(v*v for v in accelerometer[0][1:]));fast=slow=first
    history=[];valley=first;last_peak=-math.inf;steps=[]
    for i,row in enumerate(accelerometer):
        if i:
            dt=row[0]-accelerometer[i-1][0];magnitude=math.sqrt(sum(v*v for v in row[1:]))
            fast+=(1-math.exp(-dt/CONFIG['fast_tau_s']))*(magnitude-fast)
            slow+=(1-math.exp(-dt/CONFIG['baseline_tau_s']))*(magnitude-slow)
        valley=min(valley,fast);history.append((row[0],fast-slow,fast))
        if len(history)<3:continue
        left,peak,right=history[-3:]
        if (peak[1]>=CONFIG['peak_threshold_m_s2'] and peak[1]>left[1] and peak[1]>=right[1]
                and peak[0]-last_peak>=CONFIG['minimum_step_interval_s']):
            amplitude=peak[2]-valley
            if amplitude>0:
                steps.append({'time_s':peak[0],'detected_at_s':right[0],'amplitude_m_s2':amplitude})
                last_peak=peak[0];valley=peak[2]
        if len(history)>3:history.pop(0)
    return steps

def diagnose(accelerometer, gyroscope, stride_coefficient=None):
    validate_stream(accelerometer);validate_stream(gyroscope)
    if stride_coefficient is not None:weinberg_stride(1.0,stride_coefficient)
    for stream in (accelerometer,gyroscope):
        if max(b[0]-a[0] for a,b in zip(stream,stream[1:]))>CONFIG['maximum_input_gap_s']:
            raise ValueError('Input gap exceeds diagnostic integration limit; no gap filling')
    start=max(accelerometer[0][0],gyroscope[0][0]);end=min(accelerometer[-1][0],gyroscope[-1][0])
    a=[r for r in accelerometer if start<=r[0]<=end];g=[r for r in gyroscope if start<=r[0]<=end]
    headings=relative_yaw(a,g);times=[h[0] for h in headings]
    steps=detect_steps(a);x=y=0.0
    for step in steps:
        j=bisect.bisect_right(times,step['time_s'])-1
        if j<0:raise ValueError('No preceding gyro orientation for candidate')
        yaw=headings[j][1];length=weinberg_stride(step['amplitude_m_s2'],stride_coefficient or 1.0)
        x+=length*math.cos(yaw);y+=length*math.sin(yaw)
        step.update(device_yaw_rad=yaw,heading_sample_age_s=step['time_s']-times[j],
                    relative_x=x,relative_y=y,x_m=x if stride_coefficient is not None else None,
                    y_m=y if stride_coefficient is not None else None)
    def stats(rows):
        return {'rows':len(rows),'span_s':rows[-1][0]-rows[0][0],
                'event_rate_hz':(len(rows)-1)/(rows[-1][0]-rows[0][0])}
    return {'schema_version':1,'status':'diagnostic_only','research_validated':False,
            'motion_labels':'not_provided','coordinate_units':'m_coefficient_unverified' if stride_coefficient is not None else 'uncalibrated_amplitude_scale',
            'config':dict(CONFIG),'stride_coefficient':stride_coefficient,
            'accelerometer':stats(accelerometer),'gyroscope':stats(gyroscope),
            'overlap_start_s':start,'overlap_end_s':end,
            'boundary_excluded_rows':{'accelerometer':len(accelerometer)-len(a),'gyroscope':len(gyroscope)-len(g)},
            'candidate_count':len(steps),'step_candidates':steps,
            'relative_device_yaw_end_rad':headings[-1][1],
            'assumptions':['first accelerometer sample approximates gravity; not independently verified',
                           'device orientation follows walking direction with fixed offset; not independently verified',
                           'gyro bias not calibrated; heading drift is unconstrained',
                           'peak candidates are not labelled human footsteps',
                           'no trajectory reference; no wall or room inference',
                           'candidate decisions have one-sample delay; no observation-budget result claimed']}
