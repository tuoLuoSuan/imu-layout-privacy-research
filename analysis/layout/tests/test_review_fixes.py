"""Regression checks for the November review's concrete failure cases."""

import importlib
import sys
import unittest
from unittest.mock import patch
import io
from pathlib import Path

import numpy as np

LAYOUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAYOUT))


class ReviewFixTests(unittest.TestCase):
    def test_frozen_model_and_feature_contract_load(self):
        actions = importlib.import_module('action_model')
        model = actions.load_model()
        self.assertEqual(len(model['keys']), 70)
        self.assertEqual(model['classifier'].n_estimators, 400)

    def test_public_model_exception_is_exact_and_other_models_stay_private(self):
        from tools.repository_guard import private_path
        self.assertFalse(private_path('analysis/layout/models/phone-five-class.joblib'))
        self.assertTrue(private_path('analysis/layout/models/another.joblib'))
        self.assertTrue(private_path('output/model.joblib'))

    def test_missing_anchor_still_checks_prior_coverage(self):
        evidence = importlib.import_module("exp_evidence")
        row = evidence.axis_row("bed", "lying", (1.30, 1.88, 2.825, 3.965),
                                (2.84, 4.045), {}, 0, 1.17, prior="box")
        self.assertFalse(row[1])

    def test_identified_fraction_includes_wide_axes(self):
        evidence = importlib.import_module("exp_evidence")
        rows = [dict(obj="chair", cls="seated", box=(0, 0, 1, 1),
                     room=(1.05, 3), axis=axis, truth_q=0.02) for axis in (0, 1)]
        self.assertEqual(evidence.summarize(rows, lambda row: {})["identified"], 0.5)

    def test_known_wall_generator_keeps_truth_in_known_prior(self):
        leakage = importlib.import_module("leakage_curve")
        row = dict(L=1.0, room=5.0, contact=True, side="hi")
        _, covered = leakage._widths(row, 0.0, "K")
        self.assertTrue(covered.all())

    def test_oversized_object_is_geometry_error(self):
        leakage = importlib.import_module("leakage_curve")
        with self.assertRaises(ValueError):
            leakage._widths(dict(L=6.0, room=5.0, contact=False), 0.0, "U")

    def test_constant_prediction_has_no_discrimination(self):
        robust = importlib.import_module("exp_robust")
        rows = [dict(scene=str(i), obj="bed", pred=1.0, meas=value)
                for i, value in enumerate((0.0, 0.2, 2.0, 3.0))]
        self.assertEqual(robust.predictive_summary(rows, repeats=20)["auc"], 0.5)

    def test_multi_object_hits_must_share_one_layout(self):
        modes = importlib.import_module("exp_modes")
        truth = {"bed": (0, 0, 1, 1), "desk": (2, 2, 3, 3)}
        candidates = [dict(boxes={"bed": truth["bed"], "desk": (4, 4, 5, 5)}),
                      dict(boxes={"bed": (2, 0, 3, 1), "desk": truth["desk"]})]
        result = modes.evaluate_candidate_set(candidates, truth)
        self.assertTrue(result["bed"]["hit"])
        self.assertTrue(result["desk"]["hit"])
        self.assertFalse(result["full_layout_hit"])

    def test_walk_route_avoids_true_desks_and_cabinets(self):
        simulation = importlib.import_module("sim_eval")
        scene = dict(W=5.0, L=5.0, S=(0.3, 0.3),
                     gt={"desk": (2, 0, 3, 4), "cab": (3.8, 4, 4.5, 4.5)})
        anchors = dict(seated=(4, 2), cabinet=(4, 3.5), lying=(1, 4.5))
        points, walk = simulation.traj_of(scene, anchors)
        for box in scene["gt"].values():
            inside = ((points[:, 0] > box[0]) & (points[:, 0] < box[2]) &
                      (points[:, 1] > box[1]) & (points[:, 1] < box[3]))
            self.assertFalse(np.any(inside & walk))

    def test_dense_map_clips_negative_boxes(self):
        dense = importlib.import_module("dense_map")
        pred = dict(room=(1, 1), boxes={"bed": (-0.1, -0.1, 0.2, 0.2)})
        heights, _, _ = dense.height_field(pred, {"bed": 0.5}, grid=0.1)
        self.assertAlmostEqual(float(heights.sum()), 2.0)

    def test_conditioned_height_uses_same_vocabulary(self):
        heights = importlib.import_module("height_prior")
        rows = [dict(scene=scene, cat="Bed", h=0.5, area=2.0, against_wall=True)
                for scene in ("a", "b")]
        rows.append(dict(scene="a", cat="Sofa", h=1.0, area=2.0, against_wall=False))
        self.assertEqual(heights.loso_conditioned(rows)["n"], 2)

    def test_action_predictions_only_use_available_windows(self):
        actions = importlib.import_module("action_model")
        times = np.arange(0, 8, 0.02)
        acceleration = np.tile([0.0, 0.0, 9.81], (len(times), 1))
        gyro = np.zeros_like(acceleration)

        class Classifier:
            matrices = []
            def predict(self, features):
                self.matrices.append(features.copy())
                return np.array(["lying"] * len(features))

        features = actions.features_at(times, acceleration, times, gyro, 1.0)
        model = {"classifier": Classifier(), "keys": sorted(features)}
        first = actions.predict_timeline(model, times, acceleration, times, gyro, budget_s=4.0)
        changed = acceleration.copy()
        changed[times > 4] = 1000
        second = actions.predict_timeline(model, times, changed, times, gyro, budget_s=4.0)
        self.assertEqual(first, second)
        np.testing.assert_array_equal(model['classifier'].matrices[0], model['classifier'].matrices[1])
        self.assertTrue(all(row["available_s"] <= 4.0 for row in first["windows"]))

    def test_sensor_timestamps_keep_their_shared_origin(self):
        actions = importlib.import_module('action_model')
        header = 'sensor_timestamp_ns,x,y,z\n'
        streams = [io.StringIO(header + '1000000000,0,0,9.81\n'),
                   io.StringIO(header + '995000000,0,0,0\n')]
        with patch.object(Path, 'open', side_effect=streams):
            result = actions.load_phone('unused')
        self.assertAlmostEqual(result['gyroscope'][0][0], -0.005)


if __name__ == "__main__":
    unittest.main()
