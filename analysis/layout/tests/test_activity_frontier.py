"""Boundary and physical counterexamples for the activity-frontier revision."""
import unittest
import numpy as np
from analysis.layout import sim_motion as motion

class SimulationContinuityTests(unittest.TestCase):
    def test_action_gate_cannot_pass_without_cabinet_recognition(self):
        from analysis.layout.simulation_validation import required_actions_available
        per={name:{'recall':1.} for name in ['walk','other','seated','lying']}
        per['cabinet']={'recall':0.}
        self.assertFalse(required_actions_available(per))

    def test_clean_motion_reintegrates_without_a_learned_frontend(self):
        from analysis.layout.simulation_validation import physical_report
        report=physical_report(motion.generate(add_noise=False))
        self.assertTrue(report['passed'],report)

    def test_C2_transition_has_zero_endpoint_acceleration(self):
        self.assertAlmostEqual(motion.smooth_dd(0.0, 1.0), 0.0)
        self.assertAlmostEqual(motion.smooth_dd(1.0, 1.0), 0.0)

    def test_sit_posture_does_not_flip_its_yaw_basis(self):
        m=motion.Motion()
        matrices=[motion.device_pose(float(t),m.state(float(t)))[1] for t in np.linspace(9,9.8,801)]
        angle=[np.arccos(np.clip((np.trace(a.T@b)-1)/2,-1,1)) for a,b in zip(matrices,matrices[1:])]
        self.assertLess(max(angle),np.deg2rad(2))

    def test_endpoint_second_derivative_is_correct(self):
        from analysis.layout.simulation_validation import pose_derivatives
        def pose(t):
            return np.array([2*t+1.5*t*t,0.,0.]),np.eye(3)
        for t in [0.0,0.4,1.0]:
            _,a,w=pose_derivatives(pose,t,1.0)
            np.testing.assert_allclose(a,[3.,0.,0.],atol=1e-5)
            np.testing.assert_allclose(w,0,atol=1e-9)

class EvidenceSpaceTests(unittest.TestCase):
    def test_unreached_coverage_keeps_room_in_denominator(self):
        from analysis.layout.activity_report import coverage_bounds
        rows=[{'scene':'a','budget_m':4.,'coverage':.5,'scores':{'0.5':{'full_point_hit':True}}},
              {'scene':'b','budget_m':4.,'coverage':.2,'scores':{'0.5':{'full_point_hit':False}}}]
        r=coverage_bounds(rows,.4)
        self.assertEqual((r['n_rooms'],r['reached'],r['unreached']),(2,1,1))
        self.assertEqual((r['success_lower'],r['success_upper']),(.5,1.))

    def test_completed_window_does_not_need_an_extra_endpoint_sample(self):
        from analysis.layout import action_model as am
        t=np.arange(0.,4.,.02)
        a=np.tile([0.,0.,9.81],(len(t),1));g=np.zeros_like(a)
        class Classifier:
            def predict(self,x):return np.array(['lying']*len(x))
        features=am.features_at(t,a,t,g,1.)
        model={'keys':sorted(features),'classifier':Classifier()}
        result=am.predict_timeline(model,t,a,t,g,budget_s=4.)
        self.assertEqual(len(result['windows']),1)
        self.assertEqual(result['windows'][0]['end_s'],4.)

    def test_no_threshold_without_following_grid_confirmation(self):
        from analysis.layout.evidence_space import stable_threshold
        self.assertIsNone(stable_threshold([{'coverage':.9,'success_rate':1.}]))

    def test_measured_distance_calibration_never_fits_evaluation_intervals(self):
        from analysis.layout.activity_diagnostics import fit_distance_scale
        with self.assertRaises(ValueError):fit_distance_scale([2.],[3.],['same'],['same'])

    def test_broad_coverage_can_leave_two_incompatible_static_layouts(self):
        from analysis.layout.activity_diagnostics import ambiguity_witness
        r=ambiguity_witness()
        self.assertGreater(r['coverage'],.65)
        self.assertEqual(r['body_clearance_m'],.15)
        self.assertGreater(r['worst_case_center_error_lower_bound_m'],.5)

    def test_interval_requires_endpoint_intersection(self):
        from analysis.layout.evidence_space import intersect_interval
        r=intersect_interval((0,1),(2,2.1))
        self.assertEqual(r["status"],"conflict")
        self.assertIsNone(r["width_m"])

    def test_singleton_is_not_an_empty_set(self):
        from analysis.layout.evidence_space import intersect_interval
        self.assertEqual(intersect_interval((0,1),(1,2))["status"],"singleton")

    def test_center_accuracy_and_interval_resolution_are_distinct(self):
        from analysis.layout.evidence_space import interval_accuracy
        r=interval_accuracy((0,1))
        self.assertEqual(r["width_m"],1)
        self.assertEqual(r["minimax_center_error_m"],.5)

    def test_unseen_objects_remain_in_latent_world(self):
        from analysis.layout.evidence_space import make_bank,infer
        objects={"bed":(.8,1.6),"desk":(.4,.8),"cab":(.4,.6),"chair":(.4,.4)}
        banks=make_bank((3.,4.),objects,spacing=.25)
        r=infer((3.,4.),banks,np.empty((0,2)),[],use_path=False,use_actions=False)
        self.assertEqual(set(r["objects"]),set(objects))

    def test_effective_evidence_is_not_repeated_same_contact(self):
        from analysis.layout.evidence_space import containment_interval
        one=containment_interval([1.],1.,.1)
        many=containment_interval([1.]*8,1.,.1)
        self.assertEqual(one,many)
        wider=containment_interval([1.,1.8],1.,.1)
        self.assertLess(wider[1]-wider[0],one[1]-one[0])

    def test_coverage_has_no_truth_layout_input(self):
        from analysis.layout.evidence_space import spatial_coverage
        c=spatial_coverage(np.array([[1,1],[2,1]]),(3,3),radius=.25,grid=.05)
        self.assertGreater(c,0)
        self.assertLess(c,1)

if __name__=="__main__":unittest.main()
