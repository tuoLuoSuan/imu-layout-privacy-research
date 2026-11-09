import unittest
import numpy as np
from analysis.layout.wall_refine012 import fit_room_drift


class WallRefineTests(unittest.TestCase):
    def test_input_api_rejects_truth_before_reading_files(self):
        from analysis.layout.joint_input012 import infer_saved
        with self.assertRaises(ValueError):
            infer_saved('missing', {'room': [4.,4.], 'start':[1.,1.], 'inventory':[], 'gt':{}}, 'missing', 'missing')

    def test_storage_face_corrects_normal_drift_without_object_position(self):
        t = np.linspace(0, 60, 61)
        path = np.c_[np.linspace(2., .7, 61), np.full(61, 2.)]
        observation = {'time': 60., 'point': path[-1], 'normal': [-1., 0.]}
        result, _ = fit_room_drift(t, path, [observation], [4., 4.], [.5])
        self.assertGreater(result[-1, 0], 1.)
        np.testing.assert_array_equal(result[0], path[0])
        np.testing.assert_allclose(result[:, 1], path[:, 1], atol=1e-6)

    def test_does_not_move_already_compatible_path(self):
        t = np.linspace(0, 60, 61)
        path = np.c_[np.linspace(2., 1.17, 61), np.full(61, 2.)]
        observation = {'time': 60., 'point': path[-1], 'normal': [-1., 0.]}
        result, _ = fit_room_drift(t, path, [observation], [4., 4.], [.5])
        np.testing.assert_allclose(result, path, atol=1e-8)


if __name__ == '__main__':
    unittest.main()
