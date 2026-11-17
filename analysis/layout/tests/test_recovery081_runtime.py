"""Inference contract checks for the locked 078/080 composition."""
import unittest
from unittest.mock import patch
import numpy as np
import torch


class Recovery081RuntimeTests(unittest.TestCase):
    def test_routing_uses_actual_contacts_not_metadata(self):
        from analysis.layout.recovery081_runtime import choose_head
        models = {'k2': 'two', 'k6': 'six'}
        obs = {'events': [{}, {}], 'coverage_target': 1., 'contacts_requested': 14,
               'family': 'free', 'id': 'a-made-up-test-room'}
        self.assertEqual(choose_head(obs, models), ('k2', 'two'))
        obs['events'] *= 3
        self.assertEqual(choose_head(obs, models), ('k6', 'six'))
        self.assertEqual(choose_head(obs, {'k2': 'two', 'k6': None}), ('k2', 'two'))

    def test_zero_contact_bypass_never_calls_refiner(self):
        from analysis.layout.recovery081_runtime import refine_boxes
        boxes = {'chair#0': [1., 1., 1.4, 1.4]}
        with patch('analysis.layout.recovery081_runtime.build_view', side_effect=AssertionError('called')):
            result, applied = refine_boxes({'events': []}, boxes, object(), 'nonzero')
        self.assertFalse(applied)
        self.assertEqual(result, boxes)

    def test_refinement_preserves_sizes_and_bounds_without_targets(self):
        from analysis.layout.recovery081_runtime import refine_boxes
        class Shift(torch.nn.Module):
            def forward(self, x, step):
                return torch.ones_like(step) * .1
        obs = {'room': [4., 5.], 'events': [{'object': 'chair', 'pos': [3.9, 4.9]}],
               'walk': [[0., 0.]], 'inventory': [{'category': 'chair', 'dimensions': [.4, .4]}]}
        boxes = {'chair#0': [3.6, 4.6, 4., 5.]}
        result, applied = refine_boxes(obs, boxes, Shift(), 'nonzero')
        self.assertTrue(applied)
        b = np.asarray(result['chair#0'])
        np.testing.assert_allclose(b[2:]-b[:2], [.4, .4], atol=1e-6)
        self.assertTrue(np.all(b[:2] >= 0) and np.all(b[2:] <= obs['room']))


if __name__ == '__main__':
    unittest.main()
