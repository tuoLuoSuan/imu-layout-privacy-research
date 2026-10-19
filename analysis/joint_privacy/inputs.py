"""Read-only sensor inputs and explicit uncertain clock contracts. No labels."""
from dataclasses import dataclass
import hashlib,importlib.util,math
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class ClockMap:
    watch_origin_ms:float
    phone_origin_s:float
    scale:float
    span_s:float
    anchor_errors:tuple
    residual_s:float
    available_s:float
    valid_until_s:float
    drift_bound_ppm:float
    max_uncertainty_s:float

    def map_ms(self,value):return self.phone_origin_s+(float(value)-self.watch_origin_ms)/1000*self.scale

    def uncertainty_s(self,phone_s):
        # Linear interval propagation, including extrapolation: never treat two
        # hand-timed anchors as an exact slope for an arbitrarily long session.
        u=(float(phone_s)-self.phone_origin_s)/self.span_s
        endpoint=max(self.phone_origin_s,min(float(phone_s),self.phone_origin_s+self.span_s))
        return (abs(1-u)*self.anchor_errors[0]+abs(u)*self.anchor_errors[1]+
            self.residual_s+abs(float(phone_s)-endpoint)*self.drift_bound_ppm/1e6)

    def require_budget(self,budget):
        if not math.isfinite(budget) or budget<self.available_s or budget>self.valid_until_s:
            raise ValueError('Clock calibration unavailable or outside declared support')
        if self.uncertainty_s(budget)>self.max_uncertainty_s:
            raise ValueError('Clock uncertainty exceeds declared budget')

def fit_clock(value):
    required={'phone_id','watch_id','paired_session_id','mode','anchors','checks','available_s',
        'valid_until_s','drift_bound_ppm','max_uncertainty_s'}
    if not isinstance(value,dict) or set(value)!=required:raise ValueError('Explicit paired clock contract required')
    if not all(isinstance(value[k],str) and value[k] for k in ('phone_id','watch_id','paired_session_id','mode')):
        raise ValueError('Clock identity and acquisition mode required')
    anchors=value['anchors'];checks=value['checks']
    if len(anchors)!=2 or not checks:raise ValueError('Two anchors and at least one independent check required')
    for r in anchors+checks:
        if set(r)!={'watch_epoch_ms','phone_s','uncertainty_s'} or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in r.values()) or r['uncertainty_s']<=0:
            raise ValueError('Finite uncertain clock observations required')
    a,b=anchors;span=b['phone_s']-a['phone_s'];watch_span=(b['watch_epoch_ms']-a['watch_epoch_ms'])/1000
    if span<=0 or watch_span<=0:raise ValueError('Ordered independent anchors required')
    numeric=[value[k] for k in ('available_s','valid_until_s','drift_bound_ppm','max_uncertainty_s')]
    if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in numeric) or min(numeric[2:])<=0:
        raise ValueError('Finite clock bounds required')
    if value['available_s']<max(r['phone_s']+r['uncertainty_s'] for r in anchors+checks):
        raise ValueError('Calibration cannot be available before its observations')
    scale=span/watch_span
    if abs(scale-1)>value['drift_bound_ppm']/1e6+(a['uncertainty_s']+b['uncertainty_s'])/watch_span:
        raise ValueError('Clock rate/step inconsistent with declared bound')
    clock=ClockMap(a['watch_epoch_ms'],a['phone_s'],scale,span,(a['uncertainty_s'],b['uncertainty_s']),0.,*numeric)
    residual=0.
    for r in checks:
        error=abs(clock.map_ms(r['watch_epoch_ms'])-r['phone_s'])
        if error>clock.uncertainty_s(r['phone_s'])+r['uncertainty_s']:raise ValueError('Independent clock check failed')
        residual=max(residual,error)
    return ClockMap(a['watch_epoch_ms'],a['phone_s'],scale,span,(a['uncertainty_s'],b['uncertainty_s']),residual,*numeric)

def load_watch(path):
    """Reuse the frozen project's complete CRC/manifest/count validator in memory."""
    p=Path(path);data=p.read_bytes()
    module_path=ROOT/'collection/watch-s5-probe/tools/decode_research_export.py'
    spec=importlib.util.spec_from_file_location('frozen_s5_decoder',module_path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    record=module.decode_packets(data.decode('utf-8-sig').splitlines())
    return {'rows':record['rows'],'source':{'path':str(p),'sha256':hashlib.sha256(data).hexdigest(),
        'bytes':len(data),'session_id':record['session_id'],'report':record['report'],
        'recorded_start_epoch_ms':record['metadata']['started_epoch_ms'],
        'recorded_stop_epoch_ms':record['tail']['stopped_epoch_ms'] if record['tail'] else None,
        'decoder_sha256':hashlib.sha256(module_path.read_bytes()).hexdigest(),
        'units':'unvalidated native accelerometer scale','gyro_available':False,
        'timestamps':'Date.now callback arrival; not hardware sample time'}}

def watch_features(rows,budget_s,*,clock=None,window_s=1.,stride_s=.25,max_gap_s=.25):
    """Trailing norm statistics only, never a probability or body orientation.

    Without clock, milliseconds are interpreted as a synthetic relative axis.
    Real epoch inputs must be mapped with an independently checked contract.
    """
    if any(not math.isfinite(x) or x<=0 for x in (budget_s,window_s,stride_s,max_gap_s)):
        raise ValueError('Positive finite feature timing required')
    if clock:clock.require_budget(budget_s)
    data=[];previous=None
    for r in rows:
        if len(r)!=6 or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in r[:5]):raise ValueError('Invalid watch row')
        t=clock.map_ms(r[1]) if clock else r[1]/1000
        error=clock.uncertainty_s(t) if clock else 0.
        if t+error>budget_s:continue
        if previous is not None and t<=previous:raise ValueError('Repeated/regressing watch callback time')
        previous=t;data.append((t,*r[2:5],r[5],error))
    if len(data)<3:return []
    start=data[0][0];last=data[-1][0];result=[]
    for end in np.arange(start+window_s,last+1e-9,stride_s):
        selected=[r for r in data if end-window_s<=r[0]<=end]
        if len(selected)<3 or any(r[4]!='visible' for r in selected):continue
        gaps=[y[0]-x[0] for x,y in zip(selected,selected[1:])]
        if max(gaps)>max_gap_s or selected[0][0]-(end-window_s)>max_gap_s or end-selected[-1][0]>max_gap_s:continue
        magnitude=np.linalg.norm(np.asarray([r[1:4] for r in selected],dtype=float),axis=1)
        mean=float(np.mean(magnitude))
        if mean<=1e-12:continue
        error=max(r[5] for r in selected)
        result.append({'window_start_s':float(end-window_s),'window_end_s':float(end),
            'available_s':float(end+error),'sample_count':len(selected),'max_gap_s':float(max(gaps)),
            'clock_uncertainty_s':float(error),'norm_cv':float(np.std(magnitude)/mean),
            'norm_range_over_mean':float(np.ptp(magnitude)/mean),
            'norm_diff_rms_over_mean':float(np.sqrt(np.mean(np.diff(magnitude)**2))/mean),
            'quantity':'unitless trailing motion features; not calibrated walk probabilities'})
    return result
