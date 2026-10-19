import math
import unittest
from analysis.phone_pdr import pdr

G=9.80665
class Mechanics(unittest.TestCase):
    def test_weinberg_is_fourth_root_not_square_root(self):
        self.assertAlmostEqual(pdr.weinberg_stride(16.0,0.5),1.0)
        self.assertAlmostEqual(pdr.weinberg_stride(81.0,0.5),1.5)

    def test_stationary_has_no_step_candidates(self):
        a=[(i/100,0,0,G) for i in range(1001)]
        self.assertEqual(pdr.detect_steps(a),[])

    def test_periodic_synthetic_signal_has_expected_peak_times(self):
        a=[(i/100,0,0,G+1.8*math.sin(4*math.pi*i/100)) for i in range(1001)]
        steps=pdr.detect_steps(a)
        self.assertGreaterEqual(len(steps),19)
        self.assertLessEqual(len(steps),20)
        for left,right in zip(steps,steps[1:]):
            self.assertAlmostEqual(right['time_s']-left['time_s'],0.5,delta=0.03)

    def test_yaw_uses_real_timestamps_and_correct_angle(self):
        times=[0,.011,.025,.12,.3,.57,.79,1.0]
        a=[(t,0,0,G) for t in times]
        g=[(t,0,0,math.pi/2) for t in times]
        self.assertAlmostEqual(pdr.relative_yaw(a,g)[-1][1],math.pi/2,places=7)

    def test_tilted_device_uses_world_vertical_not_only_body_z(self):
        # Body is rolled +90 degrees; world yaw rate is body +Y, not body +Z.
        times=[i/100 for i in range(101)]
        a=[(t,0,G,0) for t in times]
        g=[(t,0,math.pi/2,0) for t in times]
        self.assertAlmostEqual(pdr.relative_yaw(a,g)[-1][1],math.pi/2,places=5)

    def test_uncalibrated_diagnostic_does_not_emit_meters_or_walls(self):
        a=[(i/100,0,0,G+1.8*math.sin(4*math.pi*i/100)) for i in range(201)]
        g=[(i/100,0,0,0) for i in range(201)]
        r=pdr.diagnose(a,g)
        self.assertFalse(r['research_validated'])
        self.assertEqual(r['coordinate_units'],'uncalibrated_amplitude_scale')
        self.assertTrue(r['step_candidates'])
        self.assertTrue(all(s['x_m'] is None for s in r['step_candidates']))
        self.assertNotIn('walls',r)
        self.assertNotIn('layout_accuracy',r)

    def test_large_clock_gap_cannot_be_hidden_in_a_path(self):
        with self.assertRaisesRegex(ValueError,'gap'):
            pdr.diagnose([(0,0,0,G),(2,0,0,G)],[(0,0,0,0),(2,0,0,0)])

if __name__=='__main__':unittest.main()
