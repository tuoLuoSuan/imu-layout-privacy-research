import importlib.util,unittest
import numpy as np

READY=importlib.util.find_spec('analysis.phone_ronin.ensemble') is not None
if READY:from analysis.phone_ronin.ensemble import rotate_features,c4_predict

class EnsembleExists(unittest.TestCase):
    def test_ensemble_exists(self):self.assertTrue(READY)

@unittest.skipUnless(READY,'C4 frame-control ensemble not implemented')
class EnsembleContracts(unittest.TestCase):
    def test_discrete_input_rotation_is_equivariant_after_averaging(self):
        x=np.random.default_rng(58).normal(size=(3,6,200)).astype(np.float32)
        def biased(w):return np.column_stack((w[:,3].mean(1)*2+.3,w[:,4].mean(1)*.5-.1))
        base=c4_predict(x,biased);rotated=c4_predict(rotate_features(x,1),biased)
        np.testing.assert_allclose(rotated,np.column_stack((-base[:,1],base[:,0])),atol=1e-7)

    def test_z_and_gravity_are_preserved_not_subtracted(self):
        x=np.random.default_rng(1).normal(size=(2,6,200)).astype(np.float32)
        r=rotate_features(x,1)
        np.testing.assert_array_equal(r[:,2],x[:,2]);np.testing.assert_array_equal(r[:,5],x[:,5])
        np.testing.assert_array_equal(rotate_features(r,3),x)

    def test_only_four_inferences_no_training_or_new_samples(self):
        x=np.zeros((2,6,200),dtype=np.float32);calls=[]
        def stub(w):calls.append(w.shape);return np.ones((len(w),2))
        c4_predict(x,stub);self.assertEqual(calls,[(2,6,200)]*4)

if __name__=='__main__':unittest.main()
