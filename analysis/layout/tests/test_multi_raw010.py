import unittest
import numpy as np


class MultiRaw010Tests(unittest.TestCase):
    def test_all_interactions_survive_without_instance_identity(self):
        from analysis.layout.multi_raw010 import interaction_events
        t=np.arange(0,12,.1);p=np.c_[t,np.zeros(len(t))]
        events=interaction_events(t,p,[['cabinet',1,4],['cabinet',6,9],['lying',9,12]])
        self.assertEqual([e['object'] for e in events],['cab','cab','bed'])
        self.assertTrue(all(set(e)=={'object','pos'} for e in events))
        self.assertGreater(events[1]['pos'][0]-events[0]['pos'][0],4.)

    def test_collinear_compression_keeps_turns_and_return_legs(self):
        from analysis.layout.multi_raw010 import compress
        path=np.array([[0,0],[1,0],[2,0],[2,1],[2,2],[2,1],[2,0]])
        np.testing.assert_array_equal(compress(path),[[0,0],[2,0],[2,2],[2,0]])

    def test_short_or_standing_phone_false_seats_are_rejected_by_pose_protocol(self):
        from analysis.layout.multi_raw010 import qualified_runs
        t=np.arange(0,30,.1);A=np.tile([7.,-7.,-.6],(len(t),1))
        A[(t>=10)&(t<=20)]=[9.4,-3.2,-.7]
        runs=[['seated',1,7],['seated',10,18],['seated',20,22],['cabinet',23,28]]
        self.assertEqual(qualified_runs(t,A,runs),[['seated',10,18],['cabinet',23,28]])


if __name__=='__main__':unittest.main()
