"""Offline, researcher-annotated short-walk calibration. No layout inference."""
import argparse,csv,hashlib,io,json,math,statistics
from pathlib import Path
from .pdr import diagnose,relative_yaw
from .session import load_session,validated_output

TIME_BASIS='seconds_since_first_sensor_event'
ROOT=Path(__file__).resolve().parents[2]

def _number(value,name,minimum=None):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError(name+' must be finite numeric')
    if minimum is not None and value<minimum:raise ValueError(name+' below minimum')
    return value

def evaluate(diagnostic,annotations,headings):
    """Select filtered peaks from one full-run diagnostic using half-open windows."""
    if annotations.get('schema_version')!=1 or annotations.get('time_basis')!=TIME_BASIS:
        raise ValueError('Unsupported annotation schema or time basis')
    if not isinstance(annotations.get('annotation_source'),str) or not annotations['annotation_source'].strip():
        raise ValueError('Explicit annotation source required')
    uncertainty=_number(annotations.get('time_uncertainty_s'),'time uncertainty',0)
    start=diagnostic['overlap_start_s'];end=diagnostic['overlap_end_s']
    windows={}
    for name in ('AB','turn_before','turn_after','BC'):
        w=annotations[name];left=_number(w['start_s'],name+' start');right=_number(w['end_s'],name+' end')
        if not start<=left<right<=end:raise ValueError('Window outside overlap or reversed: '+name)
        windows[name]=(left,right)
    ordered=list(windows.values())
    if any(a[1]>b[0] for a,b in zip(ordered,ordered[1:])):raise ValueError('Overlapping or unordered windows')
    expected=_number(annotations['expected_turn_deg'],'expected turn')
    if not -180<=expected<=180:raise ValueError('Expected turn outside signed half-turn')
    rows=[];previous=-math.inf
    boundaries=[v for name in ('AB','BC') for v in windows[name]]
    uncertain=[];excluded=[]
    for index,candidate in enumerate(diagnostic['step_candidates'],1):
        t=_number(candidate['time_s'],'candidate time')
        amplitude=_number(candidate['amplitude_m_s2'],'candidate amplitude',0)
        if amplitude<=0 or t<=previous:raise ValueError('Invalid candidate amplitude/order')
        previous=t;selected='excluded'
        for name in ('AB','BC'):
            if windows[name][0]<=t<windows[name][1]:selected=name
        if selected=='excluded':excluded.append(index)
        if min(abs(t-b) for b in boundaries)<=uncertainty:uncertain.append(index)
        rows.append({'candidate_index':index,'diagnostic_csv_line':index+1,'selection':selected,
            'time_s':t,'detected_at_s':candidate['detected_at_s'],'amplitude_m_s2':amplitude,
            'device_yaw_rad':candidate['device_yaw_rad']})
    def leg(name):
        distance=_number(annotations[name]['distance_m'],name+' distance',0)
        if distance<=0:raise ValueError('Positive measured distance required')
        manual=annotations[name].get('manual_steps')
        if manual is not None and (isinstance(manual,bool) or not isinstance(manual,int) or manual<0):
            raise ValueError('Manual steps must be nonnegative integer or null')
        selected=[r for r in rows if r['selection']==name]
        weights=[r['amplitude_m_s2']**.25 for r in selected]
        return {'window_s':list(windows[name]),'distance_m':distance,'manual_steps':manual,
            'candidate_count':len(selected),'candidate_indices':[r['candidate_index'] for r in selected],
            'diagnostic_csv_lines':[r['diagnostic_csv_line'] for r in selected],
            'candidate_minus_manual_steps':len(selected)-manual if manual is not None else None,
            'amplitude_quarter_power_sum':sum(weights)},weights
    calibration,weights=leg('AB');test,test_weights=leg('BC')
    if len(weights)<2:raise ValueError('Insufficient calibration candidates for leave-one sensitivity')
    total=sum(weights);distance=calibration['distance_m'];k=distance/total
    lo,hi=min(weights),max(weights)
    calibration['k']=k
    calibration['sensitivity']={'remove_one_candidate_k_range':[distance/(total-lo),distance/(total-hi)],
        'add_one_candidate_assuming_observed_weight_range':[distance/(total+hi),distance/(total+lo)],
        'assumed_added_weight_range':[lo,hi],'is_confidence_interval':False,
        'meaning':'conditional candidate-count scenarios; unknown missed-step amplitude is not bounded by observations'}
    test['predicted_length_m']=k*sum(test_weights)
    test['signed_length_error_m']=test['predicted_length_m']-test['distance_m']
    test['relative_length_error']=test['signed_length_error_m']/test['distance_m']
    previous=-math.inf
    for t,yaw in headings:
        _number(t,'heading time');_number(yaw,'heading yaw')
        if t<=previous:raise ValueError('Invalid heading order')
        previous=t
    def heading_window(name):
        left,right=windows[name];samples=[(t,y) for t,y in headings if left<=t<right]
        if not samples:raise ValueError('No heading samples in '+name)
        values=[y for t,y in samples]
        return {'window_s':[left,right],'samples':len(samples),
            'first_sample_s':samples[0][0],'last_sample_s':samples[-1][0],
            'median_unwrapped_yaw_rad':statistics.median(values),
            'yaw_range_deg':math.degrees(max(values)-min(values))}
    before=heading_window('turn_before');after=heading_window('turn_after')
    difference=math.degrees(after['median_unwrapped_yaw_rad']-before['median_unwrapped_yaw_rad'])
    def count_flag(leg):
        n=leg['candidate_minus_manual_steps'];return abs(n)<=1 if n is not None else None
    return {'schema_version':1,'status':'researcher_annotated_diagnostic_only','research_validated':False,
        'time_basis':TIME_BASIS,'annotation_source':annotations['annotation_source'],
        'time_uncertainty_s':uncertainty,'window_convention':'[start,end), using filtered peak time_s',
        'overlap_start_s':start,'overlap_end_s':end,'overlap_span_s':end-start,
        'calibration':calibration,'test':test,
        'turn':{'before':before,'after':after,'difference_deg':difference,'expected_deg':expected,
            'error_deg':difference-expected,'gyro_bias_corrected':False},
        'descriptive_flags':{'AB_count_difference_within_1':count_flag(calibration),
            'BC_count_difference_within_1':count_flag(test),'turn_error_within_15_deg':abs(difference-expected)<=15,
            'calibration_fewer_than_15_candidates':len(weights)<15,
            'meaning':'exploratory triage only, no overall scientific pass/fail'},
        'excluded_candidate_indices':excluded,'boundary_uncertain_candidate_indices':uncertain,
        'all_candidates':rows,'limits':['manual windows/reference are researcher assistance',
            'filtered peak lag is frequency-dependent; no constant time correction',
            'uncertain boundary candidates retained by fixed half-open convention',
            'AB fitted distance is not test accuracy; BC is within-session holdout only',
            'no wall inference or endpoint/continuous-trajectory accuracy claim']}

def write_evaluation(output,report,annotation_bytes):
    output=Path(output).absolute()
    if output.exists():raise FileExistsError('Output must be fresh')
    output=validated_output(output,ROOT/'output/phone-pdr')
    payload=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
    buffer=io.StringIO(newline='')
    fields=['candidate_index','diagnostic_csv_line','selection','time_s','detected_at_s','amplitude_m_s2','device_yaw_rad']
    writer=csv.DictWriter(buffer,fieldnames=fields);writer.writeheader();writer.writerows(report.get('all_candidates',[]))
    output.parent.mkdir(parents=True,exist_ok=True);output.mkdir(exist_ok=False)
    for name,data in [('evaluation.json',payload),('annotations.json',annotation_bytes),('candidate-selections.csv',buffer.getvalue().encode('utf-8'))]:
        with (output/name).open('xb') as stream:stream.write(data)
    return output

def main():
    parser=argparse.ArgumentParser(description='Researcher-annotated AB calibration and BC holdout; no hardware or layout inference')
    parser.add_argument('--session',type=Path,required=True)
    parser.add_argument('--annotations',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=validated_output(args.output,ROOT/'output/phone-pdr')
    if output.exists():raise FileExistsError('Output must be fresh')
    annotation_bytes=args.annotations.read_bytes();annotations=json.loads(annotation_bytes)
    a,g,source=load_session(args.session);diagnostic=diagnose(a,g)
    start=diagnostic['overlap_start_s'];end=diagnostic['overlap_end_s']
    aa=[r for r in a if start<=r[0]<=end];gg=[r for r in g if start<=r[0]<=end]
    report=evaluate(diagnostic,annotations,relative_yaw(aa,gg))
    def stats(rows):
        span=rows[-1][0]-rows[0][0]
        return {'rows':len(rows),'span_s':span,'event_rate_hz':(len(rows)-1)/span}
    report['full_stream_statistics']={name:diagnostic[name] for name in ('accelerometer','gyroscope')}
    report['overlap_statistics']={'accelerometer':stats(aa),'gyroscope':stats(gg)}
    report['source']=source;report['annotations_sha256']=hashlib.sha256(annotation_bytes).hexdigest()
    report['implementation_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('pdr.py'),Path(__file__).with_name('session.py')]}
    write_evaluation(output,report,annotation_bytes)
    print(json.dumps({'output':str(output),'k':report['calibration']['k'],
        'turn_difference_deg':report['turn']['difference_deg'],'research_validated':False},ensure_ascii=True))

if __name__=='__main__':main()
