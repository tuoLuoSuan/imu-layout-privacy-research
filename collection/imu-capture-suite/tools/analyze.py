"""Read-only same-session linkage diagnostics. Never creates a physical clock contract."""
import argparse,csv,hashlib,io,json,math,tempfile,zipfile,zlib
from pathlib import Path

def pairs(items):
    out={}
    for k,v in items:
        if k in out:raise ValueError('duplicate JSON key: '+k)
        out[k]=v
    return out
def load(blob):
    def reject(v):raise ValueError('non-finite JSON constant: '+v)
    return json.loads(blob,object_pairs_hook=pairs,parse_constant=reject)
def integer(v,key):
    x=v.get(key)
    if type(x)is not int or x<0:raise ValueError('nonnegative integer required: '+key)
    return x
def insist(ok,reason):
    if not ok:raise ValueError(reason)
def constant_intersection(rows,key):
    if not rows:return None
    lo=max(r[key][0] for r in rows);hi=min(r[key][1] for r in rows)
    return [lo,hi]if lo<=hi else None
def analyze(native_zip,plugin_jsonl):
    native_zip=Path(native_zip);plugin_jsonl=Path(plugin_jsonl)
    with zipfile.ZipFile(native_zip)as z:
        names=z.namelist();insist(len(names)==len(set(names)),'duplicate ZIP entries')
        insist(all('/'not in n and '\\'not in n and n not in ['.','..']for n in names),'unsafe ZIP path')
        insist(sum(i.file_size for i in z.infolist())<=134217728,'ZIP too large for bounded probe')
        insist(z.testzip()is None,'ZIP CRC failure');manifest=load(z.read('manifest.json'));entries=manifest['files']
        insist(len({e['path']for e in entries})==len(entries),'duplicate manifest entry')
        insist(set(names)=={e['path']for e in entries}|{'manifest.json'},'ZIP/manifest entries mismatch')
        blobs={}
        for e in entries:
            b=z.read(e['path']);insist(len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256'],'manifest mismatch: '+e['path']);blobs[e['path']]=b
    meta=load(blobs['metadata.json']);sid=meta['session_id'];insist(meta.get('joint_probe')is True,'not a joint native candidate session')
    events=[load(line)for line in blobs['events.jsonl'].decode('utf-8').splitlines()if line.strip()]
    logs=[load(line)for line in plugin_jsonl.read_text(encoding='utf-8').splitlines()if line.strip()]
    insist(logs and logs[0]['kind']=='header'and logs[0]['format']=='imu_joint_bridge_v1'and logs[0]['native_sid']==sid,'foreign plugin/native session')
    insist(logs[0].get('physical_clock_accepted')is False,'invalid acceptance flag')
    native_rows=[]
    for channel in ['accelerometer','gyroscope']:
        values=list(csv.DictReader(io.StringIO(blobs[channel+'.csv'].decode('utf-8'))));native_rows.append(len(values))
    insist(native_rows==meta['received']==meta['confirmed'],'native accepted/persisted CSV counts mismatch')
    insist(meta.get('dropped')==[0,0],'native dropped rows: inspect partial files')
    plugin_native={};watch_requests={};native_intervals=[];watch_intervals=[];watch_sid=None;rows=[];block_index=0;end=None;failure=None
    for v in logs[1:]:
        k=v['kind']
        if k=='native_request':
            r,p=v['request'],v['reply'];q=integer(r,'seq');insist(r['sid']==sid and p['sid']==sid,'native sid mismatch')
            insist(q not in plugin_native,'duplicate native request');insist(p['seq']==q and p['nonce']==r['nonce'] and p['n1_ns']==r['n1_ns'],'plugin native echo mismatch');plugin_native[q]=(r,p)
        elif k=='watch_hello':
            h,p=v['request'],v['reply'];insist(p['native_sid']==sid and p['sid']==h['sid'],'watch hello mismatch')
            insist(watch_sid in [None,h['sid']],'multiple watch sessions');watch_sid=h['sid']
        elif k=='watch_clock_request':
            r,p=v['request'],v['reply'];q=integer(r,'seq');insist(q not in watch_requests,'duplicate watch clock request');insist(r['sid']==watch_sid and r['native_sid']==sid,'foreign watch clock');
            insist(all(p[t]==r[t]for t in ['sid','native_sid','seq','w1_ms']),'watch request echo mismatch');watch_requests[q]=(r,p)
        elif k=='watch_clock_observation':
            o=v['observation'];q=integer(o,'seq');insist(q in watch_requests,'unbound watch observation');r,p=watch_requests[q]
            insist(all(o[t]==p[t]for t in ['sid','native_sid','seq','w1_ms','p2_us','p3_us']),'watch timestamp echo mismatch')
            w1,w4,p2,p3=[integer(o,t)for t in ['w1_ms','w4_ms','p2_us','p3_us']];insist(w4>=w1 and w4-w1<=5000 and p3>=p2,'watch clock order/timeout')
            raw=[p3-w4*1000,p2-w1*1000]
            watch_intervals.append({'seq':q,'watch_request_ms':w1,'watch_reply_ms':w4,'plugin_minus_watch_us_raw':raw,'available_native_ns':None})
        elif k=='watch_data':
            p=v['packet'];insist(p['sid']==watch_sid and p['native_sid']==sid and integer(p,'index')==block_index,'data identity/order mismatch');payload=p['payload'].encode('utf-8')
            insist(f'{zlib.crc32(payload):08x}'==p['crc32'],'watch CRC mismatch');part=load(payload);insist(isinstance(part,list)and 0<len(part)<=32,'watch block size')
            for r in part:
                insist(isinstance(r,list)and len(r)==5 and type(r[0])is int and r[0]==len(rows),'watch sample sequence')
                insist(type(r[1])is int and r[1]>=1000000000000 and(not rows or r[1]>rows[-1][1]),'watch time duplicate/reversal')
                insist(all(type(x)in [float,int]and math.isfinite(x)for x in r[2:]),'watch XYZ invalid');rows.append(r)
            block_index+=1
        elif k=='watch_data_duplicate':
            p=v['packet'];i=integer(p,'index');insist(i<block_index,'unbound duplicate block')
            original=[x['packet']for x in logs if x['kind']=='watch_data'and x['packet']['index']==i];insist(len(original)==1 and original[0]==p,'conflicting duplicate')
        elif k=='watch_end':
            insist(failure is None,'end after failure');insist(end in [None,v['packet']],'conflicting end');end=v['packet']
        elif k=='watch_failure':
            p=v['packet'];insist(end is None,'failure after end');insist(failure in [None,p],'conflicting failure')
            insist(p.get('sid')==watch_sid and p.get('native_sid')==sid,'failure identity mismatch')
            insist(p.get('stop_reason')=='failure' and isinstance(p.get('stage'),str) and 0<len(p['stage'])<=32,'failure stage invalid')
            insist(isinstance(p.get('error'),str) and 0<len(p['error'])<=240,'failure message invalid')
            insist(integer(p,'count')>=len(rows) and integer(p,'blocks')>=block_index,'failure counts regressed')
            failure=p
        elif k=='watch_failure_duplicate':
            insist(failure==v['packet'],'unbound failure duplicate')
        else:raise ValueError('unknown plugin journal kind: '+str(k))
    insist([r['seq']for r in watch_intervals]==list(range(len(watch_intervals))),'watch observation sequence')
    native_events=[e for e in events if e.get('type')=='joint_native_exchange']
    for seq,e in enumerate(native_events):
        d=e['details'];r,p=d['request'],d['reply'];insist(integer(r,'seq')==seq and seq in plugin_native,'unbound native response');pr,pp=plugin_native[seq]
        insist(r==pr and p==pp,'native/plugin request or response mismatch')
        n1,n4,p2,p3=integer(d,'n1_ns'),integer(d,'n4_ns'),integer(p,'p2_us'),integer(p,'p3_us');insist(n1==r['n1_ns']and n4>=n1 and p3>=p2,'native time order')
        low,high=n1-p2*1000,n4-p3*1000;insist(low<=high,'native negative causal interval')
        native_intervals.append({'seq':seq,'n1_ns':n1,'n4_ns':n4,'plugin_request_us':p2,'plugin_reply_us':p3,'native_minus_plugin_ns_raw':[low,high],'raw_width_ms':(high-low)/1000000,'observed_watch_clock_count':p.get('watch_clock_observations',0)})
    for w in watch_intervals:
        candidates=[n['n4_ns']for n in native_intervals if n['observed_watch_clock_count']>=w['seq']+1]
        w['available_native_ns']=min(candidates)if candidates else None
    if end is not None:
        insist(end['native_sid']==sid and end['sid']==watch_sid,'foreign end')
        insist(integer(end,'count')==len(rows)and integer(end,'blocks')==block_index and integer(end,'clock_observations')==len(watch_intervals),'watch end counts mismatch')
        start,stop=integer(end,'start_ms'),integer(end,'stop_ms');insist(stop>=start and all(start<=r[1]<=stop for r in rows),'watch samples outside recording support')
        insist(end['acquisition'].get('accepted_rows')==len(rows),'watch acquisition accepted count mismatch')
    if failure is not None:
        insist(failure['native_sid']==sid and failure['sid']==watch_sid,'foreign failure')
        reported_rows,reported_blocks=integer(failure,'count'),integer(failure,'blocks')
        insist(len(rows)<=reported_rows<=20000 and block_index<=reported_blocks<=reported_rows,'failure counts mismatch')
        start,stop=integer(failure,'start_ms'),integer(failure,'stop_ms');insist(stop>=start and all(start<=r[1]<=stop for r in rows),'watch samples outside failure support')
    gaps=[b[1]-a[1]for a,b in zip(rows,rows[1:])]
    beacon=[e['details']for e in events if e.get('type')=='joint_beacon_draw']
    status='same_session_transport_failed_partial'if failure is not None else('same_session_transport_complete_probe_only'if end is not None else'partial_probe_only')
    return {
        'schema_version':1,'status':status,
        'native_sid':sid,'watch_sid':watch_sid,'native_rows':native_rows,'watch_rows':len(rows),'watch_blocks':block_index,
        'watch_failed':failure is not None,'watch_failure_stage':None if failure is None else failure['stage'],
        'watch_failure_message':None if failure is None else failure['error'],
        'watch_failure_reported_rows':None if failure is None else integer(failure,'count'),
        'watch_failure_reported_blocks':None if failure is None else integer(failure,'blocks'),
        'watch_local_persisted_rows':None,
        'failure_count_semantics':'watch_rows/blocks are received records; failure-reported counts are local accepted/queued counts, not verified local persistence',
        'watch_end_reason':None if end is None else end['stop_reason'],'watch_max_callback_gap_ms':max(gaps)if gaps else None,
        'last_sample_shares_recorded_stop_ms':bool(rows and end is not None and rows[-1][1]==end['stop_ms']),
        'stop_tie_semantics':'ordered callbacks may share one quantized Date.now millisecond; retained, not a physical half-open boundary claim',
        'native_exchanges':len(native_intervals),'watch_exchanges':len(watch_intervals),
        'native_clock_intervals':native_intervals,'watch_clock_intervals':watch_intervals,
        'native_constant_offset_intersection_ns_raw':constant_intersection(native_intervals,'native_minus_plugin_ns_raw'),
        'watch_constant_offset_intersection_us_raw':constant_intersection(watch_intervals,'plugin_minus_watch_us_raw'),
        'intersection_semantics':'constant-offset hypothesis compatibility using reported timestamp values, not calibrated physical precision or a drift bound',
        'unmatched_native_plugin_requests':sorted(set(plugin_native)-{n['seq']for n in native_intervals}),
        'visual_codes':beacon,'visual_code_semantics':'native draw request interval only; physical display and camera latency unverified',
        'video_to_native_mapping':None,'physical_clock_accepted':False,'future_projection':None,
        'reference_created':False,'oracle_ready':False,'joint_result':False,'research_validated':False,
        'input_sha256':{'native_zip':hashlib.sha256(native_zip.read_bytes()).hexdigest(),'plugin_jsonl':hashlib.sha256(plugin_jsonl.read_bytes()).hexdigest()},
    }
def analyze_bundle(path):
    path=Path(path)
    with zipfile.ZipFile(path)as z:
        names=z.namelist();insist(len(names)==len(set(names)),'duplicate bundle entry')
        insist(sum(x.file_size for x in z.infolist())<=67_108_864,'bundle too large')
        insist(z.testzip()is None,'bundle CRC failure')
        manifest=load(z.read('bundle-manifest.json'))
        insist(manifest.get('kind')=='imu_capture_bundle_v1'and manifest.get('schema_version')==1,'unsupported bundle')
        included=manifest.get('watch_included');insist(type(included)is bool,'invalid watch inclusion')
        expected={'phone.zip','watch.jsonl'}if included else{'phone.zip'}
        insist(set(names)==expected|{'bundle-manifest.json'},'unexpected bundle members')
        entries=manifest['files'];insist(len(entries)==len(expected)and{v['path']for v in entries}==expected,'bundle manifest mismatch')
        data={}
        for v in entries:
            b=z.read(v['path']);insist(len(b)==v['bytes']and hashlib.sha256(b).hexdigest()==v['sha256'],'bundle checksum mismatch');data[v['path']]=b
    with zipfile.ZipFile(io.BytesIO(data['phone.zip']))as pz:
        native=load(pz.read('metadata.json'));insist(native['session_id']==manifest['native_sid'],'bundle/native session mismatch')
    if not included:return {'status':'phone_only_export_missing_watch_log','native_sid':native['session_id'],'native_rows':native.get('received'),'watch_rows':None,'watch_export_error':manifest.get('watch_export_error'),'physical_clock_accepted':False,'reference_created':False,'oracle_ready':False,'joint_result':False}
    with tempfile.TemporaryDirectory(prefix='imu-bundle-reader-')as tmp:
        n=Path(tmp)/'phone.zip';w=Path(tmp)/'watch.jsonl';n.write_bytes(data['phone.zip']);w.write_bytes(data['watch.jsonl']);result=analyze(n,w)
    result['bundle_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('native_zip',type=Path);p.add_argument('plugin_jsonl',type=Path,nargs='?');p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    insist(not a.output.exists(),'output already exists');result=analyze(a.native_zip,a.plugin_jsonl)if a.plugin_jsonl else analyze_bundle(a.native_zip)
    with a.output.open('x',encoding='utf-8')as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'status':result['status'],'native_rows':result['native_rows'],'watch_rows':result['watch_rows'],'physical_clock_accepted':False}))
if __name__=='__main__':main()
