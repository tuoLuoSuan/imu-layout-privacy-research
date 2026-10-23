import unittest
import numpy as np
from analysis.fixed_window_dev import core


class FixedWindowTests(unittest.TestCase):
    def test_window_uses_recording_start_not_first_sample_and_half_open_end(self):
        s=[[t,1.,2.,3.] for t in np.arange(0,60,.1)]
        a=core.fixed_window(s,[-.2,60.],20.,55.)
        self.assertAlmostEqual(a[0,0],19.8)
        self.assertTrue(np.all(a[:,0]+.2>=20.-1e-9))
        self.assertTrue(np.all(a[:,0]+.2<55.-1e-9))
        self.assertFalse(np.any(np.isclose(a[:,0],54.8)))

    def test_window_does_not_rezero_input_or_mutate_source(self):
        a=np.c_[np.arange(0,60,.01),np.ones((6000,3))];before=a.copy()
        b=core.fixed_window(a,[0.,60.],20.,55.)
        np.testing.assert_array_equal(a,before)
        self.assertAlmostEqual(b[0,0],20.)

    def test_window_rejects_short_recording_or_unsupported_interior_gap(self):
        s=np.c_[np.arange(0,60,.05),np.ones((1200,3))]
        with self.assertRaises(ValueError):core.fixed_window(s,[0.,54.],20.,55.)
        s=s[(s[:,0]<30.)|(s[:,0]>31.)]
        with self.assertRaises(ValueError):core.fixed_window(s,[0.,60.],20.,55.)

    def rows(self):
        return [{'id':'a','source_sha256':'a'*64,'block':'day1','features':[1.,0.],'label':0},
                {'id':'b','source_sha256':'b'*64,'block':'day1','features':[3.,0.],'label':1}]

    def test_dev_fit_explicitly_not_formal_and_frozen_scaling_is_training_only(self):
        m=core.fit_development(self.rows())
        self.assertEqual(m['training_rows'],2)
        self.assertIs(m['formal_calibration_model'],False)
        self.assertEqual(m['mean'],[2.,0.])
        before=m.copy()
        p=core.predict_development(m,[{'id':'c','source_sha256':'c'*64,'block':'day2','features':[1e6,0.]}])
        self.assertEqual(m,before)
        self.assertTrue(0.<p[0]['probability']<1.)

    def test_holdout_label_and_source_reuse_are_rejected(self):
        m=core.fit_development(self.rows())
        with self.assertRaises(ValueError):core.predict_development(m,[{'id':'c','source_sha256':'c'*64,'block':'day2','features':[1.,0.],'label':1}])
        with self.assertRaises(ValueError):core.predict_development(m,[{'id':'z','source_sha256':'a'*64,'block':'day2','features':[1.,0.]}])
        with self.assertRaises(ValueError):core.predict_development(m,[{'id':'c','source_sha256':'c'*64,'block':'day1','features':[1.,0.]}])

    def test_training_input_cannot_include_unselected_test_rows(self):
        m=core.fit_development(self.rows());r=self.rows()
        r.append({'id':'c','source_sha256':'c'*64,'block':'day2','features':[999.,999.],'label':1})
        with self.assertRaises(ValueError):core.fit_development(r)
        self.assertEqual(m,core.fit_development(self.rows()))

    def test_evaluation_requires_unique_and_exact_prediction_label_identity(self):
        p=[{'id':'a','probability':.2},{'id':'b','probability':.8}]
        score=core.score(p,{'a':0,'b':1})
        self.assertAlmostEqual(score['brier'],.04)
        with self.assertRaises(ValueError):core.score(p,{'x':0,'b':1})
        with self.assertRaises(ValueError):core.score([p[0],p[0]],{'a':0})

    def test_multiclass_prior_is_not_binary_point25(self):
        self.assertAlmostEqual(core.uniform_multiclass_brier(4),.75)
        self.assertAlmostEqual(core.uniform_multiclass_brier(2),.5)


if __name__=='__main__':unittest.main()
