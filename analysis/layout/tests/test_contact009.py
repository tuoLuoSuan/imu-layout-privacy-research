import unittest
import numpy as np


class ContactContractTests(unittest.TestCase):
    def test_phone_inside_bed_maps_to_foot_relative_template(self):
        from analysis.layout.contact_contract import boxes_from_contacts, CONTRACT
        contacts={'lying':{'xy':[2.,2.65],'heading':[0.,1.]},'seated':{'xy':[1.2,1.5],'heading':[-1.,0.]},'cabinet':{'xy':[1.15,.5],'heading':[-1.,0.]}}
        sizes={'bed':[1.5,2.],'chair':[.44,.44],'desk':[.6,1.2],'cab':[.6,1.]}
        boxes=boxes_from_contacts(contacts,sizes)
        np.testing.assert_allclose(boxes['bed'],[1.25,2.,2.75,4.])
        np.testing.assert_allclose(boxes['cab'],[0.,0.,.6,1.],atol=1e-10)
        np.testing.assert_allclose(boxes['chair'],[.98,1.28,1.42,1.72])
        self.assertEqual(CONTRACT['lying_phone_from_foot_m'],.65)

    def test_contract_rejects_unobserved_truth_or_instance_metadata(self):
        from analysis.layout.contact_contract import validate_contact
        with self.assertRaises(ValueError):validate_contact({'xy':[1,2],'heading':[0,1],'true_box':[0,0,2,3]})
        with self.assertRaises(ValueError):validate_contact({'xy':[1,2],'heading':[0,0]})

    def test_calibration_uses_declared_separate_distance(self):
        from analysis.layout.contact_contract import distance_scale
        self.assertAlmostEqual(distance_scale(np.array([[0.,0.],[6.,0.]]),10.),10/6)
        with self.assertRaises(ValueError):distance_scale(np.zeros((2,2)),10.)

    def test_start_is_a_device_position_and_translation_is_not_double_applied(self):
        from analysis.layout.contact_contract import register
        p=np.array([[10.,20.],[11.,20.]]);s=np.array([.8,3.8])
        out=register(p,90.,s)
        np.testing.assert_allclose(out[0],s)
        np.testing.assert_allclose(out[1],[.8,4.8])

    def test_zupt_replays_bracketed_motion_without_true_positions(self):
        from analysis.layout.inertial_replay import integrate_bracketed
        t=np.linspace(0,2,241);a=np.c_[np.cos(np.pi*t),np.zeros_like(t)]
        p=integrate_bracketed(t,a)
        self.assertLess(abs(p[-1,0]),1e-3)
        self.assertGreater(p[:,0].max(),.19)
        np.testing.assert_allclose(p,integrate_bracketed(t,a+[.2,-.1]),atol=1e-12)

    def test_rest_calibration_does_not_use_moving_acceleration_as_gravity(self):
        from analysis.layout.inertial_replay import rest_attitude
        t=np.arange(0,4,.01);a=np.tile([0.,0.,9.81],(len(t),1));g=np.tile([.001,-.002,.003],(len(t),1))
        a[t>=2,0]=3.;r=rest_attitude(t,a,g,rest_s=1.5)
        np.testing.assert_allclose(r,np.tile(np.eye(3),(len(t),1,1)),atol=1e-10)

    def test_joint_cabinet_source_is_watch_and_missing_watch_cannot_reuse_phone(self):
        from analysis.layout.watch_cabinet import fuse
        phone={'runs':[['cabinet',2,6],['seated',8,12]]}
        self.assertEqual(fuse(phone,{'runs':[]})['runs'],[['seated',8,12]])
        self.assertEqual(fuse(phone,{'runs':[['cabinet',13,16]]})['runs'],[['seated',8,12],['cabinet',13,16]])
        self.assertEqual(fuse({'runs':[['seated',8,12]]},{'runs':[['cabinet',9,11]]})['runs'],[['seated',8,9],['cabinet',9,11],['seated',11,12]])

    def test_watch_window_maturity_does_not_borrow_future_samples(self):
        from analysis.layout.watch_cabinet import detect
        t=np.arange(0,12,1/16.7);a=np.c_[np.sin(t),np.zeros(len(t)),np.full(len(t),9.81)];a[t>8]=[8,3,2]
        before=detect(t,a,budget_s=8)['windows'];full=[w for w in detect(t,a)['windows'] if w['available_s']<=8]
        self.assertEqual(before,full)

    def test_support_wall_follows_contact_direction_not_the_nearest_other_wall(self):
        from analysis.layout.contact_contract import support_gap
        self.assertAlmostEqual(support_gap([.1,1,.7,2],[-1,0],[4,5]),.1)
        self.assertAlmostEqual(support_gap([.1,1,.7,2],[1,0],[4,5]),3.3)

    def test_storage_operation_face_uses_depth_axis_at_room_corner(self):
        from analysis.layout.sim_handset import targets
        scene={'W':4.,'L':5.,'gt':{'bed#0':np.array([2.5,2.8,3.9,4.9]),'cab#0':np.array([.14,.08,.74,1.08]),'desk#0':np.array([.14,1.2,.74,2.5]),'chair#0':np.array([1.,1.5,1.44,1.94])}}
        event=next(e for e in targets(scene) if e[0]=='cabinet')
        np.testing.assert_allclose(event[1],[1.29,.58],atol=1e-10)
        np.testing.assert_allclose(event[2],[-1.,0.])

    def test_known_room_frame_oracle_does_not_reestimate_global_yaw(self):
        from analysis.layout.contact_contract import decode
        c={'seated':{'xy':[1.2,1.5],'heading':[-1,0]},'cabinet':{'xy':[1.15,.5],'heading':[-1,0]},'lying':{'xy':[2.,2.65],'heading':[0,1]}}
        sizes={'bed':[1.5,2.],'chair':[.44,.44],'desk':[.6,1.2],'cab':[.6,1.]}
        p=decode([4.,5.],[2.,.4],np.array([[2.,.4],[2.,1.]]),c,sizes,yaw_candidates=[0.])
        self.assertEqual(p['yaw_deg'],0.)
        self.assertEqual(len(p['candidates']),1)

    def test_threshold_merge_includes_dense_budgets_and_rejects_duplicates(self):
        from analysis.layout.expansion10000 import merge_threshold_records
        row=lambda n: {'coverage':1.,'visits':n,'executable':True,'status':'ok','f1':1.,'whole':True}
        fine={'scene':'room-a','source_sha256':'abc','rows':[row(21)]}
        dense={'scene':'room-a','source_sha256':'abc','rows':[row(15),row(16)]}
        q=merge_threshold_records([fine,dense],'room-a','abc',[(1.,21),(1.,15),(1.,16)])
        self.assertEqual(set(q),{(1.,15),(1.,16),(1.,21)})
        with self.assertRaises(ValueError):merge_threshold_records([fine,fine],'room-a','abc',[(1.,21)])
        with self.assertRaises(ValueError):merge_threshold_records([fine,dense],'room-a','wrong',[(1.,21),(1.,15),(1.,16)])

    def test_full_coverage_threshold_requires_all_integers_and_does_not_assume_monotonicity(self):
        from analysis.layout.expansion10000 import full_coverage_threshold
        rows=[{'coverage':1.,'visits':n,'f1':.9,'f1_bootstrap_ci':[.88,.92],
               'whole_rate':(.81 if n==4 else .7),'whole_wilson_ci':[.79,.83]} for n in range(6)]
        r=full_coverage_threshold(rows,max_visits=5)
        self.assertEqual(r['first_empirical_whole80']['visits'],4)
        self.assertIsNone(r['first_whole_lower_ci80'])
        self.assertFalse(r['whole_passes_every_later_count'])
        with self.assertRaises(ValueError):full_coverage_threshold(rows[:-1],max_visits=5)


if __name__=='__main__':unittest.main()
