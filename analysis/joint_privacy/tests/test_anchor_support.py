"""Regression contracts for DS069 target-anchor support, not clock truth."""
import copy,json,unittest
from pathlib import Path
from analysis.joint_privacy.reference_timing import map_reference
from analysis.joint_privacy.tests.test_reference_timing import fixture

class AnchorSupport(unittest.TestCase):
    def test_upper_counterexample_is_rejected_before_interval_mapping(self):
        d=fixture();d['anchors']=[{'source_s':10.,'source_error_s':0.,'target_s':5.},
                                {'source_s':200.,'source_error_s':0.,'target_s':200.}]
        d['intervals'][0].update(start_s=50.,end_s=60.,start_error_s=0.,end_error_s=0.)
        with self.assertRaisesRegex(ValueError,'Target anchor outside recorded support'):map_reference(d)

    def test_anchor_below_support_is_also_rejected(self):
        d=fixture();d['anchors'][0]['target_s']=-.001
        with self.assertRaisesRegex(ValueError,'Target anchor outside recorded support'):map_reference(d)

    def test_boundary_anchors_are_accepted_inclusively(self):
        self.assertTrue(map_reference(fixture())['intervals'][0]['fits_target_window'])

    def test_metadata_recording_support_preserves_old_envelopes(self):
        # Minimal numeric regression vector; no media IDs or private evidence files.
        old=fixture()
        old['anchors']=[{'source_s':1.5,'source_error_s':2.5,'target_s':-.000425117},
                        {'source_s':136.32999999999998,'source_error_s':1.730000000000004,'target_s':134.847633113}]
        old['target_support_s']=[0.,134.847633113]
        old['intervals']=[{'id':'narrow-regression','activity':'walk','start_s':67.,'end_s':74.,'start_error_s':1.,'end_error_s':1.}]
        d=copy.deepcopy(old);d['target_support_s'][0]=d['anchors'][0]['target_s']
        r=map_reference(d)['intervals'][0]
        self.assertAlmostEqual(r['common_interior_duration_s'],.7882347988594773,places=10)
        self.assertFalse(r['fits_target_window']);self.assertEqual(old['target_support_s'][0],0.)

    def test_reverse_or_equal_target_anchors_have_specific_message(self):
        for second in (0.,-1.):
            d=fixture();d['target_support_s']=[-2.,100.];d['anchors'][1]['target_s']=second
            with self.subTest(second=second),self.assertRaisesRegex(ValueError,'Target anchor times must be strictly increasing'):
                map_reference(d)

    def test_boolean_and_nonfinite_messages_are_separate(self):
        for value,message in [(True,'Boolean values are not times'),(float('nan'),'Finite numeric seconds required'),
                              (float('inf'),'Finite numeric seconds required')]:
            d=fixture();d['target_window_s']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,message):map_reference(d)

if __name__=='__main__':unittest.main()
