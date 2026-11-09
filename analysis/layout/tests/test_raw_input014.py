import unittest
from analysis.layout.exp_bias014 import infer_saved


class RawInput014Tests(unittest.TestCase):
    def test_reject_reference_fields_before_opening_a_model(self):
        with self.assertRaises(ValueError):infer_saved('missing',{'room':[4,4],'start':[1,1],'inventory':[],'truth':[]},tracker='gg')


if __name__=='__main__':unittest.main()
