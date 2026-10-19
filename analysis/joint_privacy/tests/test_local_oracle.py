"""Analytic partial-reference contracts: unknown and markers never become still."""
import copy,importlib.util,json,subprocess,sys,unittest
READY=importlib.util.find_spec('analysis.joint_privacy.local_oracle') is not None
if READY:from analysis.joint_privacy.local_oracle import evaluate_local_segments

def fixture():
    t=[.5,1.5,2.5,3.5,4.5,5.5];v=[[1.,0.]]*6
    a={'synthetic':True,'status':'synthetic','budget_s':6.,'observation_start_s':0.,
       'center_times_s':t,'target_ends_s':[1.,2.,3.,4.,5.,6.],
       'phone_velocities':v,'gate_policy':{'mode':'soft'},
       'variants':{'phone':{'velocities':copy.deepcopy(v),'gate_values':[1.]*6}}}
    r={'schema_version':1,'reference_source_id':'SYNTHETIC-MANUAL', 'time_resolution_s':.01,
       'timing_support_accepted':True,'interval_basis':'declared_common_interiors',
       'maximum_center_gap_s':1.01,
       'intervals':[{'id':'still','start_s':0.,'end_s':3.,'activity':'nonwalk'},
                    {'id':'walk','start_s':3.,'end_s':6.,'activity':'walk'}],
       'excluded_intervals_s':[[2.8,3.2]]}
    return a,r

class Presence(unittest.TestCase):
    def test_module_exists(self):self.assertTrue(READY,'local_oracle module missing')

@unittest.skipUnless(READY,'module not yet implemented')
class LocalOracle(unittest.TestCase):
    def test_marker_intersection_rejects_entire_targets_and_keeps_known_fragments(self):
        a,r=fixture();v=evaluate_local_segments(a,r)
        self.assertEqual(v['eligible_target_indices'],[0,1,4,5])
        self.assertEqual(v['excluded_indices']['marker_overlap'],[2,3])
        self.assertEqual([x['source_indices'] for x in v['segments']],[[0,1],[4,5]])

    def test_each_fragment_has_analytic_baseline_and_oracle_without_global_path(self):
        a,r=fixture();v=evaluate_local_segments(a,r);s,w=v['segments']
        self.assertEqual(s['phone_model_path_m'],1.);self.assertEqual(s['oracle_model_path_m'],0.)
        self.assertEqual(w['phone_model_path_m'],1.);self.assertEqual(w['oracle_model_path_m'],1.)
        self.assertEqual(s['local_phone_positions'],[[0.,0.],[1.,0.]])
        self.assertEqual(w['local_phone_positions'],[[0.,0.],[1.,0.]])
        self.assertIsNone(v['global_trajectory']);self.assertIsNone(v['aggregate_path_m'])
        self.assertEqual(v['observation_budget_s'],6.);self.assertFalse(v['joint_result'])

    def test_unknown_and_uncovered_do_not_turn_into_nonwalk(self):
        a,r=fixture();r['excluded_intervals_s']=[];r['intervals'][0]['activity']='unknown'
        v=evaluate_local_segments(a,r)
        self.assertEqual(v['eligible_target_indices'],[3,4,5]);self.assertEqual(len(v['segments']),1)
        self.assertEqual(v['excluded_indices']['unknown_or_uncovered'],[0,1,2])
        r['intervals']=r['intervals'][1:];self.assertEqual(evaluate_local_segments(a,r)['eligible_target_indices'],[3,4,5])

    def test_unverified_reference_timing_returns_no_oracle(self):
        a,r=fixture();r['timing_support_accepted']=False;v=evaluate_local_segments(a,r)
        self.assertEqual(v['status'],'unverified_reference_timing');self.assertEqual(v['segments'],[])

    def test_unknown_velocity_changes_never_bridge_fragments(self):
        a,r=fixture();x=evaluate_local_segments(a,r);a['phone_velocities'][2]=[1000.,1000.]
        a['variants']['phone']['velocities'][2]=[1000.,1000.]
        y=evaluate_local_segments(a,r);self.assertEqual(x['segments'],y['segments'])

    def test_single_full_target_does_not_claim_displacement_measurement(self):
        a,r=fixture();r['intervals']=[{'id':'one','start_s':0.,'end_s':1.,'activity':'walk'}];r['excluded_intervals_s']=[]
        v=evaluate_local_segments(a,r);self.assertEqual(v['eligible_target_indices'],[0])
        self.assertEqual(v['segments'],[]);self.assertEqual(v['excluded_indices']['singleton'],[0])

    def test_gap_breaks_integration_even_for_adjacent_input_indices(self):
        a,r=fixture();a['center_times_s']=[.5,1.5,2.5,6.5,7.5,8.5];a['target_ends_s']=[1.,2.,3.,7.,8.,9.];a['budget_s']=9.
        r['intervals']=[{'id':'all','start_s':0.,'end_s':9.,'activity':'walk'}];r['excluded_intervals_s']=[]
        self.assertEqual([s['source_indices'] for s in evaluate_local_segments(a,r)['segments']],[[0,1,2],[3,4,5]])

    def test_stateful_gate_is_not_reset_at_reference_gaps(self):
        a,r=fixture();a['gate_policy']={'mode':'hysteresis','on':.8,'off':.2}
        with self.assertRaisesRegex(ValueError,'soft'):evaluate_local_segments(a,r)

    def test_schema_values_order_and_ids_are_validated(self):
        bad=[]
        a,r=fixture();r['maximum_center_gap_s']=True;bad.append((a,r))
        a,r=fixture();r['intervals'][0]['end_s']=float('nan');bad.append((a,r))
        a,r=fixture();r['intervals'][1]['id']='still';bad.append((a,r))
        a,r=fixture();r['intervals'][1]['start_s']=2.;bad.append((a,r))
        a,r=fixture();r['regions']={};bad.append((a,r))
        a,r=fixture();r['excluded_intervals_s']=[[2.,1.]];bad.append((a,r))
        a,r=fixture();a['target_ends_s'][-1]=6.1;bad.append((a,r))
        for a,r in bad:
            with self.subTest(r=r),self.assertRaises(ValueError):evaluate_local_segments(a,r)

    def test_input_is_unchanged_and_reference_not_injected_into_attack(self):
        a,r=fixture();aa=copy.deepcopy(a);rr=copy.deepcopy(r);evaluate_local_segments(a,r)
        self.assertEqual(a,aa);self.assertEqual(r,rr);self.assertNotIn('oracle_diagnostic',a['variants'])

    def test_attack_import_does_not_import_local_reference_tool(self):
        p=subprocess.run([sys.executable,'-c',"import sys;import analysis.joint_privacy.attack;assert 'analysis.joint_privacy.local_oracle' not in sys.modules"],capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)

if __name__=='__main__':unittest.main()
