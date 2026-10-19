"""Independent analytic fixtures for the existing evaluation-only code."""
import copy,unittest
from analysis.joint_privacy.evaluation import evaluate,oracle_diagnostic


def analytic_fixture():
    attack={'synthetic':True,'status':'synthetic_analytic_fixture','budget_s':4.5,'observation_start_s':0.,
        'center_times_s':[1.,2.,3.,4.],'target_ends_s':[1.5,2.5,3.5,4.5],
        'phone_velocities':[[1.,0.]]*4,'gate_policy':{'mode':'soft'},
        'variants':{'phone':{'positions':[[0.,0.],[1.,0.],[2.,0.],[3.,0.]],
                             'velocities':[[1.,0.]]*4,'gate_values':[1.]*4,'modeled_path_m':3.}}}
    reference={'schema_version':1,'reference_source_id':'SYNTHETIC-ANALYTIC-REFERENCE',
        'time_resolution_s':.01,'reference_coverage_s':[.5,4.5],'walk_intervals_s':[[2.,4.]],
        'region_events':[{'time_s':2.,'region':'R1'},{'time_s':3.,'region':'R2'}],
        'regions':{'R1':[-.1,-.1,1.1,.1],'R2':[1.4,-.1,2.1,.1],'R3':[2.5,-.1,3.1,.1]},
        'alignment':{'rotation_rad':0.,'translation_xy_m':[0.,0.],
                     'reference_source_id':'SYNTHETIC-INDEPENDENT-AXES','fit_used_this_test_output':False}}
    return attack,reference


class AnalyticEvaluation(unittest.TestCase):
    def test_fractional_target_overlap_and_trapezoid_have_known_result(self):
        a,r=analytic_fixture();oracle=oracle_diagnostic(a,r)
        self.assertEqual(oracle['gate_values'],[0.,.5,1.,.5])
        self.assertEqual(oracle['positions'],[[0.,0.],[.25,0.],[1.,0.],[1.75,0.]])
        self.assertEqual(oracle['modeled_path_m'],1.75);self.assertFalse(oracle['deployment_input'])

    def test_nonwalk_suppression_is_accompanied_by_walk_retention(self):
        a,r=analytic_fixture();m=evaluate(a,r)['temporal_metrics']
        self.assertEqual(m['phone']['modeled_distance_during_reference_nonwalk_m'],1.)
        self.assertEqual(m['phone']['modeled_distance_during_reference_walk_m'],2.)
        self.assertEqual(m['oracle_diagnostic']['modeled_distance_during_reference_nonwalk_m'],.25)
        self.assertEqual(m['oracle_diagnostic']['modeled_distance_during_reference_walk_m'],1.5)
        self.assertEqual(m['oracle_diagnostic']['walk_model_distance_retained_fraction'],.75)
        self.assertEqual(m['oracle_diagnostic']['walk_gate_suppression_fraction'],.25)

    def test_known_region_precision_recall_do_not_create_walls(self):
        a,r=analytic_fixture();m=evaluate(a,r)
        self.assertAlmostEqual(m['spatial_metrics']['phone']['precision'],2/3)
        self.assertEqual(m['spatial_metrics']['phone']['recall'],1.)
        self.assertAlmostEqual(m['spatial_metrics']['phone']['f1'],.8)
        self.assertEqual(m['spatial_metrics']['oracle_diagnostic']['f1'],1.)
        self.assertIsNone(m['wall_error_m']);self.assertFalse(m['research_validated'])

    def test_reference_missing_part_of_a_full_target_rejects_oracle(self):
        a,r=analytic_fixture();r['reference_coverage_s']=[1.,4.5]
        self.assertEqual(oracle_diagnostic(a,r)['status'],'reference_support_incomplete')

    def test_missing_coordinate_alignment_keeps_temporal_diagnosis_only(self):
        a,r=analytic_fixture();r['alignment']=None;m=evaluate(a,r)
        self.assertEqual(m['spatial_status'],'unknown_coordinate_alignment')
        self.assertIsNone(m['spatial_metrics']);self.assertIn('temporal_metrics',m)

    def test_reference_is_not_mutated_or_copied_into_attack(self):
        a,r=analytic_fixture();aa=copy.deepcopy(a);rr=copy.deepcopy(r)
        evaluate(a,r);self.assertEqual(a,aa);self.assertEqual(r,rr)
        self.assertNotIn('oracle_diagnostic',a['variants'])


if __name__=='__main__':unittest.main()
