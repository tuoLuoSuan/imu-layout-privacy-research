"""Generate a display-only copy from the user's original SAF ZIP, preserving values."""
from pathlib import Path
import csv, hashlib, io, json, zipfile

root=Path(__file__).resolve().parents[2]
source=root/'data/raw/phone/phone_config_smoke_001/imu_88aded49-4285-4449-9cb9-e0f8c7ac40a3.zip'
expected='3a873df8d31613efbc39519a6d8781a563e8da9166a92f7c8b129f7389df1809'
assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
with zipfile.ZipFile(source) as z:
    meta=json.loads(z.read('metadata.json'))
    channels={}
    for name in ('accelerometer','gyroscope'):
        raw=list(csv.DictReader(io.StringIO(z.read(name+'.csv').decode('utf-8'))))
        first=int(raw[0]['sensor_timestamp_ns'])
        rows=[[(int(r['sensor_timestamp_ns'])-first)/1e6,*[float(r[k]) for k in ('x','y','z')]] for r in raw]
        assert all(r[0]>rows[i-1][0] for i,r in enumerate(rows) if i)
        channels[name]={'first_sensor_timestamp_ns':str(first),'rows':rows}
result={'session_id':meta['session_id'],'version':meta['app_version'],'source_sha256':expected,
        'source_archive':'data/raw/phone/phone_config_smoke_001/'+source.name,
        'requested_rate_hz':meta['requested_rate_hz'],'requested_period_us':meta['requested_period_us'],
        'duration_s':(meta['stop_elapsed_ns']-meta['collection_start_elapsed_ns'])/1e9,
        'time_semantics':'each channel relative to its first raw sensor event; no synchronization implied',
        'processing':'integer timestamp subtraction then ms conversion; xyz unchanged; no interpolation or resampling',
        'channels':channels}
out=root/'showcase/data/phone-config-smoke.json'
out.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
print(json.dumps({'rows':{k:len(v['rows']) for k,v in channels.items()},'original_zip_sha256':expected}))
