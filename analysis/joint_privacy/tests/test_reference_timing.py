"""Bounded-reference math and causal clock-plan contracts; no hardware claims."""
import copy,importlib.util,json,math,subprocess,sys,tempfile,unittest
from pathlib import Path

READY=importlib.util.find_spec('analysis.joint_privacy.reference_timing') is not None
if READY:from analysis.joint_privacy.reference_timing import map_reference,plan_clock

def fixture():
    return {'schema_version':1,'time_unit':'seconds','source_id':'synthetic-audio','target_id':'synthetic-phone',
        'anchors':[{'source_s':10.,'source_error_s':0.,'target_s':0.},
                   {'source_s':110.,'source_error_s':0.,'target_s':100.}],
        'target_support_s':[0.,100.],'target_window_s':1.,
        'intervals':[{'id':'walk','activity':'walk','start_s':30.,'end_s':50.,'start_error_s':1.,'end_error_s':1.}]}

def clock_fixture():
    return {'schema_version':1,'budgets_s':[105.,125.,155.],'threshold_s':.5,
        'clock_contract':{'phone_id':'SYNTHETIC-PHONE','watch_id':'SYNTHETIC-WATCH','paired_session_id':'SYNTHETIC-PLAN',
        'mode':'synthetic_pre_task_only','anchors':[{'watch_epoch_ms':1005000.,'phone_s':5.,'uncertainty_s':.15},
            {'watch_epoch_ms':1085000.,'phone_s':85.,'uncertainty_s':.15}],
        'checks':[{'watch_epoch_ms':1045000.,'phone_s':45.05,'uncertainty_s':.15}],
        'available_s':85.15,'valid_until_s':180.,'drift_bound_ppm':100.,'max_uncertainty_s':.5}}

class Exists(unittest.TestCase):
    def test_reference_utility_is_present(self):self.assertTrue(READY,'reference_timing utility is missing')

@unittest.skipUnless(READY,'reference timing utility not yet implemented')
class TimingMath(unittest.TestCase):
    def test_exact_offset_and_boundary_errors_have_analytic_envelopes(self):
        r=map_reference(fixture());i=r['intervals'][0]
        self.assertEqual(i['start_phone_envelope_s'],[19.,21.]);self.assertEqual(i['end_phone_envelope_s'],[39.,41.])
        self.assertEqual(i['common_interior_s'],[21.,39.]);self.assertEqual(i['admissible_target_end_s'],[22.,39.])
        self.assertFalse(r['clock_verified']);self.assertFalse(r['reference_generated'])

    def test_correlated_duration_is_not_confused_with_common_intersection(self):
        d=fixture();d['anchors'][0]['source_error_s']=2.;d['anchors'][1]['source_error_s']=2.
        r=map_reference(d)['intervals'][0]
        self.assertGreater(r['correlated_duration_range_s'][0],r['common_interior_duration_s'])

    def test_dense_interior_mappings_are_enclosed_by_corner_envelopes(self):
        d=fixture();d['anchors'][0]['source_error_s']=2.;d['anchors'][1]['source_error_s']=3.
        row=map_reference(d)['intervals'][0]
        for a in (8.,9.,10.,11.,12.):
            for b in (107.,108.5,110.,111.5,113.):
                for t in (29.,29.4,30.,30.5,31.):
                    value=(t-a)/(b-a)*100.
                    self.assertLessEqual(row['start_phone_envelope_s'][0]-1e-12,value)
                    self.assertGreaterEqual(row['start_phone_envelope_s'][1]+1e-12,value)

    def test_uncertain_anchor_order_is_rejected(self):
        d=fixture();d['anchors'][0]['source_error_s']=100.
        with self.assertRaises(ValueError):map_reference(d)

    def test_unknown_is_never_converted_to_nonwalk(self):
        d=fixture();d['intervals'][0]['activity']='unknown'
        i=map_reference(d)['intervals'][0]
        self.assertEqual(i['status'],'unknown_activity');self.assertIsNone(i['admissible_target_end_s'])

    def test_outside_authoritative_support_is_not_silently_trimmed(self):
        d=fixture();d['intervals'][0]['end_s']=120.
        i=map_reference(d)['intervals'][0]
        self.assertEqual(i['status'],'outside_target_support');self.assertIsNone(i['admissible_target_end_s'])

    def test_overlap_of_boundary_errors_is_ambiguous_not_negative_walk(self):
        d=fixture();d['intervals'][0].update(end_s=31.,end_error_s=2.)
        i=map_reference(d)['intervals'][0]
        self.assertEqual(i['status'],'ambiguous_interval_order');self.assertFalse(i['fits_target_window'])

    def test_invalid_schema_values_and_duplicate_ids_are_rejected(self):
        bad=[]
        for val in (True,float('nan'),float('inf'),-1.):
            d=fixture();d['target_window_s']=val;bad.append(d)
        d=fixture();d['extra']='truth';bad.append(d)
        d=fixture();d['time_unit']='milliseconds';bad.append(d)
        d=fixture();d['intervals'].append(copy.deepcopy(d['intervals'][0]));bad.append(d)
        d=fixture();d['anchors'][0]['extra']=1;bad.append(d)
        for d in bad:
            with self.subTest(d=d),self.assertRaises(ValueError):map_reference(d)

    def test_old_real_case_stays_below_one_second(self):
        d=fixture();d['anchors']=[{'source_s':1.5,'source_error_s':2.5,'target_s':-.000425117},
                                 {'source_s':136.33,'source_error_s':1.73,'target_s':134.847633113}]
        d['target_support_s']=[-.000425117,134.847633113]
        d['intervals'][0].update(start_s=67.,end_s=74.)
        i=map_reference(d)['intervals'][0]
        self.assertAlmostEqual(i['common_interior_duration_s'],.7882347988595058,places=10)
        self.assertEqual(i['status'],'insufficient_common_support');self.assertFalse(i['fits_target_window'])

    def test_no_complete_window_when_duration_below_target(self):
        d=fixture();d['intervals'][0].update(start_s=30.,end_s=32.5)
        self.assertFalse(map_reference(d)['intervals'][0]['fits_target_window'])

    def test_input_is_not_mutated(self):
        d=fixture();old=copy.deepcopy(d);map_reference(d);self.assertEqual(d,old)

    def test_wide_pre_task_plan_passes_only_under_assumptions(self):
        r=plan_clock(clock_fixture())
        self.assertEqual(r['status'],'plan_pass_under_assumptions')
        self.assertAlmostEqual(r['budgets'][-1]['uncertainty_s'],.4695,places=10)
        self.assertFalse(r['clock_verified']);self.assertFalse(r['hardware_verified'])

    def test_post_task_calibration_is_unavailable_at_earlier_budgets(self):
        d=clock_fixture();d['clock_contract']['available_s']=170.
        r=plan_clock(d);self.assertEqual(r['status'],'plan_rejected')
        self.assertTrue(all(b['reason']=='calibration_not_available' for b in r['budgets']))

    def test_equal_threshold_is_rejected_strictly(self):
        d=clock_fixture();r=plan_clock(d);d['threshold_s']=r['budgets'][-1]['uncertainty_s']
        self.assertFalse(plan_clock(d)['budgets'][-1]['accepted'])

    def test_duplicate_or_nonfinite_budgets_are_rejected(self):
        for budgets in ([105.,105.],[True],[float('nan')],[]):
            d=clock_fixture();d['budgets_s']=budgets
            with self.subTest(budgets=budgets),self.assertRaises(ValueError):plan_clock(d)

    def test_attack_import_does_not_load_reference_calculator(self):
        code="import sys; import analysis.joint_privacy.attack; assert 'analysis.joint_privacy.reference_timing' not in sys.modules"
        p=subprocess.run([sys.executable,'-c',code],capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)

if __name__=='__main__':unittest.main()
