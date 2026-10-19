import copy,math,tempfile,unittest
from pathlib import Path
from analysis.phone_pdr.evaluate import evaluate,write_evaluation

def fixture():
    candidates=[{'time_s':t,'detected_at_s':t+.01,'amplitude_m_s2':1.0,'device_yaw_rad':0.0} for t in [.5,1,2,3,6,7,8]]
    diagnostic={'overlap_start_s':0,'overlap_end_s':10,'step_candidates':candidates}
    annotations={'schema_version':1,'time_basis':'seconds_since_first_sensor_event','annotation_source':'synthetic known markers',
        'time_uncertainty_s':.05,'AB':{'start_s':1,'end_s':3,'distance_m':4,'manual_steps':2},
        'BC':{'start_s':6,'end_s':8,'distance_m':4,'manual_steps':2},
        'turn_before':{'start_s':3.2,'end_s':4},'turn_after':{'start_s':5,'end_s':5.8},'expected_turn_deg':90}
    headings=[(3.3,3.1),(3.5,3.1),(3.9,3.1),(5.1,3.1+math.pi/2),(5.5,3.1+math.pi/2),(5.7,3.1+math.pi/2)]
    return diagnostic,annotations,headings

class Evaluation(unittest.TestCase):
    def test_half_open_indices_and_source_csv_line_numbers(self):
        d,a,h=fixture();r=evaluate(d,a,h)
        self.assertEqual(r['calibration']['candidate_indices'],[2,3])
        self.assertEqual(r['calibration']['diagnostic_csv_lines'],[3,4])
        self.assertEqual(r['test']['candidate_indices'],[5,6])
        self.assertEqual(r['excluded_candidate_indices'],[1,4,7])
        self.assertEqual(r['boundary_uncertain_candidate_indices'],[2,4,5,7])
        self.assertFalse(r['research_validated'])

    def test_test_distance_cannot_change_calibration(self):
        d,a,h=fixture();r=evaluate(d,a,h);a['BC']['distance_m']=400
        changed=evaluate(d,a,h)
        self.assertEqual(changed['calibration']['k'],r['calibration']['k'])
        self.assertEqual(changed['test']['predicted_length_m'],4)
        self.assertNotEqual(changed['test']['signed_length_error_m'],r['test']['signed_length_error_m'])

    def test_weighted_fourth_root_calibration_and_conditional_sensitivity(self):
        d,a,h=fixture();d['step_candidates'][1]['amplitude_m_s2']=16
        r=evaluate(d,a,h);c=r['calibration']
        self.assertAlmostEqual(c['k'],4/3)
        self.assertEqual(c['sensitivity']['remove_one_candidate_k_range'],[2,4])
        self.assertEqual(c['sensitivity']['add_one_candidate_assuming_observed_weight_range'],[.8,1])
        self.assertFalse(c['sensitivity']['is_confidence_interval'])

    def test_turn_is_difference_of_unwrapped_window_medians(self):
        d,a,h=fixture();r=evaluate(d,a,h)
        self.assertAlmostEqual(r['turn']['difference_deg'],90)
        self.assertAlmostEqual(r['turn']['error_deg'],0)
        self.assertEqual(r['turn']['before']['samples'],3)
        self.assertTrue(r['descriptive_flags']['turn_error_within_15_deg'])

    def test_annotation_does_not_modify_source_candidates(self):
        d,a,h=fixture();before=copy.deepcopy(d);evaluate(d,a,h)
        self.assertEqual(d,before)

    def test_overlapping_and_out_of_range_windows_are_refused(self):
        for key,value in [('AB',{'end_s':3.5}),('BC',{'end_s':11})]:
            d,a,h=fixture();a[key].update(value)
            with self.assertRaises(ValueError):evaluate(d,a,h)

    def test_unknown_clock_or_nonfinite_reference_is_refused(self):
        d,a,h=fixture();a['time_basis']='wall clock'
        with self.assertRaises(ValueError):evaluate(d,a,h)
        d,a,h=fixture();a['AB']['distance_m']=float('nan')
        with self.assertRaises(ValueError):evaluate(d,a,h)

    def test_empty_calibration_or_turn_window_is_visible_failure(self):
        d,a,h=fixture();d['step_candidates']=[]
        with self.assertRaisesRegex(ValueError,'calibration'):evaluate(d,a,h)
        d,a,h=fixture()
        with self.assertRaisesRegex(ValueError,'heading'):evaluate(d,a,[])

    def test_unknown_manual_steps_are_not_fabricated(self):
        d,a,h=fixture();a['BC']['manual_steps']=None
        r=evaluate(d,a,h)
        self.assertIsNone(r['test']['candidate_minus_manual_steps'])
        self.assertIsNone(r['descriptive_flags']['BC_count_difference_within_1'])

    def test_writer_refuses_existing_data_and_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'original';p.write_bytes(b'ORIGINAL')
            with self.assertRaises(FileExistsError):write_evaluation(p,{},b'{}')
            self.assertEqual(p.read_bytes(),b'ORIGINAL')
        with self.assertRaises(ValueError):write_evaluation(Path.cwd()/'output/phone-pdr/../../data/no-write',{},b'{}')

if __name__=='__main__':unittest.main()
