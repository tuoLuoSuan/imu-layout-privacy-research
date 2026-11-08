import unittest
from analysis.layout import simple_rooms as S


class SimpleRoomTests(unittest.TestCase):
    def test_seed_controls_new_room_geometry(self):
        a=S.draw_geometry(10);b=S.draw_geometry(10);c=S.draw_geometry(11)
        self.assertEqual(a,b);self.assertNotEqual(a,c)

    def test_one_object_per_role_and_no_projection_collision(self):
        for seed in range(20):
            r=S.draw_geometry(seed);self.assertEqual(set(r['gt']),{'bed','desk','cab','chair'})
            for k,b in r['gt'].items():
                self.assertTrue(0<=b[0]<b[2]<=r['W']);self.assertTrue(0<=b[1]<b[3]<=r['L'])
                for other,c in r['gt'].items():
                    if other!=k:self.assertLessEqual(S.overlap(b,c),1e-8)

    def test_multiple_instances_are_preserved(self):
        r=S.draw_multi_geometry(12,{'bed':1,'desk':2,'cab':2,'chair':2})
        self.assertEqual(len(r['gt']),7)
        self.assertEqual(sum(k.startswith('desk#') for k in r['gt']),2)
        for k,b in r['gt'].items():
            for other,c in r['gt'].items():
                if other!=k:self.assertLessEqual(S.overlap(b,c),1e-8)


if __name__=='__main__':unittest.main()
