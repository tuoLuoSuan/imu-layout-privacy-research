import hashlib,importlib.util,json,tempfile,unittest,zipfile,zlib
from pathlib import Path
MODULE=Path(__file__).resolve().parents[1]/'tools/analyze.py'
spec=importlib.util.spec_from_file_location('joint_bridge_analyzer',MODULE);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
P=1792300000000000;W=P//1000
def fixture(directory):
    sid='native-session';watch='watch-session';events=[];log=[{'kind':'header','schema_version':1,'format':'imu_joint_bridge_v1','native_sid':sid,'watch_package':'org.imuresearch.s5joint','physical_clock_accepted':False}]
    for seq in range(2):
        n1=10000000000+seq*1000000000;n4=n1+2000000;p2=P+seq*1000000+1000;p3=p2+100
        req={'kind':'native_clock_req','sid':sid,'seq':seq,'nonce':f'nonce-{seq}','n1_ns':n1}
        rep={'kind':'native_clock_reply','sid':sid,'seq':seq,'nonce':f'nonce-{seq}','n1_ns':n1,'p2_us':p2,'p3_us':p3,'watch_sid':None if seq==0 else watch,'watch_rows':0,'watch_clock_observations':seq,'watch_finished':False,'watch_stop_reason':None,'physical_clock_accepted':False}
        log.append({'kind':'native_request','request':req,'reply':rep});events.append({'elapsed_ns':n4,'type':'joint_native_exchange','details':{'request':req,'reply':rep,'n1_ns':n1,'n4_ns':n4}})
    hello={'p':'J_HELLO1','sid':watch,'w1_ms':W};log.append({'kind':'watch_hello','request':hello,'reply':{'p':'J_HELLO_ACK1','sid':watch,'native_sid':sid,'duration_ms':20000}})
    req={'p':'J_CLK_REQ1','sid':watch,'native_sid':sid,'seq':0,'w1_ms':W};rep={'p':'J_CLK_REP1',**{k:req[k]for k in ['sid','native_sid','seq','w1_ms']},'p2_us':P+3000,'p3_us':P+3100};log.append({'kind':'watch_clock_request','request':req,'reply':rep});log.append({'kind':'watch_clock_observation','observation':{'p':'J_CLK_OBS1',**{k:rep[k]for k in ['sid','native_sid','seq','w1_ms','p2_us','p3_us']},'w4_ms':W+10}})
    rows=[[0,W+1,1.25,2.5,3.75],[1,W+61,2.25,3.5,4.75]];payload=json.dumps(rows,separators=(',',':'));packet={'p':'J_DATA1','sid':watch,'native_sid':sid,'index':0,'payload':payload,'crc32':f'{zlib.crc32(payload.encode()):08x}'};log.append({'kind':'watch_data','packet':packet});log.append({'kind':'watch_end','packet':{'p':'J_END1','sid':watch,'native_sid':sid,'count':2,'blocks':1,'start_ms':W,'stop_ms':W+20000,'stop_reason':'duration','clock_observations':1,'acquisition':{'accepted_rows':2,'valid_xyz_callbacks':3}}})
    meta={'session_id':sid,'app_version':'0.1.0','joint_probe':True,'received':[2,2],'confirmed':[2,2],'dropped':[0,0],'collection_start_elapsed_ns':10000000000,'stop_elapsed_ns':40000000000}
    blobs={'metadata.json':json.dumps(meta).encode(),'events.jsonl':('\n'.join(json.dumps(e)for e in events)+'\n').encode(),'accelerometer.csv':b'sequence,event_timestamp_ns,received_elapsed_ns,writer_dequeued_elapsed_ns,x,y,z,accuracy\n1,10010000000,10010000000,10010000001,1,2,3,3\n2,10020000000,10020000000,10020000001,1,2,3,3\n','gyroscope.csv':b'sequence,event_timestamp_ns,received_elapsed_ns,writer_dequeued_elapsed_ns,x,y,z,accuracy\n1,10010000000,10010000000,10010000001,1,2,3,3\n2,10020000000,10020000000,10020000001,1,2,3,3\n'}
    def write_zip():
        manifest={'files':[{'path':k,'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()}for k,v in blobs.items()]}
        with zipfile.ZipFile(directory/'native.zip','w')as z:
            for k,v in blobs.items():z.writestr(k,v)
            z.writestr('manifest.json',json.dumps(manifest))
    def write_log(): (directory/'plugin.jsonl').write_text('\n'.join(json.dumps(v)for v in log)+'\n',encoding='utf-8')
    write_zip();write_log();return log,blobs,write_log,write_zip
class AnalyzerTest(unittest.TestCase):
 def test_two_bridges_and_causal_availability(self):
    with tempfile.TemporaryDirectory()as d:
        p=Path(d);fixture(p);r=mod.analyze(p/'native.zip',p/'plugin.jsonl');self.assertEqual(r['watch_rows'],2);self.assertEqual(r['native_exchanges'],2);self.assertEqual(r['watch_exchanges'],1);self.assertEqual(r['watch_clock_intervals'][0]['available_native_ns'],11002000000);self.assertFalse(r['physical_clock_accepted']);self.assertFalse(r['oracle_ready']);self.assertIsNone(r['video_to_native_mapping'])
 def test_bad_crc_rejected(self):
    with tempfile.TemporaryDirectory()as d:
        p=Path(d);log,_,wl,_=fixture(p);next(v for v in log if v['kind']=='watch_data')['packet']['crc32']='00000000';wl();self.assertRaises(ValueError,mod.analyze,p/'native.zip',p/'plugin.jsonl')
 def test_foreign_phone_rejected(self):
    with tempfile.TemporaryDirectory()as d:
        p=Path(d);log,_,wl,_=fixture(p);log[0]['native_sid']='foreign';wl();self.assertRaises(ValueError,mod.analyze,p/'native.zip',p/'plugin.jsonl')
 def test_nonce_echo_rejected(self):
    with tempfile.TemporaryDirectory()as d:
        p=Path(d);log,_,wl,_=fixture(p);log[1]['reply']['nonce']='foreign';wl();self.assertRaises(ValueError,mod.analyze,p/'native.zip',p/'plugin.jsonl')
 def test_unknown_activity_is_never_reference(self):
    with tempfile.TemporaryDirectory()as d:
        p=Path(d);fixture(p);r=mod.analyze(p/'native.zip',p/'plugin.jsonl');self.assertFalse(r['reference_created']);self.assertFalse(r['joint_result']);self.assertFalse(r['research_validated'])
 def test_manifest_tamper_and_duplicate_keys_rejected(self):
    with tempfile.TemporaryDirectory()as d:
        p=Path(d);fixture(p);s=(p/'plugin.jsonl').read_text();(p/'plugin.jsonl').write_text(s.replace('"schema_version": 1','"schema_version": 1, "schema_version": 1',1));self.assertRaises(ValueError,mod.analyze,p/'native.zip',p/'plugin.jsonl')
 def test_changed_zip_member_rejected_by_original_manifest(self):
    with tempfile.TemporaryDirectory()as d:
        p=Path(d);fixture(p)
        with zipfile.ZipFile(p/'native.zip')as z:members={n:z.read(n)for n in z.namelist()}
        members['accelerometer.csv']+=b'3,10030000000,10030000000,10030000001,1,2,3,3\n'
        with zipfile.ZipFile(p/'tampered.zip','x')as z:
            for name,b in members.items():z.writestr(name,b)
        self.assertRaises(ValueError,mod.analyze,p/'tampered.zip',p/'plugin.jsonl')
 def test_stop_ms_tie_is_retained_and_disclosed(self):
    with tempfile.TemporaryDirectory()as d:
        p=Path(d);log,_,wl,_=fixture(p);end=next(v for v in log if v['kind']=='watch_end')['packet'];end['stop_ms']=W+61;end['stop_reason']='user';wl();r=mod.analyze(p/'native.zip',p/'plugin.jsonl');self.assertEqual(r['watch_rows'],2);self.assertTrue(r['last_sample_shares_recorded_stop_ms'])
 def test_watch_failure_is_readable_and_not_complete(self):
    with tempfile.TemporaryDirectory()as d:
        p=Path(d);log,_,wl,_=fixture(p);log[:]=[v for v in log if v['kind']!='watch_end']
        log.append({'kind':'watch_failure','packet':{'p':'J_FAIL1','sid':'watch-session','native_sid':'native-session','stage':'block','error':'synthetic block write timeout','count':2,'blocks':1,'start_ms':W,'stop_ms':W+61,'stop_reason':'failure'}});wl()
        r=mod.analyze(p/'native.zip',p/'plugin.jsonl');self.assertEqual(r['watch_rows'],2);self.assertTrue(r['watch_failed']);self.assertEqual(r['watch_failure_stage'],'block');self.assertEqual(r['status'],'same_session_transport_failed_partial');self.assertFalse(r['joint_result'])
 def test_end_after_failure_is_rejected(self):
    with tempfile.TemporaryDirectory()as d:
        p=Path(d);log,_,wl,_=fixture(p);end=next(v for v in log if v['kind']=='watch_end');log.remove(end);log.append({'kind':'watch_failure','packet':{'p':'J_FAIL1','sid':'watch-session','native_sid':'native-session','stage':'block','error':'synthetic block write timeout','count':2,'blocks':1,'start_ms':W,'stop_ms':W+61,'stop_reason':'failure'}});log.append(end);wl();self.assertRaises(ValueError,mod.analyze,p/'native.zip',p/'plugin.jsonl')
 def test_local_failure_before_upload_keeps_reported_and_received_counts_separate(self):
    with tempfile.TemporaryDirectory()as d:
        p=Path(d);log,_,wl,_=fixture(p);log[:]=[v for v in log if v['kind']not in ['watch_data','watch_end']]
        log.append({'kind':'watch_failure','packet':{'p':'J_FAIL1','sid':'watch-session','native_sid':'native-session','stage':'block','error':'synthetic local write timeout','count':16,'blocks':2,'start_ms':W,'stop_ms':W+2000,'stop_reason':'failure'}});wl()
        r=mod.analyze(p/'native.zip',p/'plugin.jsonl');self.assertEqual(r['watch_rows'],0);self.assertEqual(r['watch_blocks'],0);self.assertEqual(r['watch_failure_reported_rows'],16);self.assertEqual(r['watch_failure_reported_blocks'],2);self.assertIsNone(r['watch_local_persisted_rows']);self.assertEqual(r['status'],'same_session_transport_failed_partial');self.assertFalse(r['oracle_ready'])
 def test_failure_cannot_underreport_received_rows(self):
    with tempfile.TemporaryDirectory()as d:
        p=Path(d);log,_,wl,_=fixture(p);log[:]=[v for v in log if v['kind']!='watch_end'];log.append({'kind':'watch_failure','packet':{'p':'J_FAIL1','sid':'watch-session','native_sid':'native-session','stage':'block','error':'synthetic','count':1,'blocks':0,'start_ms':W,'stop_ms':W+2000,'stop_reason':'failure'}});wl();self.assertRaises(ValueError,mod.analyze,p/'native.zip',p/'plugin.jsonl')
