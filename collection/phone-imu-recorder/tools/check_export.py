"""Independent, offline export validator. Never changes the input ZIP."""
import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import sys
import zipfile
from pathlib import Path

S = 1_000_000_000


def distribution(values):
    if not values:
        return dict(count=0, min_ns=None, median_ns=None, p95_ns=None, max_ns=None)
    ordered = sorted(values)
    k = (len(ordered)-1)*.95
    i = int(k)
    p95 = ordered[i]+(ordered[min(i+1,len(ordered)-1)]-ordered[i])*(k-i)
    return dict(count=len(values), min_ns=min(values), median_ns=statistics.median(values), p95_ns=p95, max_ns=max(values))


def verify(path):
    failures, unknown, warnings = [], [], []
    result = dict(format_version=1, validator="independent_python_v1", input_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                  failures=failures, unknown=unknown, warnings=warnings, channels=[])
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(set(names)) != len(names) or any('/' in n or '\\' in n or n in ('.','..') for n in names):
            raise ValueError("duplicate or unsafe ZIP entry")
        if sum(i.file_size for i in z.infolist()) > 512*1024*1024:
            raise ValueError("export exceeds first-version size budget")
        if z.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        manifest=json.loads(z.read('manifest.json'))
        meta=json.loads(z.read('metadata.json'))
        app=json.loads(z.read('integrity_report.json'))
        if manifest.get('format_version') != 1 or meta.get('format_version') != 1:
            raise ValueError("unsupported format_version")
        entries=manifest['files']
        if len({e['path'] for e in entries}) != len(entries) or 'manifest.json' in {e['path'] for e in entries}:
            raise ValueError("manifest must exclude itself and have unique paths")
        if set(names) != {e['path'] for e in entries}|{'manifest.json'}:
            failures.append('manifest_file_set_mismatch')
        for entry in entries:
            b=z.read(entry['path'])
            if len(b) != entry['bytes'] or hashlib.sha256(b).hexdigest() != entry['sha256']:
                failures.append('checksum_mismatch:'+entry['path'])
            if 'rows' in entry and max(0,len(b.decode('utf-8').splitlines())-1) != entry['rows']:
                failures.append('manifest_row_count:'+entry['path'])
        if meta.get('completion_state') != 'complete' or meta.get('visibility_condition_failed'):
            failures.append('completion_or_visibility_failed')
        start, end = int(meta.get('collection_start_elapsed_ns',0)), int(meta.get('stop_elapsed_ns',0))
        states=meta.get('states',[])
        if any(b['elapsed_ns'] < a['elapsed_ns'] for a,b in zip(states,states[1:])):
            failures.append('state_time_regression')
        baseline_ok_all=True
        for channel_index,name in enumerate(('accelerometer','gyroscope')):
            raw=list(csv.DictReader(io.StringIO(z.read(name+'.csv').decode('utf-8'))))
            values=[]
            for line,row in enumerate(raw,2):
                try:
                    if None in row or any(v is None for v in row.values()):
                        raise ValueError('incomplete row')
                    numeric={k:int(row[k]) for k in ('sequence','sensor_timestamp_ns','received_elapsed_realtime_ns','writer_dequeued_elapsed_realtime_ns','accuracy')}
                    if not all(math.isfinite(float(row[k])) for k in ('x','y','z')):
                        raise ValueError('non-finite sensor value')
                    values.append(numeric)
                except (ValueError,KeyError,TypeError):
                    failures.append(f'parse_error:{name}:{line}')
            events=[v['sensor_timestamp_ns'] for v in values]
            delivery=[v['received_elapsed_realtime_ns'] for v in values]
            if [v['sequence'] for v in values] != list(range(1,len(values)+1)):
                failures.append('sequence_count:'+name)
            for key in ('received','enqueued','written','confirmed'):
                if meta.get(key,[-1,-1])[channel_index] != len(values):
                    failures.append(f'count:{name}:{key}')
            if meta.get('dropped',[-1,-1])[channel_index] != 0:
                failures.append('dropped:'+name)
            if any(v['writer_dequeued_elapsed_realtime_ns'] < v['received_elapsed_realtime_ns'] for v in values):
                failures.append('queue_clock_regression:'+name)
            item=dict(name=name,rows=len(values))
            for kind,times in (('event',events),('delivery',delivery)):
                intervals=[b-a for a,b in zip(times,times[1:])]
                gaps=[dict(after_row=i+1,interval_ns=d) for i,d in enumerate(intervals) if d>100_000_000]
                if not intervals or any(d<0 or (d==0 and kind=='event') for d in intervals):
                    failures.append(f'{kind}_time_invalid:{name}')
                if any(d>S for d in intervals):
                    failures.append(f'over_1s:{name}:{kind}')
                if gaps:
                    warnings.append(dict(channel=name,kind=kind,type='over_100ms',count=len(gaps),max_ns=max(x['interval_ns'] for x in gaps)))
                item[kind+'_intervals']=dict(**distribution([d for d in intervals if d>0]),over_100ms=gaps)
            if not events or events[0]<start or events[0]-start>S or events[-1]>end or end-events[-1]>S:
                failures.append('event_edge_gap:'+name)
            baseline=[t for t in events if start+2*S<=t<start+60*S]
            base_deltas=[b-a for a,b in zip(baseline,baseline[1:])]
            state_at_start='unknown'
            for state in states:
                if state['elapsed_ns']<=start+2*S:
                    state_at_start=state['state']
            foreground=state_at_start=='foreground' and not any(start+2*S<x['elapsed_ns']<start+60*S and x['state']!='foreground' for x in states)
            valid=bool(baseline) and sum(d>0 for d in base_deltas)>=1000 and all(0<d<=S for d in base_deltas) and foreground and end>=start+60*S
            if baseline:
                valid=valid and baseline[0]-(start+2*S)<=S and start+60*S-baseline[-1]<=S
            median=statistics.median([d for d in base_deltas if d>0]) if any(d>0 for d in base_deltas) else None
            item['baseline']=dict(valid=valid,samples=len(baseline),positive_intervals=sum(d>0 for d in base_deltas),median_ns=median,window=[start+2*S,start+60*S])
            if not valid:
                unknown.append('baseline_invalid:'+name)
                baseline_ok_all=False
            for index,state in enumerate(states):
                lo=max(start,state['elapsed_ns'])
                hi=min(end,states[index+1]['elapsed_ns'] if index+1<len(states) else end)
                ds=[b-a for a,b in zip(events,events[1:]) if lo<=a and b<hi and b>a]
                if hi-lo>=S:
                    if len(ds)<10 or median is None:
                        unknown.append('state_stability_insufficient:'+name+':'+state['state'])
                    elif not median*.8 <= statistics.median(ds) <= median*1.2:
                        failures.append('state_stability:'+name+':'+state['state'])
            result['channels'].append(item)
            app_channels=app.get('channels',[])
            if channel_index<len(app_channels):
                a=app_channels[channel_index]
                if a.get('rows')!=len(values) or a.get('baseline',{}).get('median_ns')!=median:
                    failures.append('app_report_numeric_mismatch:'+name)
            else:
                unknown.append('app_report_fields_missing:'+name)
        anchors=[]
        for a in csv.DictReader(io.StringIO(z.read('anchors.csv').decode('utf-8'))):
            try:
                before,wall,after=(int(a[k]) for k in ('elapsed_before_ns','wall_ms','elapsed_after_ns'))
                anchors.append((before+(after-before)//2,wall,0<after-before<=5_000_000))
            except (KeyError,ValueError,TypeError):
                anchors.append((0,0,False))
        mapped=[]
        for a,b in zip(anchors,anchors[1:]):
            delta=b[0]-a[0]
            if a[2] and b[2] and 0<delta<=15*S and abs((b[1]-a[1])*1_000_000-delta)<=100_000_000:
                lo,hi=max(start,a[0]),min(end,b[0])
                if hi>lo:mapped.append([lo,hi])
        unmapped=[]
        cursor=start
        for lo,hi in mapped:
            if lo<cursor:
                failures.append('anchor_mapping_regression');continue
            if lo>cursor:unmapped.append([cursor,lo])
            cursor=hi
        if cursor<end:unmapped.append([cursor,end])
        result.update(session_id=meta.get('session_id'),valid_mapping_intervals=mapped,unmapped_intervals=unmapped,
                      utc_mapping='unavailable' if not mapped else 'partial' if unmapped else 'complete',
                      baseline_valid=baseline_ok_all,external_observation='requires_independent_review',
                      overall='fail' if failures else 'pending_external_review')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zip',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    try:
        report=verify(args.zip)
    except Exception as e:
        report=dict(overall='invalid_input',error=f'{type(e).__name__}: {e}')
        code=2
    else:
        code=1 if report['failures'] else 2
    (args.output/'independent_integrity.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('overall','failures','unknown','warnings','error') if k in report},ensure_ascii=False))
    print('退出码 2 可表示尚需外部审查；不自动宣称整体验收通过。')
    return code


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
