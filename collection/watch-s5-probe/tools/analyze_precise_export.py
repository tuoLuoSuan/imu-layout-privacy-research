"""Check 0.4.1 acquisition observations after unchanged schema2 transport validation."""
import argparse
import json
import sys
import decode_research_export as decoder
import analyze_input_export as base


def analyze(record):
    meta=record['metadata']['metadata'];rows=record['rows'];tail=record['tail']
    if meta.get('record_purpose')!='recording':
        raise ValueError('not a formal recording')
    r=tail.get('acquisition_observation') if tail else None
    if not isinstance(r,dict) or r.get('schema_version')!=1:
        raise ValueError('missing acquisition observation')
    mode=r.get('sensor_path')
    expected={'generic':('@system.sensor.subscribe',['high','mid','low']),
              'legacy':('@system.sensor.subscribeAccelerometer',['game','ui','normal'])}.get(mode)
    if expected is None or r.get('api')!=expected[0] or meta.get('acquisition_api')!=expected[0] or r.get('requested_interval')!=meta.get('requested_interval') or r['requested_interval'] not in expected[1]:
        raise ValueError('API / requested interval mismatch')
    counts=[r.get(k) for k in ('accepted_rows','valid_xyz_callbacks','callback_count','fractional_xyz_scalars')]
    if any(isinstance(n,bool) or not isinstance(n,int) or n<0 for n in counts) or not counts[0]<=counts[1]<=counts[2] or counts[0]!=len(rows):
        raise ValueError('acquisition counters mismatch')
    fractional=sum(v!=int(v) for row in rows for v in row[2:5])
    if counts[3]!=fractional:
        raise ValueError('fractional scalar count mismatch')
    if len(json.dumps(r,ensure_ascii=True,separators=(',',':')))>32768:
        raise ValueError('acquisition report exceeds boundary')
    if rows:
        for name,row in [('first',rows[0]),('last',rows[-1])]:
            text=r.get(name+'_callback_json')
            if not isinstance(text,str) or base.ascii_units(text)>2048:
                raise ValueError('missing or oversized callback snapshot')
            raw=decoder.json_object(text);p=raw.get('ACCELEROMETER') if mode=='generic' else raw
            if not isinstance(p,dict) or not all(decoder.number(p.get(k)) for k in ('x','y','z')) or [p[k] for k in ('x','y','z')]!=row[2:5] or r.get(name+'_accepted_callback_epoch_ms')!=row[1]:
                raise ValueError('raw callback snapshot / row mapping mismatch')
    elif r.get('first_callback_json') is not None or r.get('last_callback_json') is not None:
        raise ValueError('unexpected accepted callback snapshot for empty recording')
    out=base.analyze(record);cleanup=r.get('cleanup',{}).get('status')
    out['derived_acquisition_warnings']=[]
    if cleanup!='unsubscribe_returned':
        out['derived_acquisition_warnings'].append('acquisition_cleanup_not_confirmed')
        out['warnings']=sorted(set(out['warnings']+['acquisition_cleanup_not_confirmed']))
        if out.get('session_status')=='sealed':out['session_status']='sealed_with_warnings'
    out['recording_observation']={'sensor_path':mode,'api':r['api'],'requested_interval':r['requested_interval'],
        'accepted_rows':len(rows),'callback_count':counts[2],'fractional_xyz_scalars':fractional,
        'distinct_xyz':len({tuple(row[2:5]) for row in rows}),'cleanup_status':cleanup,
        'unsubscribe_return_observed':cleanup=='unsubscribe_returned','hardware_time_verified':False,
        'unit_verified':False,'axis_verified':False,'cross_device_sync_verified':False,
        'note':'Only JS callback observations; no hardware-rate, native batch-completeness or physical screen-state claim.'}
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input');parser.add_argument('--output',required=True);args=parser.parse_args()
    try:
        record=decoder.decode_packets(decoder.scan_media([args.input]));record['report']=analyze(record);decoder.save_export(record,args.output)
    except (ValueError,OSError,KeyError,TypeError) as e:
        print(str(e),file=sys.stderr);return 2
    print(json.dumps(record['report'],ensure_ascii=True));return 0


if __name__=='__main__':sys.exit(main())
