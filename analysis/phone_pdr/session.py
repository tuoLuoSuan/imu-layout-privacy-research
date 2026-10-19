"""Read native phone bundles without changing originals; exclusively create output."""
import csv,hashlib,io,json,math,os,stat,zipfile
from pathlib import Path

def validated_output(output, allowed_root):
    output=Path(os.path.abspath(output));allowed_root=Path(os.path.abspath(allowed_root))
    if output==allowed_root or not output.is_relative_to(allowed_root):raise ValueError('Path escapes diagnostic output root')
    for ancestor in [output,*output.parents]:
        if ancestor.exists():
            info=ancestor.lstat()
            if ancestor.is_symlink() or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):raise ValueError('Linked output path refused')
    return output

def _parse(payload):
    rows=[];previous=None
    with io.StringIO(payload.decode('utf-8-sig'),newline='') as stream:
        reader=csv.DictReader(stream)
        if not set(['sequence','sensor_timestamp_ns','x','y','z']).issubset(reader.fieldnames or []):raise ValueError('Missing native CSV fields')
        for index,row in enumerate(reader,1):
            if int(row['sequence'])!=index:raise ValueError('Non-contiguous sequence')
            t=int(row['sensor_timestamp_ns']);v=tuple(float(row[k]) for k in ('x','y','z'))
            if not all(math.isfinite(x) for x in v):raise ValueError('Values must be finite')
            if previous is not None and t<=previous:raise ValueError('Non-increasing event timestamp')
            previous=t;rows.append((t,*v))
    if len(rows)<2:raise ValueError('Insufficient samples')
    return rows

def load_session(path):
    path=Path(path);names=['metadata.json','accelerometer.csv','gyroscope.csv']
    if path.is_dir():payload={n:(path/n).read_bytes() for n in names};carrier=None
    else:
        carrier=path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(carrier)) as z:
            if any(z.namelist().count(n)!=1 for n in names):raise ValueError('Missing or duplicated native bundle member')
            payload={n:z.read(n) for n in names}
    metadata=json.loads(payload['metadata.json'])
    units=metadata.get('units',{})
    if units.get('accelerometer')!='m/s^2 including gravity' or units.get('gyroscope')!='rad/s':raise ValueError('Unsupported or unknown units')
    a=_parse(payload['accelerometer.csv']);g=_parse(payload['gyroscope.csv'])
    if metadata.get('written')!=[len(a),len(g)]:raise ValueError('Metadata written counts disagree')
    origin=min(a[0][0],g[0][0])
    def relative(rows):return [((r[0]-origin)/1e9,*r[1:]) for r in rows]
    source={'carrier':str(path),'carrier_sha256':hashlib.sha256(carrier).hexdigest() if carrier is not None else None,
            'app_version':metadata.get('app_version'),'requested_period_us':metadata.get('requested_period_us'),
            'timestamp_semantics':'Android SensorEvent.timestamp; not validated physical hardware clock',
            'files':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in payload.items()},
            'existing_integrity_report':'not modified or reclassified by this diagnostic'}
    return relative(a),relative(g),source

def write_diagnostic(output, result, source):
    output=Path(os.path.abspath(output))
    if output.exists():raise FileExistsError('Output must be fresh')
    output=validated_output(output,Path(__file__).resolve().parents[2]/'output/phone-pdr')
    output.parent.mkdir(parents=True,exist_ok=True);output.mkdir(exist_ok=False)
    report=dict(result,source=source)
    with (output/'diagnostic.json').open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    columns=['time_s','detected_at_s','amplitude_m_s2','device_yaw_rad','heading_sample_age_s','relative_x','relative_y','x_m','y_m']
    with (output/'step-candidates.csv').open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(result.get('step_candidates',[]))
    return output
