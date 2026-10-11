"""Sparse reconstruction data structures for incremental SfM."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from camera.pinhole import project


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class CameraPose:
    """World-to-camera pose."""

    rotation: FloatArray
    translation: FloatArray

    def __init__(self, rotation: ArrayLike, translation: ArrayLike) -> None:
        object.__setattr__(
            self,
            "rotation",
            np.asarray(rotation, dtype=np.float64).reshape(3, 3),
        )
        object.__setattr__(
            self,
            "translation",
            np.asarray(translation, dtype=np.float64).reshape(3),
        )


@dataclass(frozen=True)
class Observation:
    """One 2D observation of a sparse point track."""

    camera_id: str
    track_id: int
    pixel: FloatArray

    def __init__(self, camera_id: str, track_id: int, pixel: ArrayLike) -> None:
        object.__setattr__(self, "camera_id", str(camera_id))
        object.__setattr__(self, "track_id", int(track_id))
        object.__setattr__(
            self,
            "pixel",
            np.asarray(pixel, dtype=np.float64).reshape(2),
        )


@dataclass(frozen=True)
class Reconstruction:
    """Cameras, sparse points, and feature observations in one SfM gauge."""

    intrinsic: FloatArray
    cameras: dict[str, CameraPose]
    points: dict[int, FloatArray]
    observations: list[Observation]
    registered_view_ids: list[str] = field(default_factory=list)
    initial_reprojection_rmse_px: float | None = None
    final_reprojection_rmse_px: float | None = None
    diagnostics: dict[str, object] = field(default_factory=dict)

    def __init__(
        self,
        intrinsic: ArrayLike,
        cameras: dict[str, CameraPose],
        points: dict[int, ArrayLike],
        observations: Iterable[Observation],
        *,
        registered_view_ids: Iterable[str] | None = None,
        initial_reprojection_rmse_px: float | None = None,
        final_reprojection_rmse_px: float | None = None,
        diagnostics: dict[str, object] | None = None,
    ) -> None:
        camera_copy = dict(cameras)
        point_copy = {
            int(track_id): np.asarray(point, dtype=np.float64).reshape(3)
            for track_id, point in points.items()
        }
        observation_copy = list(observations)
        object.__setattr__(
            self,
            "intrinsic",
            np.asarray(intrinsic, dtype=np.float64).reshape(3, 3),
        )
        object.__setattr__(self, "cameras", camera_copy)
        object.__setattr__(self, "points", point_copy)
        object.__setattr__(self, "observations", observation_copy)
        object.__setattr__(
            self,
            "registered_view_ids",
            list(registered_view_ids if registered_view_ids is not None else camera_copy),
        )
        object.__setattr__(
            self,
            "initial_reprojection_rmse_px",
            initial_reprojection_rmse_px,
        )
        object.__setattr__(
            self,
            "final_reprojection_rmse_px",
            final_reprojection_rmse_px,
        )
        object.__setattr__(self, "diagnostics", dict(diagnostics or {}))

    def residuals(self) -> FloatArray:
        """Return stacked reprojection residuals for valid observations."""
        residual_parts: list[FloatArray] = []
        for observation in self.observations:
            camera = self.cameras.get(observation.camera_id)
            point = self.points.get(observation.track_id)
            if camera is None or point is None:
                continue
            predicted, _ = project(
                point.reshape(1, 3),
                self.intrinsic,
                camera.rotation,
                camera.translation,
            )
            residual_parts.append(predicted[0] - observation.pixel)
        if not residual_parts:
            raise ValueError("reconstruction has no projectable observations")
        return np.concatenate(residual_parts).astype(np.float64)

    def reprojection_rmse(self) -> float:
        """Return pixel RMSE over all current observations."""
        residual = self.residuals()
        return float(np.sqrt(np.mean(residual * residual)))

    def with_updates(
        self,
        *,
        cameras: dict[str, CameraPose] | None = None,
        points: dict[int, ArrayLike] | None = None,
        observations: Iterable[Observation] | None = None,
        initial_reprojection_rmse_px: float | None = None,
        final_reprojection_rmse_px: float | None = None,
        diagnostics: dict[str, object] | None = None,
    ) -> "Reconstruction":
        """Return a copy with selected fields replaced."""
        return Reconstruction(
            self.intrinsic,
            cameras if cameras is not None else self.cameras,
            points if points is not None else self.points,
            observations if observations is not None else self.observations,
            registered_view_ids=self.registered_view_ids,
            initial_reprojection_rmse_px=(
                self.initial_reprojection_rmse_px
                if initial_reprojection_rmse_px is None
                else initial_reprojection_rmse_px
            ),
            final_reprojection_rmse_px=(
                self.final_reprojection_rmse_px
                if final_reprojection_rmse_px is None
                else final_reprojection_rmse_px
            ),
            diagnostics=diagnostics if diagnostics is not None else self.diagnostics,
        )
