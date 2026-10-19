"""Evaluation-side timing support and clock planning, never verified clocks.

No raw IMU, model prediction, geometry or activity inference is read here.
The caller's time/error/identity declarations remain assumptions. This tool
does not create reference.json or convert unknown intervals into nonwalking.
"""
import argparse,itertools,json,math
from pathlib import Path
from .inputs import fit_clock
from .output import write_json


def _keys(value,required):
    if not isinstance(value,dict) or set(value)!=set(required):
        raise ValueError('Exact timing schema required: '+', '.join(sorted(required)))


def _number(value,*,minimum=None,positive=False):
    if isinstance(value,bool):raise ValueError('Boolean values are not times')
    if not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Finite numeric seconds required')
    if (minimum is not None and value<minimum) or (positive and value<=0):
        raise ValueError('Timing value outside allowed range')
    return float(value)


def _version(value):
    if type(value) is not int or value!=1:raise ValueError('Timing schema version 1 required')


def _text(value):
    if not isinstance(value,str) or not value.strip():raise ValueError('Explicit nonempty identity required')


def map_reference(document):
    """Propagate two uncertain source anchors into an exact target clock axis.

    Extrema are evaluated at corners of the declared rectangular uncertainty
    set, with disjoint ordered anchor intervals. Duration corners share the
    same clock mapping; the common intersection is a separate, stricter policy.
    """
    _keys(document,{'schema_version','time_unit','source_id','target_id','anchors',
                    'target_support_s','target_window_s','intervals'})
    _version(document['schema_version'])
    if document['time_unit']!='seconds':raise ValueError('Use seconds explicitly')
    for key in ('source_id','target_id'):_text(document[key])
    support=document['target_support_s']
    if not isinstance(support,list) or len(support)!=2:raise ValueError('Recorded target support required')
    lo,hi=map(_number,support)
    if not lo<hi:raise ValueError('Ordered recorded target support required')
    window=_number(document['target_window_s'],positive=True)
    anchors=document['anchors']
    if not isinstance(anchors,list) or len(anchors)!=2:raise ValueError('Exactly two anchors required')
    parsed=[]
    for anchor in anchors:
        _keys(anchor,{'source_s','source_error_s','target_s'})
        center=_number(anchor['source_s']);error=_number(anchor['source_error_s'],minimum=0.)
        target=_number(anchor['target_s'])
        if not lo<=target<=hi:raise ValueError('Target anchor outside recorded support')
        parsed.append((center-error,center+error,target,center))
    a,b=parsed;span=b[2]-a[2]
    if not math.isfinite(span) or span<=0:
        raise ValueError('Target anchor times must be strictly increasing')
    if not a[1]<b[0]:
        raise ValueError('Source anchor uncertainty intervals must be disjoint and ordered')
    corners=list(itertools.product(a[:2],b[:2]))
    def mapped(t,x,y):return _number(a[2]+(t-x)/(y-x)*span)
    intervals=document['intervals'];seen=set();rows=[]
    if not isinstance(intervals,list) or not intervals:raise ValueError('Explicit local intervals required')
    for item in intervals:
        _keys(item,{'id','activity','start_s','end_s','start_error_s','end_error_s'})
        _text(item['id'])
        if item['id'] in seen:raise ValueError('Duplicate interval identity')
        seen.add(item['id'])
        if item['activity'] not in ('walk','nonwalk','unknown'):raise ValueError('Explicit walk/nonwalk/unknown required')
        start=_number(item['start_s']);end=_number(item['end_s'])
        se=_number(item['start_error_s'],minimum=0.);ee=_number(item['end_error_s'],minimum=0.)
        if start>=end:raise ValueError('Nominal interval must be ordered')
        starts=[mapped(t,x,y) for t,x,y in itertools.product((start-se,start+se),a[:2],b[:2])]
        ends=[mapped(t,x,y) for t,x,y in itertools.product((end-ee,end+ee),a[:2],b[:2])]
        sb=[min(starts),max(starts)];eb=[min(ends),max(ends)]
        durations=[mapped(v,x,y)-mapped(u,x,y)
                   for x,y in corners for u,v in itertools.product((start-se,start+se),(end-ee,end+ee))]
        width=max(0.,eb[0]-sb[1]);common=[sb[1],eb[0]] if width>0 else None
        inside=lo<=min(sb+eb) and max(sb+eb)<=hi
        if item['activity']=='unknown':status='unknown_activity'
        elif start+se>=end-ee:status='ambiguous_interval_order'
        elif not inside:status='outside_target_support'
        elif width<window:status='insufficient_common_support'
        else:status='local_windows_supported_under_assumptions'
        fits=status=='local_windows_supported_under_assumptions'
        rows.append({'id':item['id'],'activity':item['activity'],'status':status,
            'start_phone_nominal_s':mapped(start,a[3],b[3]),'end_phone_nominal_s':mapped(end,a[3],b[3]),
            'start_phone_envelope_s':sb,'end_phone_envelope_s':eb,
            'correlated_duration_range_s':[min(durations),max(durations)],
            'common_interior_s':common,'common_interior_duration_s':width,
            'full_envelopes_inside_target_support':inside,'fits_target_window':fits,
            'admissible_target_end_s':[common[0]+window,common[1]] if fits else None})
    return {'schema_version':1,'status':'timing_support_diagnostic_only','time_unit':'seconds',
        'source_id':document['source_id'],'target_id':document['target_id'],
        'target_support_s':[lo,hi],'target_window_s':window,'intervals':rows,
        'clock_verified':False,'research_validated':False,'reference_generated':False,
        'admission_policy':'intersection common to all declared timing corners; insufficiency is not impossibility of every uncertainty-aware evaluation',
        'identity_and_error_bounds_authenticated':False,
        'limits':['Error intervals and affine clock relation are caller assumptions, not physical calibration.',
                  'Shared-mapping duration is distinct from the common intersection.',
                  'No claim of continuous label coverage between separate intervals.']}


def plan_clock(document):
    """Preflight available-time/uncertainty requirements using existing math."""
    _keys(document,{'schema_version','clock_contract','budgets_s','threshold_s'})
    _version(document['schema_version'])
    threshold=_number(document['threshold_s'],positive=True)
    budgets=document['budgets_s']
    if not isinstance(budgets,list) or not budgets:raise ValueError('Explicit positive budgets required')
    budgets=[_number(v,positive=True) for v in budgets]
    if len(set(budgets))!=len(budgets):raise ValueError('Duplicate budget')
    clock=fit_clock(document['clock_contract']);rows=[]
    for budget in budgets:
        error=clock.uncertainty_s(budget)
        if budget<clock.available_s:reason='calibration_not_available'
        elif budget>clock.valid_until_s:reason='outside_declared_clock_support'
        elif error>clock.max_uncertainty_s:reason='contract_uncertainty_exceeded'
        elif error>=threshold:reason='strict_threshold_not_met'
        else:reason=None
        rows.append({'budget_s':budget,'uncertainty_s':error,'accepted':reason is None,'reason':reason})
    return {'schema_version':1,'status':'plan_pass_under_assumptions' if all(r['accepted'] for r in rows) else 'plan_rejected',
        'threshold_s':threshold,'comparison':'strictly less than threshold',
        'budgets':rows,'calibration_available_s':clock.available_s,
        'clock_verified':False,'hardware_verified':False,'research_validated':False,
        'limits':'A mathematical plan pass is not an actual recording, clock acceptance or bound validation.'}


def _unique_pairs(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('Duplicate JSON key: '+k)
        result[k]=v
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('map','clock-plan'));parser.add_argument('input',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    value=json.loads(args.input.read_text(encoding='utf-8-sig'),object_pairs_hook=_unique_pairs,
                     parse_constant=lambda v:(_ for _ in ()).throw(ValueError('Nonfinite JSON value: '+v)))
    result=(map_reference if args.mode=='map' else plan_clock)(value)
    write_json(args.output,result)
    print(json.dumps({'status':result['status'],'output':str(args.output)},ensure_ascii=False))


if __name__=='__main__':main()
