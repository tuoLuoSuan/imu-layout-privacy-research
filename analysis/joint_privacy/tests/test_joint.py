import ast,copy,importlib.util,json,tempfile,unittest
from pathlib import Path
import numpy as np

READY=importlib.util.find_spec('analysis.joint_privacy.attack') is not None
if READY:
    from analysis.joint_privacy.attack import run_attack
    from analysis.joint_privacy.inputs import fit_clock,watch_features,load_watch
    from analysis.joint_privacy.evaluation import evaluate,oracle_diagnostic
    from analysis.joint_privacy.demo import fixture

class ImplementationExists(unittest.TestCase):
    def test_new_joint_harness_exists(self):self.assertTrue(READY,'Separate joint attack/evaluation not implemented')

@unittest.skipUnless(READY,'New joint harness not implemented')
class JointContracts(unittest.TestCase):
    def test_task_origin_excludes_calibration_motion_and_rebases_paths(self):
        a,ref=fixture();a['observation_start_s']=3.
        r=run_attack(a)
        self.assertGreaterEqual(r['center_times_s'][0],3.5)
        self.assertEqual(r['variants']['phone']['positions'][0],[0.,0.])
        ref['reference_coverage_s']=[3.,9.]
        self.assertEqual(oracle_diagnostic(r,ref)['status'],'oracle_diagnostic_only')

    def test_unknown_clock_still_allows_phone_and_oracle_diagnosis(self):
        a,ref=fixture();a['clock_contract']=None
        r=run_attack(a)
        self.assertEqual(r['status'],'unverified_clock_pairing')
        self.assertEqual(set(r['variants']),{'phone'})
        self.assertEqual(oracle_diagnostic(r,ref)['status'],'oracle_diagnostic_only')

    def test_nested_reference_fields_are_not_silently_accepted(self):
        a,_=fixture();a['probability_provenance']['joint']['regions']=['R1']
        with self.assertRaises(ValueError):run_attack(a)

    def test_phone_joint_and_three_controls_are_distinct_outputs(self):
        attack,truth=fixture();r=run_attack(attack)
        self.assertEqual(set(r['variants']),{'phone','phone_gated','joint_gated','constant','shuffled','circular_shift','watch_misaligned','phone_misaligned'})
        p=r['gate_diagnostics'];self.assertAlmostEqual(p['joint_mean'],p['constant_mean'])
        self.assertEqual(sorted(p['joint_values']),sorted(p['shuffled_values']))
        self.assertEqual(sorted(p['joint_values']),sorted(p['circular_shift_values']))
        self.assertFalse(r['research_validated']);self.assertIsNone(r['walls'])

    def test_future_probability_and_velocity_cannot_change_prefix(self):
        attack,_=fixture();r=run_attack(attack);changed=copy.deepcopy(attack)
        changed['phone_predictions'].append({'center_s':99.,'target_end_s':99.5,'available_s':99.6,'vx':100.,'vy':80.})
        for values in changed['probability_streams'].values():
            values.append({'window_end_s':99.5,'available_s':99.6,'p_walk':.1})
        self.assertEqual(r,run_attack(changed))

    def test_truth_keys_and_unknown_keys_are_rejected_at_attack_boundary(self):
        attack,_=fixture()
        for key in ('truth','regions','radar','R1','unexpected'):
            bad=copy.deepcopy(attack);bad[key]={}
            with self.assertRaises(ValueError):run_attack(bad)

    def test_missing_or_untrained_real_probabilities_are_unknown_not_invented(self):
        attack,_=fixture();attack['synthetic']=False
        self.assertEqual(run_attack(attack)['status'],'unverified_probability_provenance')
        attack,_=fixture();attack['probability_streams']['joint']=[]
        self.assertEqual(run_attack(attack)['status'],'incomplete_probability_coverage')

    def test_stale_gate_is_not_carried_forever(self):
        attack,_=fixture();attack['probability_streams']['joint']=attack['probability_streams']['joint'][:1]
        self.assertEqual(run_attack(attack)['status'],'incomplete_probability_coverage')

    def test_gate_or_phone_prediction_available_after_budget_is_excluded(self):
        attack,_=fixture();attack['probability_streams']['joint'][-1]['available_s']=100.
        # Last gate may use the preceding <=1.5s causal gate; not the future value.
        one=run_attack(attack);attack['probability_streams']['joint'][-1]['p_walk']=.777
        self.assertEqual(one,run_attack(attack))
        attack,_=fixture()
        for row in attack['phone_predictions']:row['available_s']=100.
        self.assertEqual(run_attack(attack)['status'],'insufficient_phone_context')

    def test_record_support_is_enforced_by_attack(self):
        attack,_=fixture();attack['budget_s']=100.
        self.assertEqual(run_attack(attack)['status'],'outside_recorded_session')

    def test_pair_identity_cannot_be_inferred_from_nearby_filenames(self):
        attack,_=fixture();attack['probability_provenance']['joint']['paired_session_id']='other'
        self.assertEqual(run_attack(attack)['status'],'unverified_probability_provenance')

    def test_eval_requires_independent_alignment_for_region_scores(self):
        attack,truth=fixture();r=run_attack(attack);truth['alignment']=None
        report=evaluate(r,truth)
        self.assertEqual(report['spatial_status'],'unknown_coordinate_alignment')
        self.assertIsNone(report['spatial_metrics'])

    def test_oracle_stays_evaluation_only_and_uses_same_gate_policy(self):
        attack,truth=fixture();r=run_attack(attack);report=oracle_diagnostic(r,truth)
        self.assertEqual(report['gate_policy'],r['gate_policy'])
        self.assertEqual(report['status'],'oracle_diagnostic_only')
        self.assertNotIn('oracle',r['variants'])

    def test_region_reference_is_budgeted_and_never_fills_unknown_walls(self):
        attack,truth=fixture();r=run_attack(attack);report=evaluate(r,truth)
        self.assertEqual(report['spatial_status'],'region_evidence_only')
        self.assertIsNone(report['wall_error_m'])
        truth['region_events'].append({'time_s':100.,'region':'future'})
        self.assertEqual(report,evaluate(r,truth))

    def test_attack_dependencies_do_not_import_evaluation_or_truth(self):
        folder=Path(__file__).resolve().parents[1]
        for name in ('attack.py','inputs.py','activity.py','output.py','space.py','from_prefix.py','prepare.py'):
            tree=ast.parse((folder/name).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):imports=[n.name for n in node.names]
                elif isinstance(node,ast.ImportFrom):imports=[(node.module or '')]+[n.name for n in node.names]
                else:continue
                self.assertFalse(any('evaluation' in s or 'truth' in s for s in imports),(name,imports))

@unittest.skipUnless(READY,'New joint harness not implemented')
class InputContracts(unittest.TestCase):
    def test_primary_mismatch_shifts_wrist_features_before_joint_model(self):
        from analysis.joint_privacy.activity import paired_activity_probabilities
        p=np.arange(12).reshape(4,3);w=np.arange(8).reshape(4,2);calls=[]
        def predictor(x):calls.append(x.copy());return np.full(len(x),.5)
        paired_activity_probabilities(p,w,predictor,shift_samples=2,
            target_end_s=[1.,2.,3.,4.],availability_s=[1.1,2.1,3.1,4.1],budget_s=4.1,clock_uncertainty_s=0.)
        self.assertEqual(len(calls),3)
        np.testing.assert_array_equal(calls[0][:,:3],calls[1][:,:3])
        np.testing.assert_array_equal(calls[1][:,3:],np.roll(w,2,axis=0))

    def test_mismatch_is_built_only_inside_available_prefix(self):
        from analysis.joint_privacy.activity import paired_activity_probabilities
        p=np.ones((6,2));w=np.arange(6).reshape(6,1)/10
        predictor=lambda f:f[:,-1]
        options=dict(shift_samples=2,target_end_s=[1,2,3,4,5,6],availability_s=[1.1,2.1,3.1,4.1,5.1,6.1],budget_s=4.1,clock_uncertainty_s=0.)
        one=paired_activity_probabilities(p,w,predictor,**options)
        w[4:]=999;p[4:]=999
        two=paired_activity_probabilities(p,w,predictor,**options)
        for k in one:np.testing.assert_array_equal(one[k],two[k])

    def test_output_file_is_exclusive_and_data_escape_is_refused(self):
        from analysis.joint_privacy.output import write_json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'fresh/result.json';write_json(p,{'a':1},allowed_root=root)
            before=p.read_bytes()
            with self.assertRaises(FileExistsError):write_json(p,{'a':2},allowed_root=root)
            self.assertEqual(before,p.read_bytes())
            with self.assertRaises(ValueError):write_json(root.parent/'escape.json',{},allowed_root=root)

    def clock(self):
        return {'phone_id':'p','watch_id':'w','paired_session_id':'pair','mode':'cooperative_pre_task',
            'anchors':[{'watch_epoch_ms':1_000_000.,'phone_s':0.,'uncertainty_s':.05},
                       {'watch_epoch_ms':1_010_000.,'phone_s':10.,'uncertainty_s':.05}],
            'checks':[{'watch_epoch_ms':1_005_000.,'phone_s':5.,'uncertainty_s':.05}],
            'available_s':10.1,'valid_until_s':150.,'drift_bound_ppm':100.,'max_uncertainty_s':.25}

    def test_unknown_clock_and_future_calibration_do_not_align(self):
        with self.assertRaises(ValueError):fit_clock({})
        clock=fit_clock(self.clock());self.assertAlmostEqual(clock.map_ms(1_020_000.),20.)
        with self.assertRaises(ValueError):clock.require_budget(5.)
        with self.assertRaises(ValueError):clock.require_budget(151.)
        self.assertGreater(clock.uncertainty_s(120.),clock.uncertainty_s(10.))

    def test_clock_step_or_bad_independent_check_is_rejected(self):
        data=self.clock();data['checks'][0]['phone_s']=6.
        with self.assertRaises(ValueError):fit_clock(data)

    def test_anchor_uncertainty_is_propagated_when_extrapolated(self):
        clock=fit_clock(self.clock())
        self.assertGreater(clock.uncertainty_s(120.),1.)
        with self.assertRaises(ValueError):clock.require_budget(120.)
        data=self.clock();data['anchors'][1]['watch_epoch_ms']=data['anchors'][0]['watch_epoch_ms']
        with self.assertRaises(ValueError):fit_clock(data)

    def test_wrist_features_are_trailing_unitless_not_walk_probabilities(self):
        rows=[[i,i*60.,1.+.1*np.sin(i),0.,10.,'visible'] for i in range(40)]
        result=watch_features(rows,2.)
        self.assertTrue(result);self.assertNotIn('p_walk',result[0])
        scaled=[[r[0],r[1],r[2]*3,r[3]*3,r[4]*3,r[5]] for r in rows]
        two=watch_features(scaled,2.)
        self.assertAlmostEqual(result[-1]['norm_cv'],two[-1]['norm_cv'])
        changed=rows+[[40,9000.,999.,800.,777.,'visible']]
        self.assertEqual(result,watch_features(changed,2.))

    def test_unobserved_hidden_or_gapped_watch_window_is_not_filled(self):
        rows=[[i,i*60.,1.,0.,10.,'hidden'] for i in range(40)]
        self.assertEqual(watch_features(rows,2.),[])

if __name__=='__main__':unittest.main()
