"""Read frozen synthetic outputs and export a deterministic, browser-only view.

No sampling, retraining, scoring, threshold selection or real sensor input.
The output directory may exist; output files must not already exist.
"""
import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import numpy as np

FAMILIES=['dorm','apartment','conference','office','classroom','hotel']
NAMES=['宿舍','公寓','会议室','办公室','教室','酒店']
MODES=['oracle_groups','complete_fixed','density_fixed']

def load(path):return json.loads(path.read_text('utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def put(root,name,data):
    path=root/name
    if path.exists():raise FileExistsError(path)
    raw=(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8')
    if len(raw)>1_990_000:raise ValueError(f'Asset exceeds source policy: {name} {len(raw)}')
    path.write_bytes(raw)
    return dict(file=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def corners(path):
    points=[path[0]] if path else []
    for i in range(1,len(path)-1):
        a,b,c=np.array(path[i-1]),np.array(path[i]),np.array(path[i+1])
        if not np.array_equal(b-a,c-b):points.append(path[i])
    if len(path)>1:points.append(path[-1])
    return [[round(.2*p[1]+.1,6),round(.2*p[0]+.1,6)] for p in points]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    root=args.source_root
    lib=root/'output/prospective-space/2026-10-30-simulation-abstention-and-action-plan-001/six-family-geometry-library-001'
    integration=root/'output/prospective-space/2026-11-01-auto-group-ranking-closeout-001'
    inputs=[lib/'run-v2/houses.jsonl',integration/'run/test-houses.json',
            integration/'run/test-metrics.npz',integration/'run/test-summary.json',
            lib/'noisy-candidate-ranking-001/run/test-summary.json',integration/'PROTOCOL.md',integration/'freeze.json']
    hashes=[dict(name=p.relative_to(root).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in inputs]
    with inputs[0].open(encoding='utf-8') as stream:houses=[json.loads(line) for line in stream if line.strip()]
    houses=[h for h in houses if h['split']=='test']
    metadata=load(inputs[1])['rows']
    with np.load(inputs[2]) as archive:z={name:archive[name] for name in archive.files}
    summary=load(inputs[3]);noise=load(inputs[4])
    assert len(houses)==len(metadata)==600
    assert [r['house_id'] for r in houses]==[r['house_id'] for r in metadata]
    assert z['observed_positions'].shape==(600,4,32,2)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    exported=[]
    catalogue=[dict(id=h['house_id'],family=h['family'],sites=len(h['quality']['sites'])) for h in houses]
    for family,name in zip(FAMILIES,NAMES):
        rows=[]
        for hi,(house,meta) in enumerate(zip(houses,metadata)):
            if house['family']!=family:continue
            routes=[]
            for ri,route in enumerate(house['routes']):
                events=route['events'][:32]
                truth=np.array([e['xy_truth'] for e in events])
                paths=[corners(e['path_cells']) for e in events]
                assert all(np.max(np.abs(np.array(path[-1])-event['xy_truth']))<1e-10 for path,event in zip(paths,events))
                methods=[]
                for gi,mode in enumerate(MODES):
                    q=int(z['structure'][hi,ri,gi,1]);values=z['metrics'][hi,ri,gi,1]
                    labels=z['assignments'][hi,ri,gi].tolist()
                    assert len(set(labels))==q and min(labels)>=0
                    mask=np.flatnonzero(z['best_masks'][hi,ri,gi,1]).tolist()
                    methods.append(dict(mode=mode,assignments=labels,group_count=q,
                        representatives=z['representatives'][hi,ri,gi,:q].tolist(),
                        identity_top1=float(values[0]),identity_top5=float(values[1]),class_top1=float(values[3]),
                        unassigned_events=int(z['structure'][hi,ri,gi,2]),
                        target_retained=bool(z['structure'][hi,ri,gi,3]),
                        candidate_count=int(np.count_nonzero(z['sites']>=q)),
                        first_tie_count=len(mask),first_ties=[houses[i]['house_id'] for i in mask[:12]],
                        first_ties_truncated=len(mask)>12,
                        relation=dict(zip(['tp','fp','fn','tn'],map(int,z['structure'][hi,ri,gi,6:10])))))
                routes.append(dict(truth=truth.tolist(),site_ids=[e['site_truth'] for e in events],
                    paths=paths,observed=z['observed_positions'][hi,ri].tolist(),methods=methods))
            rows.append(dict(id=house['house_id'],family=family,cohort=meta['cohort'],
                alias_ids=[houses[i]['house_id'] for i in meta['alias_indices']],
                rooms=house['rooms'],objects=house['objects'],doors=house['doors'],entry=house['entry'],
                sites=[dict(id=s['id'],xy=s['xy'],kind=s['coarse']) for s in house['quality']['sites']],routes=routes))
        assert len(rows)==100
        parts=[]
        for half in range(2):
            name_part='simulation-'+family+'-'+str(half+1)+'.json'
            parts.append(put(args.output_dir,name_part,dict(schema='simulation-family-part-v1',family=family,houses=rows[50*half:50*(half+1)])))
        asset=put(args.output_dir,'simulation-'+family+'.json',dict(schema='simulation-family-v1',family=family,houses=100,parts=parts))
        exported.append(dict(id=family,name=name,houses=len(rows),**asset))
    fixed=[r for r in summary['rows'] if r['score']=='fixed_penalty']
    for row in fixed:
        cohort=row['cohort']
        members=[m for m in metadata if cohort=='all' or m['cohort']==cohort or m['family']==cohort]
        ceiling=sum((Fraction(1,m['class_size']) for m in members),Fraction(0))
        row['complete_02m_representation_ceiling']=dict(numerator=float(ceiling),denominator=len(members),value=float(ceiling/len(members)))
    def_rows=[r for r in noise['rows'] if r['cohort']=='all' and r['visits']==32 and r['method']=='partial_normalized_spectrum' and (r['sigma']==0 or r['sigma']==.5)]
    assert len(def_rows)==4
    index=dict(schema='simulation-lab-v1',houses=600,routes_per_house=4,visits=32,
        families=exported,catalogue=catalogue,modes=MODES,aggregate_rows=fixed,
        condition=dict(error='brownian',terminal_per_axis_sd_m=.5,penalty_lambda=.0003,grid_m=.2,
                       known_closed_catalog=True,inference='full_record_offline',post_audit_exploratory=True),
        scope=dict(raw_imu_simulated=False,procthor_generated=False,real_room_ranking=False,
                   origin_yaw_scale='distance-spectrum invariants; display geometry is evaluation side only'),
        defence=dict(rows=def_rows,deployed_defence_validated=False,
                     scoring='oracle grouping; partial normalized spectrum; lambda=0; not the integration score'),
        flags=summary['flags'],sources=hashes,
        selection='All 600 test houses, all four routes. Default first ID per family, never selected for high scores.',
        route_display='Frozen grid path; collinear segments compressed for display only. Replay reveals the completed full-record grouping, not prefix inference.')
    put(args.output_dir,'simulation-index.json',index)
    for before,path in zip(hashes,inputs):assert sha(path)==before['sha256'],path
    print(json.dumps(dict(families=[dict(id=r['id'],bytes=r['bytes']) for r in exported],houses=600,routes=2400,source_files_unchanged=len(inputs)),ensure_ascii=False))

if __name__=='__main__':main()
