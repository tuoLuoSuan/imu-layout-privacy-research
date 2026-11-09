import unittest
import numpy as np


class OrientedTests(unittest.TestCase):
    def test_bed_long_axis_is_constrained_by_measured_lying_heading(self):
        from analysis.layout.oriented_raw011 import bed_orientation_mask
        boxes=np.array([[0.,0.,2.,1.],[0.,0.,1.,2.]])
        np.testing.assert_array_equal(bed_orientation_mask(boxes,[1.,0.]),[True,False])

    def test_cabinet_heading_selects_the_observed_operation_side(self):
        from analysis.layout.oriented_raw011 import directed_contact
        boxes=np.array([[0.,.5,.4,1.5],[1.6,.5,2.,1.5]])
        keep,_=directed_contact('cab',boxes,[1.,1.],[-1.,0.],.1)
        np.testing.assert_array_equal(keep,[True,False])

    def test_seated_direction_is_a_relation_without_given_table_centre(self):
        from analysis.layout.oriented_raw011 import directed_contact
        boxes=np.array([[0.,.5,.6,1.5],[1.4,.5,2.,1.5]])
        keep,_=directed_contact('desk_relation',boxes,[1.,1.],[-1.,0.],.1)
        np.testing.assert_array_equal(keep,[True,False])

    def test_soft_contact_cost_prefers_the_measured_seat_to_a_boundary_candidate(self):
        from unittest.mock import patch
        from analysis.layout import multi_instance as M
        boxes=np.array([[0.,0.,.4,.4],[.3,0.,.7,.4]])
        inv=[{'id':'chair#0','category':'chair','dimensions':[.4,.4]}];events=[{'object':'chair','pos':[.3,.2]}]
        with patch.object(M,'_proposals',return_value=(boxes,{'point_m':np.array([.5,.2])})):
            r=M.decode_instances([3,3],inv,events,[],support_cost_weight=.3)
        np.testing.assert_allclose(r['boxes']['chair#0'],boxes[0])

    def test_declared_storage_front_is_normal_to_the_short_depth_axis(self):
        from analysis.layout.oriented_raw011 import directed_contact
        boxes=np.array([[1.,.5,1.4,1.5],[.2,.8,1.4,1.2]])
        keep,_=directed_contact('cab',boxes,[2.,1.],[-1.,0.],.1)
        np.testing.assert_array_equal(keep,[True,False])


if __name__=='__main__':unittest.main()
