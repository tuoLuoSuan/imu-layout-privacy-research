import importlib.util,unittest
import numpy as np

READY=importlib.util.find_spec('analysis.joint_privacy.space') is not None
if READY:from analysis.joint_privacy.space import distance_field

class SpaceExists(unittest.TestCase):
    def test_representation_exists(self):self.assertTrue(READY)

@unittest.skipUnless(READY,'Distance representation not implemented')
class SpaceContracts(unittest.TestCase):
    def test_distance_to_segment_not_only_logged_vertices(self):
        r=distance_field([[0.,0.],[2.,0.]],cell_m=1.,margin_m=1.)
        x=np.asarray(r['x_centers_m_model']);y=np.asarray(r['y_centers_m_model'])
        d=np.asarray(r['distance_to_modeled_path_m'])
        self.assertEqual(d[np.where(y==0)[0][0],np.where(x==1)[0][0]],0.)
        self.assertEqual(d[np.where(y==1)[0][0],np.where(x==1)[0][0]],1.)
        self.assertIsNone(r['walls']);self.assertFalse(r['free_space_validated'])

    def test_collinear_resampling_does_not_create_more_space_evidence(self):
        a=distance_field([[0.,0.],[2.,0.]],cell_m=1.,margin_m=1.)
        b=distance_field([[0.,0.],[1.,0.],[2.,0.]],cell_m=1.,margin_m=1.)
        np.testing.assert_allclose(a['distance_to_modeled_path_m'],b['distance_to_modeled_path_m'])

    def test_unbounded_raster_and_nan_are_refused(self):
        with self.assertRaises(ValueError):distance_field([[0.,0.],[10000.,0.]],cell_m=.1)
        with self.assertRaises(ValueError):distance_field([[0.,0.],[np.nan,0.]])

if __name__=='__main__':unittest.main()
