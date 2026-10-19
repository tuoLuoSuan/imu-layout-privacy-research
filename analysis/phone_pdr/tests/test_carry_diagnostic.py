import copy,math,unittest
from analysis.phone_pdr.pdr import relative_yaw
from analysis.phone_pdr.carry_diagnostic import orientation_trace,principal_axis,diagnose_carry,rotate_vector

G=9.80665
class CarryDiagnostic(unittest.TestCase):
    def test_trace_matches_old_yaw_on_tilted_world_z_rotation(self):
        tilt=math.pi/3;times=[i/100 for i in range(201)]
        a=[(t,0,G*math.sin(tilt),G*math.cos(tilt)) for t in times]
        g=[(t,0,math.sin(tilt),math.cos(tilt)) for t in times]
        trace=orientation_trace(a,g);old=relative_yaw(a,g)
        for item,(_,yaw) in zip(trace,old):self.assertAlmostEqual(item['device_yaw_rad'],yaw,places=12)
        world=rotate_vector(trace[0]['quaternion'],a[0][1:])
        self.assertAlmostEqual(world[2],G,places=10)
        self.assertAlmostEqual(world[1],0,places=10)

    def test_principal_axis_has_two_signs_and_no_body_heading(self):
        theta=math.radians(37)
        rows=[(math.sin(i*.1)*math.cos(theta),math.sin(i*.1)*math.sin(theta)) for i in range(100)]
        r=principal_axis(rows)
        self.assertAlmostEqual(r['axis_mod_pi_rad'],theta,places=10)
        self.assertAlmostEqual(r['axis_candidates_rad'][1]-r['axis_candidates_rad'][0],math.pi)
        self.assertIsNone(r['signed_walking_heading_rad'])

    def test_weak_and_isotropic_signals_return_unknown_axis(self):
        self.assertIsNone(principal_axis([(0,0)]*30)['axis_mod_pi_rad'])
        circle=[(math.cos(i*2*math.pi/100),math.sin(i*2*math.pi/100)) for i in range(100)]
        self.assertIsNone(principal_axis(circle)['axis_mod_pi_rad'])

    def test_dominant_lateral_axis_is_not_claimed_as_forward(self):
        rows=[(.1*math.cos(i*.13),2*math.sin(i*.13)) for i in range(100)]
        result=principal_axis(rows)
        self.assertLess(abs(result['axis_mod_pi_rad']-math.pi/2),.03)
        self.assertIsNone(result['signed_walking_heading_rad'])
        self.assertFalse(result['body_forward_direction_validated'])

    def test_pure_vertical_regrip_remains_ambiguous(self):
        times=[i/100 for i in range(201)]
        a=[(t,0,0,G) for t in times];g=[(t,0,0,math.pi/2) for t in times]
        r=diagnose_carry(a,g)
        self.assertEqual(r['windows'][0]['rotation_flag'],'yaw_rotation_ambiguous')
        self.assertFalse(r['body_heading_observable'])
        self.assertIsNone(r['global_trajectory'])
        self.assertTrue(all(link['relative_body_angle_rad'] is None for link in r['window_links']))

    def test_quiet_device_does_not_mean_validated_carry(self):
        t=[i/100 for i in range(201)];a=[(x,0,0,G) for x in t];g=[(x,0,0,0) for x in t]
        result=diagnose_carry(a,g)
        self.assertEqual(result['windows'][0]['rotation_flag'],'quiet_device_rotation')
        self.assertFalse(result['windows'][0]['stable_carry_validated'])
        self.assertIsNone(result['windows'][0]['horizontal_acceleration_axis']['axis_mod_pi_rad'])

    def test_input_is_not_mutated_and_large_gap_is_refused(self):
        t=[i/100 for i in range(201)];a=[(x,0,0,G) for x in t];g=[(x,0,0,0) for x in t]
        original=copy.deepcopy((a,g));diagnose_carry(a,g);self.assertEqual((a,g),original)
        with self.assertRaisesRegex(ValueError,'gap'):diagnose_carry([(0,0,0,G),(2,0,0,G)],[(0,0,0,0),(2,0,0,0)])

if __name__=='__main__':unittest.main()
