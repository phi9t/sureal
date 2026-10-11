"""Incremental SfM tests on the generated orbit scene."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from features.match import MatchDiagnostics
from scene.orbit import generate_orbit_scene
from sfm.incremental import (
    _build_predicted_pnp_support,
    _predict_constant_velocity_pose,
    _triangulate_inlier_tracks,
    reconstruct_orbit_scene,
    score_orbit_reconstruction,
    score_relative_rotation_stages,
)
from geometry.epipolar import RelativePose
from sfm.initialize import PairMatch, SfmView
from sfm.reconstruction import CameraPose
from sfm.tracks import TrackGraph


def _strip_ground_truth(frame: dict) -> dict:
    stripped = dict(frame)
    for key in (
        "azimuth_degrees",
        "elevation_degrees",
        "R_world_to_camera",
        "t_world_to_camera_m",
        "camera_center_world_m",
        "depth_path",
        "normal_path",
        "surface_points_path",
        "surface_normals_path",
    ):
        stripped.pop(key, None)
    return stripped


def _pose_signature(reconstruction) -> tuple[tuple[str, ...], np.ndarray, np.ndarray]:
    camera_ids = tuple(reconstruction.registered_view_ids)
    rotations = np.stack(
        [reconstruction.cameras[camera_id].rotation for camera_id in camera_ids],
        axis=0,
    )
    translations = np.stack(
        [reconstruction.cameras[camera_id].translation for camera_id in camera_ids],
        axis=0,
    )
    return camera_ids, rotations, translations


def _rotation_z(angle_radians: float) -> np.ndarray:
    cosine = float(np.cos(angle_radians))
    sine = float(np.sin(angle_radians))
    return np.array(
        [
            [cosine, -sine, 0.0],
            [sine, cosine, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def _apply_relative(
    relative_rotation: np.ndarray,
    relative_translation: np.ndarray,
    pose: CameraPose,
) -> CameraPose:
    return CameraPose(
        relative_rotation @ pose.rotation,
        relative_rotation @ pose.translation + relative_translation,
    )


class IncrementalSfmTest(unittest.TestCase):
    def test_constant_velocity_predictor_extrapolates_sequence_pose(self) -> None:
        """Catches reversed world-to-camera composition in pose prediction."""
        view_order = ["frame-000", "frame-001", "frame-002"]
        step_rotation = _rotation_z(np.deg2rad(7.5))
        step_translation = np.array([0.25, -0.15, 0.4], dtype=np.float64)
        first = CameraPose(_rotation_z(np.deg2rad(3.0)), np.array([1.0, 2.0, 3.0]))
        second = _apply_relative(step_rotation, step_translation, first)
        third = _apply_relative(step_rotation, step_translation, second)

        predicted, source_pair = _predict_constant_velocity_pose(
            view_order,
            2,
            {0, 1},
            {"frame-000": first, "frame-001": second},
        )

        self.assertEqual(source_pair, ("frame-000", "frame-001"))
        np.testing.assert_allclose(predicted.rotation, third.rotation, atol=1e-12)
        np.testing.assert_allclose(predicted.translation, third.translation, atol=1e-12)

        predicted_back, source_pair_back = _predict_constant_velocity_pose(
            view_order,
            0,
            {1, 2},
            {"frame-001": second, "frame-002": third},
        )

        self.assertEqual(source_pair_back, ("frame-002", "frame-001"))
        np.testing.assert_allclose(predicted_back.rotation, first.rotation, atol=1e-12)
        np.testing.assert_allclose(predicted_back.translation, first.translation, atol=1e-12)

    def test_predicted_pnp_support_matches_projected_tracks(self) -> None:
        """Catches regressions to pair-only support for incremental PnP."""
        image = np.zeros((24, 24), dtype=np.float64)
        source_descriptor = np.array([[1.0, 0.0, 0.0]], dtype=np.float64)
        source = SfmView(
            "frame-000",
            image,
            np.eye(3, dtype=np.float64),
            np.array([[8.0, 8.0]], dtype=np.float64),
            source_descriptor,
            1,
        )
        second = SfmView(
            "frame-001",
            image,
            np.eye(3, dtype=np.float64),
            np.array([[8.0, 8.0]], dtype=np.float64),
            source_descriptor,
            1,
        )
        candidate = SfmView(
            "frame-002",
            image,
            np.eye(3, dtype=np.float64),
            np.array([[8.4, 8.1], [10.0, 8.0], [2.0, 2.0]], dtype=np.float64),
            np.array(
                [
                    [1.0, 0.0, 0.0],
                    [0.1, 0.9, 0.0],
                    [0.0, 1.0, 0.0],
                ],
                dtype=np.float64,
            ),
            1,
        )
        graph = TrackGraph()
        track_id = graph.add_match(
            source.view_id,
            0,
            source.keypoints[0],
            second.view_id,
            0,
            second.keypoints[0],
        )
        assert track_id is not None

        support = _build_predicted_pnp_support(
            candidate,
            2,
            CameraPose(np.eye(3), np.zeros(3)),
            [source, second, candidate],
            {"frame-000": CameraPose(np.eye(3), np.zeros(3))},
            graph,
            {track_id: np.array([8.0, 8.0, 1.0], dtype=np.float64)},
            set(),
        )

        self.assertEqual(support.track_ids, [track_id])
        self.assertEqual(support.candidate_feature_indices, [0])
        np.testing.assert_allclose(support.object_points, [[8.0, 8.0, 1.0]])
        np.testing.assert_allclose(support.image_points, [[8.4, 8.1]])

    def test_pose_filter_blocks_aliased_pair_track_growth(self) -> None:
        """Catches growth tracks that disagree with already-estimated cameras."""
        image = np.zeros((24, 24), dtype=np.float64)
        left = SfmView(
            "frame-000",
            image,
            np.eye(3, dtype=np.float64),
            np.array([[8.0, 8.0]], dtype=np.float64),
            np.ones((1, 3), dtype=np.float64),
            1,
        )
        right = SfmView(
            "frame-001",
            image,
            np.eye(3, dtype=np.float64),
            np.array([[8.0, 12.0]], dtype=np.float64),
            np.ones((1, 3), dtype=np.float64),
            1,
        )
        pair = PairMatch(
            0,
            1,
            left.view_id,
            right.view_id,
            np.array([0], dtype=np.int64),
            np.array([0], dtype=np.int64),
            left.keypoints,
            right.keypoints,
            np.array([True], dtype=np.bool_),
            RelativePose(
                np.eye(3, dtype=np.float64),
                np.array([-1.0, 0.0, 0.0], dtype=np.float64),
                np.eye(3, dtype=np.float64),
            ),
            MatchDiagnostics(1, 1, 1),
            1,
        )
        graph = TrackGraph()
        points: dict[int, np.ndarray] = {}

        _triangulate_inlier_tracks(
            graph,
            points,
            pair,
            {
                left.view_id: CameraPose(np.eye(3), np.zeros(3)),
                right.view_id: CameraPose(np.eye(3), np.array([-1.0, 0.0, 0.0])),
            },
            [left, right],
            set(),
            new_tracks_only=True,
            pose_inlier_threshold_px=1.5,
        )

        self.assertEqual(graph.tracks(), {})
        self.assertEqual(points, {})

    def test_incremental_sfm_registers_every_smoke_orbit_view(self) -> None:
        """Catches reconstructions that stop after the initialization pair."""
        with tempfile.TemporaryDirectory() as temporary:
            scene_root = Path(temporary) / "orbit"
            manifest = generate_orbit_scene(scene_root, "smoke")

            reconstruction = reconstruct_orbit_scene(scene_root, manifest, "smoke")
            metrics = score_orbit_reconstruction(reconstruction, manifest)

        self.assertEqual(
            reconstruction.registered_view_ids,
            [frame["id"] for frame in manifest["frames"]],
        )
        self.assertEqual(metrics["registered_view_count"], len(manifest["frames"]))
        self.assertLess(metrics["final_reprojection_rmse_px"], metrics["initial_reprojection_rmse_px"])
        self.assertTrue(np.isfinite(metrics["ate_m"]))
        self.assertTrue(np.isfinite(metrics["mean_rotation_error_deg"]))

    def test_full_orbit_profile_meets_accuracy_targets(self) -> None:
        """Catches pose estimators that only work on the tiny smoke fixture."""
        with tempfile.TemporaryDirectory() as temporary:
            scene_root = Path(temporary) / "orbit"
            manifest = generate_orbit_scene(scene_root, "full")

            reconstruction = reconstruct_orbit_scene(scene_root, manifest, "full")
            metrics = score_orbit_reconstruction(reconstruction, manifest)
            stage_scores = score_relative_rotation_stages(reconstruction, manifest)

        self.assertEqual(
            reconstruction.registered_view_ids,
            [frame["id"] for frame in manifest["frames"]],
        )
        self.assertEqual(metrics["registered_view_count"], 7)
        diagnostics = json.dumps(stage_scores, sort_keys=True)
        self.assertLess(metrics["mean_rotation_error_deg"], 1.0, diagnostics)
        self.assertLess(metrics["max_rotation_error_deg"], 2.0, diagnostics)
        self.assertLess(metrics["ate_m"], 0.05)

    def test_estimation_is_unchanged_when_ground_truth_fields_are_hidden(self) -> None:
        """Pose, azimuth, depth and surface truth are score-only fields."""
        with tempfile.TemporaryDirectory() as temporary:
            scene_root = Path(temporary) / "orbit"
            manifest = generate_orbit_scene(scene_root, "smoke")
            hidden_manifest = {
                **manifest,
                "frames": [_strip_ground_truth(frame) for frame in manifest["frames"]],
            }

            clean = reconstruct_orbit_scene(scene_root, manifest, "smoke")
            hidden = reconstruct_orbit_scene(scene_root, hidden_manifest, "smoke")

        clean_ids, clean_rotations, clean_translations = _pose_signature(clean)
        hidden_ids, hidden_rotations, hidden_translations = _pose_signature(hidden)
        self.assertEqual(clean_ids, hidden_ids)
        self.assertEqual(len(clean.points), len(hidden.points))
        np.testing.assert_allclose(clean_rotations, hidden_rotations)
        np.testing.assert_allclose(clean_translations, hidden_translations)


if __name__ == "__main__":
    unittest.main()
