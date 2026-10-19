import unittest
import numpy as np
from analysis.joint_privacy.attack import _probabilities,run_attack
from analysis.joint_privacy.demo import fixture
from analysis.joint_privacy.evaluation import evaluate

class ReviewContracts(unittest.TestCase):
    def test_target_time_cannot_use_delayed_probability(self):
        rows=[{'window_end_s':1.,'available_s':2.95,'p_walk':.3}]
        self.assertIsNone(_probabilities(rows,[1.5],3.,availability_mode='target_time'))
        np.testing.assert_array_equal(_probabilities(rows,[1.5],3.,availability_mode='prefix_retrospective'),[.3])

    def test_clock_error_sets_minimum_circular_shift(self):
        from analysis.joint_privacy.activity import minimum_shift_samples
        self.assertEqual(minimum_shift_samples(.5,.25),3)

    def test_symmetric_control_keeps_wrist_fixed(self):
        from analysis.joint_privacy.activity import paired_activity_probabilities
        p=np.arange(12).reshape(4,3);w=np.arange(8).reshape(4,2);calls=[]
        def predictor(x):calls.append(x.copy());return np.full(len(x),.5)
        result=paired_activity_probabilities(p,w,predictor,shift_samples=2,target_end_s=[1,2,3,4],
            availability_s=[1.1,2.1,3.1,4.1],budget_s=4.1,clock_uncertainty_s=.1)
        self.assertIn('shifted_phone',result);self.assertEqual(len(calls),3)
        np.testing.assert_array_equal(calls[2][:,:3],np.roll(p,2,axis=0))
        np.testing.assert_array_equal(calls[2][:,3:],w)

    def test_near_full_roll_is_also_a_weak_shift(self):
        from analysis.joint_privacy.activity import paired_activity_probabilities
        p=np.ones((8,1));w=p.copy()
        with self.assertRaises(ValueError):
            paired_activity_probabilities(p,w,lambda f:np.full(len(f),.5),shift_samples=7,
                target_end_s=np.arange(8)*.25,availability_s=np.arange(8)*.25,
                budget_s=2.,clock_uncertainty_s=.5)

    def test_model_tail_and_probability_mode_are_disclosed(self):
        a,ref=fixture();r=run_attack(a);report=evaluate(r,ref)
        self.assertIn('probability_time_mode',r)
        self.assertIn('model_unscored_tail_s',report)
        self.assertIn('phone_misaligned',r['variants'])

if __name__=='__main__':unittest.main()
