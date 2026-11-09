"""Independent, evaluation-only audit of the frozen raw-input011 confirmation.

Reference furniture and trajectories are used here, never by the infer CLI.
No record is excluded, including infeasible decodes and wrong frame choices.
"""
import argparse, collections, hashlib, json
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.stats import binomtest
from . import multi_instance as M


def wilson(k, n):
    z=1.959963984540054; p=k/n; d=1+z*z/n
    c=(p+z*z/(2*n))/d; h=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [float(c-h),float(c+h)]


def bootstrap(x, seed=11011):
    x=np.asarray(x,float); rng=np.random.default_rng(seed)
    return np.quantile(x[rng.integers(len(x),size=(20000,len(x)))].mean(axis=1),[.025,.975]).tolist()


def independent_score(pred, truth):
    per={}; errors=[]; matched_iou=[]; tp=0
    for cls in ['bed','desk','cab','chair']:
        ps=np.array([b for k,b in pred.items() if k.split('#')[0]==cls]).reshape(-1,4)
        ts=np.array([b for k,b in truth.items() if k.split('#')[0]==cls]).reshape(-1,4); hit=0
        if len(ps) and len(ts):
            distance=np.linalg.norm((ps[:,:2]+ps[:,2:])[:,None,:]/2-(ts[:,:2]+ts[:,2:])[None,:,:]/2,axis=2)
            rows,cols=linear_sum_assignment((distance>.5)*(min(len(ps),len(ts))+1)+np.minimum(distance,100)*1e-5)
            for i,j in zip(rows,cols):
                hit+=bool(distance[i,j]<=.5); errors.append(float(distance[i,j]))
                overlap=np.maximum(0,np.minimum(ps[i,2:],ts[j,2:])-np.maximum(ps[i,:2],ts[j,:2])).prod()
                union=np.prod(ps[i,2:]-ps[i,:2])+np.prod(ts[j,2:]-ts[j,:2])-overlap
                matched_iou.append(float(overlap/union))
        per[cls]={'tp':int(hit),'n_truth':len(ts),'n_pred':len(ps)};tp+=hit
    all_hit=bool(truth) and tp==len(pred)==len(truth)
    # IoU is independently assigned by overlap, not reused centre matching.
    all_iou=bool(truth) and len(pred)==len(truth)
    for cls in per:
        ps=np.array([b for k,b in pred.items() if k.split('#')[0]==cls]).reshape(-1,4)
        ts=np.array([b for k,b in truth.items() if k.split('#')[0]==cls]).reshape(-1,4)
        if len(ps)!=len(ts):all_iou=False;continue
        if not len(ts):continue
        overlap=np.maximum(0,np.minimum(ps[:,None,2:],ts[None,:,2:])-np.maximum(ps[:,None,:2],ts[None,:,:2])).prod(axis=2)
        iou=overlap/(np.prod(ps[:,2:]-ps[:,:2],axis=1)[:,None]+np.prod(ts[:,2:]-ts[:,:2],axis=1)[None,:]-overlap)
        a,b=linear_sum_assignment((iou<.5)*(len(ps)+1)-iou*1e-5)
        all_iou=all_iou and bool(np.all(iou[a,b]>=.5))
    return {'tp':int(tp),'f1':2*tp/(len(pred)+len(truth)) if pred or truth else 0.,'whole':all_hit,'whole_iou0_5':all_iou,'per_class':per,'matched_centre_errors_m':errors,'centre_assignment_ious':matched_iou}


def audit(root,native):
    root,native=map(Path,(root,native)); frozen=json.loads((root/'freeze.json').read_text())
    code_check={name:hashlib.sha256(Path(__file__).with_name(name+'.py').read_bytes()).hexdigest()==sha for name,sha in frozen['code_sha256'].items()}
    if not all(code_check.values()):raise AssertionError('Frozen inference source changed')
    records=[];rows=[]
    for i in frozen['ids']:
        folder=root/f'multi-{i:05d}';r=json.loads((folder/'results.json').read_text());scene=M.load_native(native/f'multi-{i:05d}.json')
        assert hashlib.sha256((native/f'multi-{i:05d}.json').read_bytes()).hexdigest()==r['native_sha256']
        for name,sha in r['input_sha256'].items():assert hashlib.sha256((folder/'input'/name).read_bytes()).hexdigest()==sha
        truth=np.load(folder/'evaluation-truth.npz');records.append(r)
        for q in r['rows']:
            result=independent_score(q['prediction']['boxes'],scene['gt'])
            assert result['tp']==q['score']['tp'] and result['whole']==q['score']['all_instances_hit']
            assert abs(result['f1']-q['score']['f1'])<1e-12
            assert result['whole_iou0_5']==q['whole_iou0_5']
            row={'scene':r['scene'],'n_objects':r['n_objects'],'speed_m_s':r['speed_m_s'],'duration_s':r['duration_s'],'arm':q['arm'],'status':q['prediction']['status'],**result}
            if not q['oracle_assisted']:
                est=np.load(folder/(q['arm']+'-estimated.npz'));p=est['path'];degree=q['prediction']['yaw_deg'];a=np.radians(degree);Q=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]]);priors=json.loads((folder/'input/known-priors.json').read_text());room_path=(p-p[0])@Q.T+priors['start'];e=np.linalg.norm(room_path-truth['position'][:,:2],axis=1)
                row.update(relative_frame_ade_m=q['relative_frame_ade_m'],relative_frame_p90_m=q['relative_frame_p90_m'],room_frame_ade_m=float(e.mean()),room_frame_p90_m=float(np.quantile(e,.9)),path_ratio=float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum()/np.linalg.norm(np.diff(truth['position'][:,:2],axis=0),axis=1).sum()))
            rows.append(row)
    names=[q['arm'] for q in records[0]['rows']];summary={}
    for arm in names:
        group=[r for r in rows if r['arm']==arm];n=len(group);whole=sum(r['whole'] for r in group)
        summary[arm]={'n':n,'whole':whole,'rate':whole/n,'wilson95':wilson(whole,n),'ok':sum(r['status']=='ok' for r in group),'mean_f1':float(np.mean([r['f1'] for r in group])),'f1_bootstrap95':bootstrap([r['f1'] for r in group]),'whole_iou0_5':sum(r['whole_iou0_5'] for r in group),'status_counts':dict(collections.Counter(r['status'] for r in group)),'per_class':{c:{'tp':sum(r['per_class'][c]['tp'] for r in group),'n_truth':sum(r['per_class'][c]['n_truth'] for r in group)} for c in ['bed','desk','cab','chair']},'speed_strata':{str(s):{'n':sum(r['speed_m_s']==s for r in group),'whole':sum(r['whole'] for r in group if r['speed_m_s']==s),'f1':float(np.mean([r['f1'] for r in group if r['speed_m_s']==s]))} for s in [.55,.65,.75]}}
        if 'relative_frame_ade_m' in group[0]:
            for key in ['relative_frame_ade_m','relative_frame_p90_m','room_frame_ade_m','room_frame_p90_m','path_ratio']:summary[arm]['median_'+key]=float(np.median([r[key] for r in group]))
    paired={};primary=[r for r in rows if r['arm']=='new_raw']
    for arm in names[1:]:
        other=[r for r in rows if r['arm']==arm];a=np.array([r['whole'] for r in primary],int);b=np.array([r['whole'] for r in other],int);plus=int(np.sum(a>b));minus=int(np.sum(b>a))
        paired[arm]={'both_hit':int(np.sum((a==1)&(b==1))),'new_only':plus,'other_only':minus,'both_miss':int(np.sum((a==0)&(b==0))),'gain_pp':float(100*np.mean(a-b)),'paired_bootstrap95_pp':[100*v for v in bootstrap(a-b)],'exact_mcnemar_p':float(binomtest(plus,plus+minus,.5).pvalue) if plus+minus else 1.}
        delta=np.array([x['f1']-y['f1'] for x,y in zip(primary,other)])
        paired[arm].update(f1_gain=float(delta.mean()),f1_gain_paired_bootstrap95=bootstrap(delta))
    out={'n':len(records),'code_freeze_matches':code_check,'independent_score_checks':len(rows),'all_input_hashes_match':True,'duration_s_range':[min(r['duration_s'] for r in records),max(r['duration_s'] for r in records)],'summary':summary,'paired':paired,'rows':rows,'scope':'Offline, same-generator-domain supervised calibration;32 new recordings, not32 untouched natural rooms; failed rooms retained; no geometric activity threshold inferred here'}
    (root/'audit.json').write_text(json.dumps(out,indent=1));return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--native',required=True);a=p.parse_args();r=audit(a.root,a.native);print(json.dumps({k:r[k] for k in ['n','independent_score_checks','duration_s_range','summary','paired']},indent=1))
