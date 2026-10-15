"""Read-only, single-SQLite ROS bag checks. No ROS or device dependencies."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

TOPICS={'/livox/lidar':'sensor_msgs/msg/PointCloud2','/livox/imu':'sensor_msgs/msg/Imu'}


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def inspect_bag(directory):
    directory=Path(directory).resolve()
    databases=list(directory.glob('*.db3')) if directory.is_dir() else []
    if len(databases)!=1:raise ValueError('Expected one existing SQLite bag file; input is never created.')
    db=databases[0]
    if Path(str(db)+'-wal').exists():raise ValueError('WAL present: close the recorder before immutable inspection.')
    before=digest(db)
    report={'schema_version':1,'database_bytes':db.stat().st_size,'database_sha256_before':before,
            'metadata_present':(directory/'metadata.yaml').is_file(),'topics':{},
            'geometry_quality':'not_assessed','capture_window':'not_assessed',
            'time_semantics':'SQLite record timestamps, not independently validated device clocks'}
    valid=report['metadata_present']
    with closing(sqlite3.connect(db.as_uri()+'?mode=ro&immutable=1',uri=True)) as con:
        con.execute('PRAGMA query_only=ON')
        report['sqlite_quick_check']=con.execute('PRAGMA quick_check').fetchone()[0]
        valid=valid and report['sqlite_quick_check']=='ok'
        for name,expected_type in TOPICS.items():
            definitions=con.execute('SELECT id,type FROM topics WHERE name=?',(name,)).fetchall()
            if len(definitions)!=1:
                report['topics'][name]={'definition_count':len(definitions),'messages':0};valid=False;continue
            topic_id,kind=definitions[0]
            count=0;first=last=None;minimum=maximum=None;nonpositive=0
            for (stamp,) in con.execute('SELECT timestamp FROM messages WHERE topic_id=? ORDER BY id',(topic_id,)):
                if last is not None:
                    delta=stamp-last;nonpositive+=int(delta<=0)
                    minimum=delta if minimum is None else min(minimum,delta)
                    maximum=delta if maximum is None else max(maximum,delta)
                if first is None:first=stamp
                last=stamp;count+=1
            span=last-first if count>1 else None
            report['topics'][name]={'type':kind,'messages':count,'first_record_ns':first,'last_record_ns':last,
                'span_s':span/1e9 if span is not None else None,'nonpositive_record_intervals':nonpositive,
                'min_record_interval_ns':minimum,'max_record_interval_ns':maximum,
                'mean_interarrival_rate_hz':(count-1)*1e9/span if span and span>0 and not nonpositive else None}
            valid=valid and kind==expected_type and count>=2 and nonpositive==0
    report['database_sha256_after']=digest(db)
    report['bytes_unchanged']=before==report['database_sha256_after']
    report['record_structure']='pass' if valid and report['bytes_unchanged'] else 'fail'
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('bag',type=Path);p.add_argument('--output',type=Path)
    args=p.parse_args();report=inspect_bag(args.bag);text=json.dumps(report,indent=2)+'\n'
    if args.output:
        with args.output.open('x',encoding='utf-8') as f:f.write(text)
    else:print(text,end='')
    return 0 if report['record_structure']=='pass' else 2


if __name__=='__main__':raise SystemExit(main())
