import unittest
import numpy as np

from analysis.layout.heading_consensus012 import axis_consensus


class HeadingConsensusTests(unittest.TestCase):
    def test_does_not_let_first_bad_contact_define_room_axes(self):
        angle = np.radians([30., 2., 91., 181., 271.])
        headings = np.c_[np.cos(angle), np.sin(angle)]
        angle, meta = axis_consensus(headings)
        self.assertLess(abs(angle - 1.25), .1)
        self.assertEqual(meta['inliers'], 4)

    def test_unknown_yaw_is_preserved_modulo_quarter_turn(self):
        a = np.radians([13., 103., 193., 283.])
        result, _ = axis_consensus(np.c_[np.cos(a), np.sin(a)])
        self.assertAlmostEqual(result, 13.)

    def test_no_reference_and_empty_observations(self):
        result, meta = axis_consensus(np.empty((0, 2)))
        self.assertEqual(result, 0.)
        self.assertFalse(meta['accepted'])


if __name__ == '__main__':
    unittest.main()
