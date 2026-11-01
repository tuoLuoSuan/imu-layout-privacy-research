"""Read frozen predictors and private captures; export only aggregate evidence.

No estimator fitting, collection, device access, or modification of old results.
The private input inventory stays in the caller's explicitly selected output.
"""
import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import argparse,hashlib,importlib.util,itertools,json,math
from pathlib import Path
import numpy as np
import joblib
from scipy.stats import binomtest

LABELS=['close_cabinet','idle','lie_down','lying','open_cabinet','sit_down','stand_up','upright','walk']
FLAGS=dict(formal_score=None,real_candidate_rank=None,real_room_ranking=None,real_room_family_count=None,physical_accuracy_validated=False,physical_clock_accepted=False,sensor_window_join_allowed=False,generalization_accuracy_validated=False,scientific_geometry_ground_truth_verified=False,collection_open=False)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def ratio(a,b):return dict(numerator=int(a),denominator=int(b),value=a/b if b else None)
def wilson(a,b):
    z=1.959963984540054;p=a/b;den=1+z*z/b
    return [(p+z*z/(2*b)-z*math.sqrt(p*(1-p)/b+z*z/(4*b*b)))/den,(p+z*z/(2*b)+z*math.sqrt(p*(1-p)/b+z*z/(4*b*b)))/den]
def metrics(rows,key,labels=LABELS,truth='label'):
    cm=[[0]*len(labels) for _ in labels];missing=0
    for r in rows:
        if r.get(key) is None:missing+=1;continue
        cm[labels.index(r[truth])][labels.index(r[key])]+=1
    per={}
    for i,label in enumerate(labels):
        tp=cm[i][i];fp=sum(row[i] for row in cm)-tp;fn=sum(cm[i])-tp+sum(r[truth]==label and r.get(key) is None for r in rows)
        per[label]=dict(tp=tp,fp=fp,fn=fn,support=tp+fn,precision=ratio(tp,tp+fp),recall=ratio(tp,tp+fn),f1=ratio(2*tp,2*tp+fp+fn))
    k=sum(cm[i][i] for i in range(len(labels)))
    return dict(accuracy=ratio(k,len(rows)),coverage=ratio(len(rows)-missing,len(rows)),wilson95=wilson(k,len(rows)),macro_f1=sum(p['f1']['value'] or 0 for p in per.values())/len(labels),per_class=per,labels=labels,confusion_matrix=cm,by_setting={s:ratio(sum(r.get(key)==r[truth] for r in rows if ('-G' in r['part'])==(s=='ground')),sum(('-G' in r['part'])==(s=='ground') for r in rows)) for s in ('ground','bed')})
def paired(rows,a,b,truth='label'):
    x=sum(r.get(a)==r[truth] and r.get(b)!=r[truth] for r in rows)
    y=sum(r.get(a)!=r[truth] and r.get(b)==r[truth] for r in rows)
    return dict(a_only=x,b_only=y,discordant=x+y,p_exact=float(binomtest(min(x,y),x+y,.5).pvalue) if x+y else 1.,n=len(rows),scope='event-level descriptive; events share recording sessions')
def holm(items):
    last=0
    for i,index in enumerate(sorted(range(len(items)),key=lambda j:items[j]['p_exact'])):
        last=max(last,min(1.,items[index]['p_exact']*(len(items)-i)));items[index]['p_holm_within_batch_task']=last

def main():
    p=argparse.ArgumentParser();p.add_argument('--research-root',required=True);p.add_argument('--out',required=True);p.add_argument('--snapshot',required=True);p.add_argument('--restored-root');a=p.parse_args()
    root=Path(a.research_root).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    inventory={}
    def track(path,role='evidence'):
        path=Path(path).resolve();key=path.as_posix()
        if key not in inventory:inventory[key]=dict(path=key,bytes=path.stat().st_size,sha256=sha(path),role=role)
        return path
    def load(rel):return json.loads(track(root/rel).read_text(encoding='utf-8'))
    def write(path,value):
        path=Path(path);assert not path.exists(),str(path);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    track(Path(__file__),'export-audit-code')
    restored=None
    if a.restored_root:
        restored=Path(a.restored_root).resolve();manifest=json.loads(track(restored/'MANIFEST-sha256.json','restoration-manifest').read_text(encoding='utf-8'))
        restored_count=0;restored_bytes=0
        for directory,entry in manifest['sets'].items():
            for item in entry['files']:
                path=track(restored/directory/item['name'],'restored-original')
                assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],'Restored original hash mismatch'
                restored_count+=1;restored_bytes+=item['bytes']
        write(out/'restored-originals-verification.json',dict(files=restored_count,bytes=restored_bytes,all_manifest_sha256_match=True,source_originals_modified=False))
    table_path=track(root/'output/action-recognition/2026-10-31-v5-165-cue-package-001/ready/event-table-151.json','cue-labels')
    table={(r['part'],r['step_id']):r for r in json.loads(table_path.read_text(encoding='utf-8'))}
    for rel in ['output/action-recognition/2026-11-02-accuracy-rebuild-001/dataset_ext.py','analysis/action_recognition/pipeline.py']:track(root/rel,'feature-source')
    batches={};raw_audits={};hash_checks=[]
    for batch,folder,script,freeze_name in [('T2','2026-11-03-heldout2-eval-001','score_t2_arms.py','2026-11-03-heldout2-freeze-001'),('T3','2026-11-04-t3-eval-001','score_t3_arms.py','2026-11-04-t3-freeze-001')]:
        base=root/'output/action-recognition'/folder;source=track(base/script,'scoring-source')
        spec=importlib.util.spec_from_file_location('readonly_'+batch,source);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        if restored:
            mod.PULL=restored/('phone-'+batch.lower());mod.WATCH=restored/('watch-'+batch.lower())
        freeze=load('output/action-recognition/'+freeze_name+'/freeze.json')
        keys=['joint','phone','watch'] if batch=='T2' else ['9-joint','9-phone','9-watch','8-joint','8-phone','8-watch']
        missing_raw=[(mod.PULL/zname).as_posix() for part,sid,zname in mod.ROSTER if not (mod.PULL/zname).is_file()]
        raw_available=not missing_raw and mod.WATCH.is_dir()
        models={}
        for key in keys:
            path=track(root/'output/action-recognition'/freeze_name/('model-'+key+'.joblib'),'frozen-estimator')
            expected=freeze.get('arms',{}).get(key,{}).get('model_sha256')
            if expected:assert sha(path)==expected,'Frozen model SHA mismatch'
            hash_checks.append(dict(batch=batch,arm=key,sha256=sha(path),prior_hash_match=(sha(path)==expected) if expected else None,prior_digest_available=expected is not None))
            models[key]=joblib.load(path) if raw_available else None
        rows=[];sessions=[]
        for part,sid,zname in (mod.ROSTER if raw_available else []):
            zpath=track(mod.PULL/zname,'raw-phone-bundle');phone=mod.read_phone(zpath)
            watches=sorted(mod.WATCH.glob('imu_joint_bridge_%s*.jsonl'%zname.split('_')[1].split('-')[0]));assert len(watches)==1
            wrist=mod.read_watch(track(watches[0],'raw-watch-log'))
            ep=track(mod.RECORDS/sid/'events.jsonl','cue-record')
            ev=[json.loads(s) for s in ep.read_text(encoding='utf-8').splitlines() if s.strip()]
            start=next(e['wall_ms'] for e in ev if e['kind']=='run_start')
            slots=[e for e in ev if e['kind']=='cue_slot_start'];ends=[e for e in ev if e['kind']=='cue_slot_end']
            rates={k:float((len(t)-1)/(t[-1]-t[0])) for k,(t,x) in phone['channels'].items()}
            sessions.append(dict(part=part,sid=sid,targets=len(slots),closed=len(ends),phone_rate_hz=rates,run_start_wall_ms=start,freeze_created_utc=freeze['created_utc']))
            for slot in slots:
                _,aug,quality=mod.features_for(phone,wrist,slot,start,1.)
                label=table[part,slot['step_id']]['label']
                rows.append(dict(part=part,sid=sid,step_id=slot['step_id'],label=label,label8='cabinet' if label in ('open_cabinet','close_cabinet') else label,cue_slot_start_wall_ms=slot['wall_ms'],window_wall_ms=[slot['wall_ms']+1000,slot['wall_ms']+4000],augmented=aug,quality=quality))
        reference=json.loads(track(base/('t2-arms-eval.json' if batch=='T2' else 't3-arms-eval.json'),'historical-predictions').read_text(encoding='utf-8'))
        if not raw_available:
            rows=[dict(r) for r in reference['events']]
            print(batch,'original ZIP paths absent; independently recount stored event predictions, no raw-replay claim',flush=True)
        assert len(rows)==71 and len({r['sid']+'/'+r['step_id'] for r in rows})==71
        for key,bundle in models.items():
            if bundle is None:continue
            cols=bundle['columns'];ok=[r for r in rows if all(c in r['augmented'].get(d,{}) for d,c in cols)]
            X=np.array([[r['augmented'][d][c] for d,c in cols] for r in ok])
            for r,pred in zip(ok,bundle['model'].predict(X)):r['pred_'+key]=str(pred)
        previous={(r['sid'],r['step_id']):r for r in reference['events']};mismatch=[]
        for r in rows:
            old=previous[(r['sid'],r['step_id'])]
            for key in ['label']+['pred_'+k for k in keys]:
                if r.get(key)!=old.get(key):mismatch.append(dict(sid=r['sid'],step_id=r['step_id'],field=key,new=r.get(key),old=old.get(key)))
        write(out/(batch+'-prediction-comparison.json'),dict(mismatches=mismatch,count=len(mismatch) if raw_available else None,raw_replay_performed=raw_available,scope='raw predictor replay' if raw_available else 'stored-event recount only; historical event agreement is not independently tested'))
        assert not mismatch,'STOP: frozen predictor replay mismatch'
        if raw_available:write(out/(batch+'-event-features.json'),dict(rows=[{k:v for k,v in r.items() if not k.startswith('pred_')} for r in rows],window_offset_s=1.0,window_width_s=3.0,scaler_fitted=False,model_training_performed=False))
        result={};pairs={}
        for task in ([9] if batch=='T2' else [9,8]):
            labs=LABELS if task==9 else ['cabinet']+[x for x in LABELS if x not in ('close_cabinet','open_cabinet')]
            truth='label' if task==9 else 'label8';prefix='' if batch=='T2' else str(task)+'-'
            result[str(task)]={arm:metrics(rows,'pred_'+prefix+arm,labs,truth) for arm in ('joint','phone','watch')}
            comparisons=[dict(arm_a=x,arm_b=y,**paired(rows,'pred_'+prefix+x,'pred_'+prefix+y,truth)) for x,y in itertools.combinations(('joint','phone','watch'),2)];holm(comparisons);pairs[str(task)]=comparisons
        batches[batch]=dict(tasks=result,paired=pairs,recording_sessions=6,events=71,evaluation_status='freeze declares evaluation specified before this batch; earlier batch results already known')
        raw_audits[batch]=dict(sessions=sessions,predictions=[{k:v for k,v in r.items() if k not in ('augmented','quality')} for r in rows],trained_models=0,features_rebuilt=raw_available,missing_raw_paths=missing_raw)
        write(out/(batch+'-raw-replay.json'),raw_audits[batch])
        print(batch,'counts independently recomputed; raw replay:',raw_available,flush=True)
    # Original T is the expanded-D second look, not a new independent confirmation.
    old=load('output/action-recognition/2026-11-03-action-freeze-001/run/fixed-results.json')
    batches['T']=dict(tasks={'9':{arm:dict(accuracy=v['metrics']['accuracy'],wilson95=v['metrics']['accuracy_wilson95']['bounds'],macro_f1=v['metrics']['macro_f1']) for arm,v in old['device_arms'].items()}},recording_sessions=6,events=71,evaluation_status='expanded-development second look; D expanded after inspecting T bed confusion',historical_primary=old['confirmatory_result']['metrics']['accuracy'])
    rows=[dict(part=r['part'],label=r['label'],pred_joint=r['pred_joint'],pred_phone=r['pred_phone'],pred_watch=r['pred_watch']) for r in raw_audits['T2']['predictions']]+[dict(part=r['part'],label=r['label'],pred_joint=r['pred_9-joint'],pred_phone=r['pred_9-phone'],pred_watch=r['pred_9-watch']) for r in raw_audits['T3']['predictions']]
    combined={arm:metrics(rows,'pred_'+arm) for arm in ('joint','phone','watch')};cp=paired(rows,'pred_joint','pred_phone')
    r7=load('output/joint-privacy/2026-11-04-run007b-result-001/result.json');c7=load('output/joint-privacy/2026-11-01-eightvisit007-confirmatory-001/contract.json')
    r8=load('output/joint-privacy/2026-11-04-run008-newplace-negcontrol-001/result.json');c8=load('output/joint-privacy/2026-11-04-run008-newplace-negcontrol-001/contract.json')
    assert sha(root/'output/joint-privacy/2026-11-01-eightvisit007-confirmatory-001/contract.json')==r7['contract_sha256']
    assert sha(root/'output/joint-privacy/2026-11-04-run008-newplace-negcontrol-001/contract.json')==r8['contract_sha256']
    visits={}
    for name,v in r7['visits'].items():
        g=v['by_gate']['0.30'];visits[name]=dict(unique=ratio(g['unique'],v['struct_valid']),multi=g['multi'],missing=g['missing'],median_xyz=g['median_xyz'])
        assert g['unique']==v['struct_valid'] and g['multi']==0
    assert all(r7['V2'].values()) and all(r7['V3'].values())
    sensitivity=all(v['by_gate'][gate]['unique']==v['by_gate']['0.30']['unique'] and v['by_gate'][gate]['multi']==0 for v in r7['visits'].values() for gate in v['by_gate'])
    n8=dict(N1=ratio(r8['N1']['frames_producing_candidate'],r8['N1']['frames']),N2=ratio(r8['N2']['unique'],r8['N2']['struct_valid']),N3_distances_m=r8['N3']['distances_m'],N4_radius_m=r8['N4']['measured_radius_from_sensor_m'],N4_radius_required_m=c8['p_new']['pool_entry_conditions']['distance_from_sensor_min_m'],N4_radius_condition_met=r8['N4']['radius_condition_met'],reported_verdict=r8['verdict'],interpretation='N1-N3 pass; N4 radius eligibility not met. A conditional close-range stand, not full eligibility pass.')
    assert n8['N4_radius_condition_met']==(n8['N4_radius_m']>=n8['N4_radius_required_m'])
    radar=dict(run007b=dict(frames=r7['frames'],visits=visits,empty_pre=ratio(r7['V1prime']['empty_pre']['frames_producing_candidate'],r7['V1prime']['empty_pre']['frames']),empty_post=ratio(r7['V1prime']['empty_post']['frames_producing_candidate'],r7['V1prime']['empty_post']['frames']),height_sensitivity_gates=len(c7['sensitivity_gate_minimum_z_span_m']),sensitivity_identical=sensitivity,reported_verdict=r7['verdict'],station_name_mapping='A/C exchanged relative to tape labels; do not use literal layout identity'),run008=n8,scope='stand-window radar candidate availability, independent of phone/watch classification; no simultaneous tri-device experiment')
    for v in visits.values():v.pop('median_xyz',None)
    auto_base='output/prospective-space/2026-11-01-run007b-auto-interface-001/'
    if (root/auto_base/'verification.json').is_file():
        auto=load(auto_base+'run/results.json');prefix=load(auto_base+'prefix-results.json');verified=load(auto_base+'verification.json')
        radar['automatic_interface']=dict(frames=auto['frames'],event_count=auto['automatic_event_count'],matched_visits=ratio(auto['matched_declared_visits'],8),duration_median_s=auto['duration_median_s'],groups={k:v['groups'] for k,v in auto['grouping'].items()},relation_metrics={k:v['visit_relations'] for k,v in auto['grouping'].items()},spatial_counterfactual={k:v['spatial_counterfactual'] for k,v in auto['grouping'].items()},prefix_metrics={k:{f:x for f,x in v.items() if f!='queries'} for k,v in prefix['methods'].items()},replay_files=len(verified['replay']),post_audit_exploratory=True,scope=auto['stage_scope'],source_sha256=sha(root/auto_base/'run/results.json'))
        radar['automatic_interface']['candidate_frame_counts']=auto['candidate_frame_counts']
        channel={}
        for name,g in auto['grouping'].items():
            expected=sum(k*(k-1)//2 for k in g['groups']['cluster_sizes']);actual=g['labels_only_counterfactual']['fp'];assert expected==actual
            channel[name]=dict(expected_pairs=expected,observed_relabelled_false_pairs=actual)
        radar['automatic_interface']['label_channel_consistency_check']=dict(methods=channel,scope='algebraic identity under fixed predictions; excluded from negative-control evidence')
    sensitivity_base='output/research-sync/2026-11-01-restored-raw-and-simulation-closeout-001/radar-sensitivity/'
    if (root/sensitivity_base/'results.json').is_file():
        sen=load(sensitivity_base+'results.json');radar['post_audit_sensitivity']=dict(events=[{k:v for k,v in r.items() if k!='intervals'} for r in sen['events']],grouping=sen['complete_linkage'],scope=sen['warning'],main_settings_changed=False)
    base='output/prospective-space/2026-10-30-simulation-abstention-and-action-plan-001/six-family-geometry-library-001/'
    simulation={}
    for stage,rel in [('partial','partial-candidate-matching-001/run/test-qualified-summary.json'),('count_penalty','count-penalty-and-layout-classes-001/run/test-summary.json'),('group_errors','group-error-propagation-001/run/test-summary.json')]:
        x=load(base+rel)
        selected=[r for r in x.get('rows',[]) if r.get('cohort')=='all' and (stage!='count_penalty' or r.get('selected_lambda'))]
        simulation[stage]=dict(source_sha256=sha(root/base/rel),independent_unit=x.get('independent_unit'),rows=selected,export_scope='all-house cohort only; count-penalty keeps the development-selected lambda; no test-score filtering',scope={k:v for k,v in x.items() if k not in ('rows','query_coverage') and not isinstance(v,(dict,list))})
        if stage=='count_penalty':simulation[stage]['primary_strata']=[r for r in x['rows'] if r.get('cohort') in ('all','singleton','alias') and r.get('selected_lambda') and r.get('visits')==32 and r.get('structure')=='brownian' and r.get('sigma')==.5]
    integration_base='output/prospective-space/2026-11-01-auto-group-ranking-closeout-001/'
    if (root/integration_base/'report-facts.json').is_file():
        fact=load(integration_base+'report-facts.json');v=load(integration_base+'verification.json')
        simulation['automatic_group_ranking']=dict(**fact,validation=dict(replay_files=len(v['replay_files']),brute_force_checks=len(v['brute_force_probes']),ratio_checks=v['ratio_objects_checked'],input_changes=v['input_changes']),source_sha256=sha(root/integration_base/'report-facts.json'))
    rates=[v for batch in raw_audits.values() for s in batch['sessions'] for v in s['phone_rate_hz'].values()]
    snapshot=dict(schema='current-evidence-snapshot-v1',updated_client_date='2026-11-01',batch_labels_are_not_verified_calendar_dates=True,batches=batches,combined_T2_T3=dict(events=142,recording_sessions=12,metrics=combined,joint_vs_phone=cp,scope='same person and room; descriptive pooling across batch-specific frozen predictors'),radar=radar,simulation=simulation,phone_measured_rate_hz_range=[min(rates),max(rates)] if rates else None,action_raw_replay_available={k:v['features_rebuilt'] for k,v in raw_audits.items()},limitations=['Cue-declared labels; execution unverified.','Physical clocks and radar/IMU joins remain unaccepted.','T is a second look; T2 and T3 follow earlier batch feedback.','8-class and 9-class tasks must be shown together; task coarsening is not algorithmic improvement.','T3 model binaries have current SHA inventories, but no binary digest field was found in the original T3 freeze JSON.','Event-level intervals and tests are descriptive; events share sessions.','When original ZIP paths are unavailable, only stored event predictions are independently recounted; raw-feature replay is not claimed.'],flags=FLAGS)
    if restored:
        assert all(snapshot['action_raw_replay_available'].values()),'Restored mode requires complete original replay'
        snapshot['restored_originals']=dict(files=restored_count,bytes=restored_bytes,all_manifest_sha256_match=True)
        snapshot['limitations'][-1]='Originals restored and verified; raw features and frozen predictors replayed without retraining. Historical unavailable-path statement superseded.'
    snapshot['site_data_mode']='versioned exported snapshot; not a live paper-ledger reader'
    write(Path(a.snapshot),snapshot)
    for item in inventory.values():assert sha(item['path'])==item['sha256'],'Input changed'
    write(out/'input-sha256.json',dict(scope='Only listed inputs verified; no claim about unread files',files=list(inventory.values()),unchanged=True,model_checks=hash_checks))
    print('snapshot exported; models trained: 0; inputs:',len(inventory),flush=True)

if __name__=='__main__':main()
