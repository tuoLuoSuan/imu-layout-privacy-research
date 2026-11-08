"""Floor storage cannot inherit a wall shelf's projection-overlap permission."""
import unittest
import numpy as np
from analysis.layout.continuous_decode import decode


def fixed_region(boxes):
    modes=[]
    for b in boxes:
        b=np.asarray(b,float);modes.append({'dimensions':b[2:]-b[:2],
            'q_regions':np.array([[*b[:2],*b[:2]]])})
    centers=[(np.array(b[:2])+b[2:])/2 for b in boxes]
    return {'modes':modes,'point_m':centers[0]}


class SolidStorageTests(unittest.TestCase):
    def test_solid_storage_forces_supported_desk_alternative(self):
        regions={'bed':fixed_region([[0,3,1,4]]),
                 'cab':fixed_region([[0,0,1,1]]),
                 'desk':fixed_region([[0,0,1,1],[2,0,3,1]]),
                 'chair':fixed_region([[3,3,3.4,3.4]])}
        result=decode([4,4],regions,[],[],solid_storage=True)
        np.testing.assert_allclose(result['boxes']['desk'],[2,0,3,1])

    def test_wall_shelf_keeps_projection_overlap_permission(self):
        regions={'bed':fixed_region([[0,3,1,4]]),'cab':fixed_region([[0,0,1,1]]),
                 'desk':fixed_region([[0,0,1,1]]),'chair':fixed_region([[3,3,3.4,3.4]])}
        self.assertEqual(decode([4,4],regions,[],[])['status'],'ok')
        self.assertEqual(decode([4,4],regions,[],[],solid_storage=True)['status'],'joint_search_conflict')

    def test_joint_choice_can_move_storage_instead_of_losing_desk(self):
        regions={'bed':fixed_region([[0,3,1,4]]),
                 'cab':fixed_region([[0,0,1,1],[2,0,3,1]]),
                 'desk':fixed_region([[0,0,1,1]]),'chair':fixed_region([[3,3,3.4,3.4]])}
        result=decode([4,4],regions,[],[],solid_storage=True)
        self.assertEqual(result['status'],'ok')
        np.testing.assert_allclose(result['boxes']['cab'],[2,0,3,1])

    def test_seated_desk_relation_requires_explicit_protocol(self):
        regions={'bed':fixed_region([[0,3,1,4]]),'cab':fixed_region([[0,0,1,1]]),
                 'desk':fixed_region([[2,0,3,1],[2,2,3,3]]),
                 'chair':fixed_region([[3,2,3.4,2.4]])}
        events=[{'object':'chair','pos':[3.2,2.2]}]
        result=decode([4,4],regions,events,[],solid_storage=True,desk_seat_max_distance=.9)
        np.testing.assert_allclose(result['boxes']['desk'],[2,2,3,3])

    def test_declared_desk_relation_has_a_sound_outer_region(self):
        from analysis.layout.continuous_regions import object_region,contains_box
        events=[{'object':'chair','pos':[3.2,2.2]}]
        region=object_region([4,4],[1,1],'desk',events,[],desk_seat_max_distance=.9)
        self.assertTrue(contains_box(region,[2,2,3,3]))
        self.assertFalse(contains_box(region,[0,0,1,1]))


if __name__=='__main__': unittest.main()
