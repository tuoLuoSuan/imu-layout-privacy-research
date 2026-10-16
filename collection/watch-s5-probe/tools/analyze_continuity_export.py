"""Validate 0.4.2 JS continuity observations; no hardware or external liveness claim."""
import argparse
import bisect
import json
import sys
import analyze_precise_export as previous
import decode_research_export as decoder

POLICY={'schema_version':1,'heartbeat_period_ms':1000,'tick_delay_warning_ms':1500,'silence_limit_ms':3000,
        'time_basis':'JS_callback_wall_clock','external_liveness_reference':False}

def natural(value):
    return isinstance(value,int) and not isinstance(value,bool) and value>=0

def analyze(record):
    out=previous.analyze(record);head=record['metadata'];meta=head['metadata'];tail=record['tail'];rows=record['rows']
    p=meta.get('continuity_policy');c=tail.get('continuity_observation')
    if not isinstance(p,dict) or p!=POLICY or not all(natural(p.get(k)) for k in ('schema_version','heartbeat_period_ms','tick_delay_warning_ms','silence_limit_ms')):
        raise ValueError('missing or unknown continuity policy')
    if meta.get('sensor_path')!=tail['acquisition_observation']['sensor_path']:
        raise ValueError('head / acquisition sensor path mismatch')
    if not isinstance(c,dict) or c.get('schema_version')!=1 or c.get('semantics')!='JS_wall_clock_observations_only' or c.get('external_liveness_reference') is not False:
        raise ValueError('missing or invalid continuity observation')
    started=head['started_epoch_ms'];stopped=tail['stopped_epoch_ms'];times=[r[1] for r in rows]
    if not decoder.number(started) or not decoder.number(stopped) or stopped<started:
        raise ValueError('invalid continuity epoch boundary')
    if times and (times[0]<started or times[-1]>stopped or any(b<a for a,b in zip(times,times[1:]))):
        raise ValueError('invalid continuity row boundary')
    first,last=(times[0],times[-1]) if times else (None,None)
    start_gap=(first if first is not None else stopped)-started
    terminal=stopped-(last if last is not None else started)
    maximum=max([start_gap,terminal]+[b-a for a,b in zip(times,times[1:])])
    expected={'accepted_rows':len(rows),'started_epoch_ms':started,'stopped_epoch_ms':stopped,
        'first_accepted_epoch_ms':first,'last_accepted_epoch_ms':last,'start_gap_ms':start_gap,
        'terminal_gap_ms':terminal,'max_no_accepted_gap_ms':maximum}
    if any(c.get(k)!=v or (v is not None and not decoder.number(c.get(k))) for k,v in expected.items()):
        raise ValueError('continuity summary / rows mismatch')
    if c.get('silence_observed') is not (maximum>p['silence_limit_ms']):
        raise ValueError('continuity silence summary mismatch')
    integers=['tick_count','heartbeat_count','late_tick_count']
    if not all(natural(c.get(k)) for k in integers) or not c['late_tick_count']<=c['tick_count'] or not c['heartbeat_count']<=c['tick_count']:
        raise ValueError('invalid continuity tick counts')
    tick=c.get('last_tick_epoch_ms');max_tick=c.get('max_tick_gap_ms');end_tick=c.get('terminal_tick_gap_ms')
    if not all(decoder.number(v) for v in (tick,max_tick,end_tick)) or not started<=tick<=stopped or max_tick<0 or end_tick!=stopped-tick:
        raise ValueError('invalid continuity tick timing')
    if not c['tick_count'] and (tick!=started or max_tick!=0 or c['late_tick_count']):
        raise ValueError('invented ticks before timer execution')
    events=[e for e in record['events'] if e['type']=='capture_heartbeat']
    if len(events)!=c['heartbeat_count']:
        raise ValueError('heartbeat events / summary mismatch')
    last_beat=started
    for i,e in enumerate(events,1):
        t=e['callback_epoch_ms'];detail=e.get('detail')
        if not isinstance(detail,str) or len(detail)>120:
            raise ValueError('invalid heartbeat detail')
        d=decoder.json_object(detail);n=d.get('n')
        if d.get('i')!=i or not natural(n) or n>len(rows) or t-last_beat<p['heartbeat_period_ms'] or t>tick:
            raise ValueError('invalid heartbeat order/count')
        # Same-ms callbacks may be before OR after the tick; do not invent their order.
        if not bisect.bisect_left(times,t)<=n<=bisect.bisect_right(times,t):
            raise ValueError('heartbeat accepted count / time mismatch')
        a=times[n-1] if n else None
        if d.get('a')!=a or d.get('g')!=t-(a if a is not None else started):
            raise ValueError('heartbeat last accepted row mismatch')
        last_beat=t
    derived=[]
    if maximum>p['silence_limit_ms']:derived.append('sensor_silence_observed')
    if terminal>p['silence_limit_ms'] and tail['stop_reason']=='duration':derived.append('duration_with_terminal_silence')
    if c['late_tick_count'] or end_tick>p['tick_delay_warning_ms']:derived.append('heartbeat_tick_delay')
    if tick-last_beat>=p['heartbeat_period_ms']:derived.append('heartbeat_reference_incomplete')
    out['derived_continuity_warnings']=derived
    out['warnings']=sorted(set(out['warnings']+derived))
    if out['warnings'] and out.get('session_status')=='sealed':out['session_status']='sealed_with_warnings'
    out['continuity_verification']={'summary_matches_rows_and_events':True,'heartbeat_count':len(events),
        'start_gap_ms':start_gap,'terminal_gap_ms':terminal,'max_no_accepted_gap_ms':maximum,
        'max_tick_gap_ms':max_tick,'late_tick_count':c['late_tick_count'],
        'external_liveness_reference':False,'note':'One JS loop and wall clock; cannot identify OS freeze, screen power, hardware samples or native batch loss.'}
    return out

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input');parser.add_argument('--output',required=True);args=parser.parse_args()
    try:
        record=decoder.decode_packets(decoder.scan_media([args.input]));record['report']=analyze(record);decoder.save_export(record,args.output)
    except (ValueError,OSError,KeyError,TypeError) as e:
        print(str(e),file=sys.stderr);return 2
    print(json.dumps(record['report'],ensure_ascii=True));return 0

if __name__=='__main__':sys.exit(main())
