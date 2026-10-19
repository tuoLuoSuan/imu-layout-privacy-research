import unittest
from analysis.phone_ronin.prefix import evaluate_prefix,path_end
from analysis.phone_ronin.tests.test_prefix import signals,predictor

class SupportContracts(unittest.TestCase):
    def test_appended_array_without_recorded_stop_is_unknown(self):
        a,g,aa,ga=signals(70.)
        def forbidden(w):raise AssertionError('Untrusted array length reached network')
        r=evaluate_prefix(a,g,aa,ga,60.,forbidden)
        self.assertEqual(r['summary']['status'],'unknown_support')
        self.assertIsNone(r['summary']['support_end_s'])
        self.assertIsNone(path_end(a,g,aa,ga,60.,forbidden))

    def test_raw_and_model_tail_names_are_explicit(self):
        a,g,aa,ga=signals();r=evaluate_prefix(a,g,aa,ga,2.,predictor,support_end_s=4.)
        s=r['summary'];self.assertIn('raw_unobserved_tail_s',s)
        self.assertIn('resampling_interpolation_used',s)
        self.assertNotIn('unobserved_tail_s',s)
        self.assertEqual(s['support_end_s'],4.)

    def test_missing_support_does_not_disable_budget_validation(self):
        a,g,aa,ga=signals()
        with self.assertRaises(ValueError):evaluate_prefix(a,g,aa,ga,-1.,predictor)

if __name__=='__main__':unittest.main()
