"""Package derived011 evidence without publishing real raw sensor streams."""
import argparse,hashlib,json,platform
from pathlib import Path
import numpy as np
import scipy,sklearn
from . import action_model as AM, paths, multi_instance as M, multi_raw010 as X
from .oriented_raw011 import directed_contact,bed_orientation_mask


def report(package,native,output):
    p,native,output=map(Path,(package,native,output));audit=json.loads((p/'confirm32/audit.json').read_text());real=json.loads((p/'real-joint/results.json').read_text());freeze=json.loads((p/'confirm32/freeze.json').read_text());motion=p/'spectral-training/trees-distance.joblib';wrist=Path('output/research-sync/2026-11-09-joint-input-and-recovery-010/wrist-ensemble-final/model.joblib');checks=[]
    for i in freeze['ids']:
        sc=M.load_native(native/f'multi-{i:05d}.json');s=json.loads((native/f'multi-{i:05d}.json').read_text())['agent_placement']['position'];sc['S']=np.array([s['x'],s['z']]);script,_=X.plan(sc)
        for event in script:
            if event['label'] not in ['lying','seated','cabinet']:continue
            cls={'lying':'bed','seated':'desk','cabinet':'cab'}[event['label']];boxes=np.array([b for k,b in sc['gt'].items() if M.category(k)==cls]);point=np.asarray(event['b']);heading=np.asarray(event['heading'])
            if cls=='bed':
                within=np.all((point>=boxes[:,:2])&(point<=boxes[:,2:]),axis=1);valid=bool(np.any(within&bed_orientation_mask(boxes,heading)))
            else:valid=bool(directed_contact('desk_relation' if cls=='desk' else 'cab',boxes,point,heading,.3)[0].any())
            checks.append({'scene':sc['scene'],'channel':cls,'valid':valid})
    contract={'n':len(checks),'invalid':[r for r in checks if not r['valid']],'by_channel':{c:{'n':sum(r['channel']==c for r in checks),'valid':sum(r['valid'] for r in checks if r['channel']==c)} for c in ['bed','desk','cab']},'scope':'Ideal generated interactions, all32 frozen records retained; does not validate natural carry protocol'};(p/'confirmation-contract-audit.json').write_text(json.dumps(contract,indent=1))
    expected={'phone':'0ee65930c5e5a5eeab8139bb4477c222dc2e51bccd5eadb4aeadb36e1504d6d4','ronin':'5ae5c9e508f2dc9609c25b59d0e3dfd770ecbcde6920cbc5be3c6d9fed8a6346','wrist':'12bc70f63f2731270aa875f7ebbacafb9dc7849382f9bad56f56b21415531ad4','displacement':'2b540d7075ac782c119f25ed69cfbcd561e4612524076afceb4713c8fef8f3d3'}
    actual={k:hashlib.sha256(f.read_bytes()).hexdigest() for k,f in [('phone',AM.MODEL_PATH),('ronin',Path(paths.RONIN_CKPT)),('wrist',wrist),('displacement',motion)]};assert actual==expected
    truth={'bed':[1.17,1.96,2.695,4.045],'desk':[.05,1.05,.65,2.10],'cab':[.05,0,.65,1.05],'chair':[1.11,.92,1.55,1.36]};phone=json.loads((p/'real-phone/prediction.json').read_text());errors={c:float(np.linalg.norm((np.asarray(b[:2])+b[2:])/2-(np.asarray(truth[c][:2])+truth[c][2:])/2)) for c,b in phone['boxes'].items()}
    out={'schema':'raw-input-repair-011','parent_revision':'0c71b94','input':'Phone6axis120Hz + watch3axis16.7Hz, no watch gyro; known room/start/inventory','inference':'Full-record offline; supervised same-generator-domain displacement + signal phone activities + watch-only cabinet + unknown contact-point/plane loops + directional finite decoder','n_frozen_recordings':audit['n'],'duration_s_range':audit['duration_s_range'],'summary':audit['summary'],'paired':audit['paired'],'contract_audit':contract,'independent_evaluation':{'n_scores':audit['independent_score_checks'],'frozen_source_matches':audit['code_freeze_matches'],'all_input_hashes_match':audit['all_input_hashes_match']},'input_firewall':json.loads((p/'input-firewall/verification.json').read_text()),'corrected_old16_gauge':json.loads((p/'gauge-corrected16/summary.json').read_text()),'real_regression':{'legacy_phone_baseline_max_box_delta_m':real['phone_baseline_max_box_delta_m'],'legacy_phone_errors_m':errors,'joint_zero_shift_errors_m':{m['class']:m['error_m'] for r in real['rows'] if r['shift_s']==0 for m in r['score']['matches']},'joint_all_hit_each_shift':{str(r['shift_s']):r['score']['all_instances_hit'] for r in real['rows']},'phone_trajectory_exact':real['phone_trajectory_exactly_equal_previous_replay'],'physical_clock_accepted':False,'same_synthetic_frontend_used':False,'scope':'One reused real development room; production protocol/solver differ; no new synthetic-to-real success claim'},'weight_sha256':actual,'training':json.loads((p/'spectral-training/trees-distance.json').read_text()),'selection_freeze':json.loads((p/'selection-freeze.json').read_text()),'versions':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'scikit_learn':sklearn.__version__},'limits':['Not a raw-IMU80percent activity threshold: only100percent/14visit dose confirmed','New whole-hit gain exact paired p=.109, not established at.05; sample small','32 new long signals from same generator; geometry may have prior short/geometric use','Same-generator supervised calibration; no claim of zero-shot transfer or repaired pretrained RoNIN','Known room/start/inventory, near-wall/Manhattan/interaction-facing priors','Whole centre success differs from footprint success','Gait-template inverse prototype excluded from frozen inference; matched-template unit test is not independent validation']}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(out,ensure_ascii=False,indent=1)+'\n',encoding='utf-8');(p/'derived-summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=1)+'\n',encoding='utf-8');print(json.dumps({'contract':contract,'models_unchanged':True,'real_phone_errors_m':errors,'output':str(output)},ensure_ascii=False,indent=1));return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--native',required=True);p.add_argument('--out',required=True);a=p.parse_args();report(a.package,a.native,a.out)
