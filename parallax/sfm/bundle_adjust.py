"""Levenberg-Marquardt bundle adjustment with sparse Schur elimination."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy import sparse
from scipy.sparse.linalg import spsolve

from geometry.pnp import rotation_matrix_from_vector, rotation_vector_from_matrix
from sfm.reconstruction import CameraPose, Observation, Reconstruction


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class BundleAdjustmentResult:
    reconstruction: Reconstruction
    initial_rmse_px: float
    final_rmse_px: float
    iterations: int
    used_schur_complement: bool


def _project_safe(
    point: FloatArray,
    intrinsic: FloatArray,
    pose: CameraPose,
) -> FloatArray:
    camera = pose.rotation @ point + pose.translation
    if camera[2] <= 1e-9 or not np.all(np.isfinite(camera)):
        return np.array([1e6, 1e6], dtype=np.float64)
    homogeneous = intrinsic @ camera
    return homogeneous[:2] / homogeneous[2]


def _residual_vector(
    camera_ids: list[str],
    point_ids: list[int],
    observations: list[Observation],
    intrinsic: FloatArray,
    camera_params: FloatArray,
    point_params: FloatArray,
) -> FloatArray:
    camera_index = {camera_id: index for index, camera_id in enumerate(camera_ids)}
    point_index = {track_id: index for index, track_id in enumerate(point_ids)}
    residual = np.empty(2 * len(observations), dtype=np.float64)
    for obs_index, observation in enumerate(observations):
        c_index = camera_index[observation.camera_id]
        p_index = point_index[observation.track_id]
        params = camera_params[c_index]
        pose = CameraPose(
            rotation_matrix_from_vector(params[:3]),
            params[3:],
        )
        predicted = _project_safe(point_params[p_index], intrinsic, pose)
        residual[2 * obs_index : 2 * obs_index + 2] = predicted - observation.pixel
    return residual


def _robust_loss_value(
    residual: FloatArray,
    *,
    loss: str,
    scale: float,
) -> float:
    if scale <= 0.0:
        raise ValueError("robust loss scale must be positive")
    vectors = residual.reshape(-1, 2)
    norms = np.linalg.norm(vectors, axis=1)
    if loss == "linear":
        return float(residual @ residual)
    if loss == "huber":
        squared = norms * norms
        return float(
            np.sum(
                np.where(
                    norms <= scale,
                    squared,
                    2.0 * scale * norms - scale * scale,
                )
            )
        )
    if loss == "cauchy":
        return float(np.sum(scale * scale * np.log1p((norms / scale) ** 2)))
    raise ValueError(f"unsupported robust loss: {loss}")


def _robust_sqrt_weights(
    residual: FloatArray,
    *,
    loss: str,
    scale: float,
) -> FloatArray:
    if scale <= 0.0:
        raise ValueError("robust loss scale must be positive")
    vectors = residual.reshape(-1, 2)
    norms = np.linalg.norm(vectors, axis=1)
    if loss == "linear":
        observation_weights = np.ones(len(vectors), dtype=np.float64)
    elif loss == "huber":
        observation_weights = np.ones(len(vectors), dtype=np.float64)
        large = norms > scale
        observation_weights[large] = scale / np.maximum(norms[large], 1e-12)
    elif loss == "cauchy":
        observation_weights = 1.0 / (1.0 + (norms / scale) ** 2)
    else:
        raise ValueError(f"unsupported robust loss: {loss}")
    return np.repeat(np.sqrt(observation_weights), 2)


def _pack(
    reconstruction: Reconstruction,
    fixed_camera_ids: set[str],
) -> tuple[list[str], list[str], list[int], FloatArray, FloatArray]:
    variable_camera_ids = [
        camera_id
        for camera_id in reconstruction.registered_view_ids
        if camera_id not in fixed_camera_ids
    ]
    camera_ids = list(reconstruction.registered_view_ids)
    if set(camera_ids) != set(reconstruction.cameras):
        camera_ids = sorted(reconstruction.cameras)
    all_camera_params = np.array(
        [
            np.r_[
                rotation_vector_from_matrix(reconstruction.cameras[camera_id].rotation),
                reconstruction.cameras[camera_id].translation,
            ]
            for camera_id in camera_ids
        ],
        dtype=np.float64,
    )
    variable_params = np.array(
        [
            np.r_[
                rotation_vector_from_matrix(reconstruction.cameras[camera_id].rotation),
                reconstruction.cameras[camera_id].translation,
            ]
            for camera_id in variable_camera_ids
        ],
        dtype=np.float64,
    )
    point_ids = sorted(reconstruction.points)
    points = np.array([reconstruction.points[track_id] for track_id in point_ids], dtype=np.float64)
    return camera_ids, variable_camera_ids, point_ids, all_camera_params, points


def _compose_camera_params(
    camera_ids: list[str],
    variable_camera_ids: list[str],
    fixed_params: FloatArray,
    variables: FloatArray,
) -> FloatArray:
    variable_by_id = {
        camera_id: variables[index]
        for index, camera_id in enumerate(variable_camera_ids)
    }
    return np.array(
        [
            variable_by_id.get(camera_id, fixed_params[index])
            for index, camera_id in enumerate(camera_ids)
        ],
        dtype=np.float64,
    )


def _sparse_jacobian(
    camera_ids: list[str],
    variable_camera_ids: list[str],
    point_ids: list[int],
    observations: list[Observation],
    intrinsic: FloatArray,
    fixed_camera_params: FloatArray,
    camera_variables: FloatArray,
    point_params: FloatArray,
    residual: FloatArray,
) -> sparse.csr_matrix:
    camera_variable_index = {
        camera_id: index for index, camera_id in enumerate(variable_camera_ids)
    }
    point_index = {track_id: index for index, track_id in enumerate(point_ids)}
    columns = 6 * len(variable_camera_ids) + 3 * len(point_ids)
    jacobian = sparse.lil_matrix((len(residual), columns), dtype=np.float64)
    epsilon = 1e-6

    for obs_index, observation in enumerate(observations):
        rows = slice(2 * obs_index, 2 * obs_index + 2)
        base = residual[rows]
        c_variable = camera_variable_index.get(observation.camera_id)
        if c_variable is not None:
            for axis in range(6):
                shifted_cameras = camera_variables.copy()
                shifted_cameras[c_variable, axis] += epsilon
                params = _compose_camera_params(
                    camera_ids,
                    variable_camera_ids,
                    fixed_camera_params,
                    shifted_cameras,
                )
                shifted = _residual_vector(
                    camera_ids,
                    point_ids,
                    [observation],
                    intrinsic,
                    params,
                    point_params,
                )
                jacobian[rows, 6 * c_variable + axis] = (shifted - base) / epsilon
        p_index = point_index[observation.track_id]
        point_column = 6 * len(variable_camera_ids) + 3 * p_index
        for axis in range(3):
            shifted_points = point_params.copy()
            shifted_points[p_index, axis] += epsilon
            params = _compose_camera_params(
                camera_ids,
                variable_camera_ids,
                fixed_camera_params,
                camera_variables,
            )
            shifted = _residual_vector(
                camera_ids,
                point_ids,
                [observation],
                intrinsic,
                params,
                shifted_points,
            )
            jacobian[rows, point_column + axis] = (shifted - base) / epsilon
    return jacobian.tocsr()


def _schur_step(
    normal: sparse.csr_matrix,
    gradient: FloatArray,
    camera_variable_count: int,
    point_count: int,
    damping: float,
) -> FloatArray:
    camera_size = 6 * camera_variable_count
    point_size = 3 * point_count
    if point_size == 0:
        return np.asarray(
            spsolve(
                normal + damping * sparse.eye(normal.shape[0], format="csr"),
                -gradient,
            ),
            dtype=np.float64,
        )
    damped = normal + damping * sparse.eye(normal.shape[0], format="csr")
    if camera_size == 0:
        point_delta = np.empty(point_size, dtype=np.float64)
        c_block = damped.tocsr()
        for point_index in range(point_count):
            start = 3 * point_index
            block = c_block[start : start + 3, start : start + 3].toarray()
            point_delta[start : start + 3] = np.linalg.solve(
                block,
                -gradient[start : start + 3],
            )
        return point_delta

    a_block = damped[:camera_size, :camera_size].tolil()
    b_block = damped[:camera_size, camera_size:].tocsr()
    c_block = damped[camera_size:, camera_size:].tocsr()
    g_camera = gradient[:camera_size]
    g_points = gradient[camera_size:]
    schur = a_block.copy()
    rhs = -g_camera.copy()
    inverse_point_blocks: list[FloatArray] = []
    for point_index in range(point_count):
        start = 3 * point_index
        block = c_block[start : start + 3, start : start + 3].toarray()
        inverse = np.linalg.inv(block)
        inverse_point_blocks.append(inverse)
        b_columns = b_block[:, start : start + 3].toarray()
        schur -= sparse.csr_matrix(b_columns @ inverse @ b_columns.T)
        rhs += b_columns @ inverse @ g_points[start : start + 3]
    camera_delta = np.asarray(spsolve(schur.tocsr(), rhs), dtype=np.float64)
    point_delta = np.empty(point_size, dtype=np.float64)
    for point_index, inverse in enumerate(inverse_point_blocks):
        start = 3 * point_index
        b_columns = b_block[:, start : start + 3].toarray()
        point_delta[start : start + 3] = -inverse @ (
            g_points[start : start + 3] + b_columns.T @ camera_delta
        )
    return np.r_[camera_delta, point_delta]


def _unpack(
    reconstruction: Reconstruction,
    camera_ids: list[str],
    variable_camera_ids: list[str],
    point_ids: list[int],
    fixed_camera_params: FloatArray,
    camera_variables: FloatArray,
    point_params: FloatArray,
) -> Reconstruction:
    params = _compose_camera_params(
        camera_ids,
        variable_camera_ids,
        fixed_camera_params,
        camera_variables,
    )
    cameras = {
        camera_id: CameraPose(rotation_matrix_from_vector(row[:3]), row[3:])
        for camera_id, row in zip(camera_ids, params)
    }
    points = {
        track_id: point.copy()
        for track_id, point in zip(point_ids, point_params)
    }
    return reconstruction.with_updates(cameras=cameras, points=points)


def bundle_adjust(
    reconstruction: Reconstruction,
    *,
    fixed_camera_ids: tuple[str, ...] = (),
    max_iterations: int = 8,
    robust_loss: str = "huber",
    robust_scale_px: float = 2.0,
) -> BundleAdjustmentResult:
    """Refine cameras and sparse points with damped Schur-complement LM."""
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")
    fixed = set(fixed_camera_ids)
    observations = [
        observation
        for observation in reconstruction.observations
        if observation.camera_id in reconstruction.cameras
        and observation.track_id in reconstruction.points
    ]
    if not observations:
        raise ValueError("bundle adjustment needs observations")
    camera_ids, variable_camera_ids, point_ids, fixed_camera_params, point_params = _pack(
        reconstruction,
        fixed,
    )
    camera_variables = np.array(
        [
            np.r_[
                rotation_vector_from_matrix(reconstruction.cameras[camera_id].rotation),
                reconstruction.cameras[camera_id].translation,
            ]
            for camera_id in variable_camera_ids
        ],
        dtype=np.float64,
    )
    camera_params = _compose_camera_params(
        camera_ids,
        variable_camera_ids,
        fixed_camera_params,
        camera_variables,
    )
    residual = _residual_vector(
        camera_ids,
        point_ids,
        observations,
        reconstruction.intrinsic,
        camera_params,
        point_params,
    )
    initial_rmse = float(np.sqrt(np.mean(residual * residual)))
    best_loss = _robust_loss_value(
        residual,
        loss=robust_loss,
        scale=robust_scale_px,
    )
    damping = 1e-3
    iterations = 0

    for _ in range(max_iterations):
        jacobian = _sparse_jacobian(
            camera_ids,
            variable_camera_ids,
            point_ids,
            observations,
            reconstruction.intrinsic,
            fixed_camera_params,
            camera_variables,
            point_params,
            residual,
        )
        sqrt_weights = _robust_sqrt_weights(
            residual,
            loss=robust_loss,
            scale=robust_scale_px,
        )
        weighted_jacobian = jacobian.multiply(sqrt_weights[:, None])
        weighted_residual = sqrt_weights * residual
        normal = weighted_jacobian.T @ weighted_jacobian
        gradient = np.asarray(
            weighted_jacobian.T @ weighted_residual,
            dtype=np.float64,
        ).reshape(-1)
        try:
            step = _schur_step(
                normal.tocsr(),
                gradient,
                len(variable_camera_ids),
                len(point_ids),
                damping,
            )
        except (np.linalg.LinAlgError, ValueError):
            damping *= 10.0
            continue
        if not np.all(np.isfinite(step)):
            damping *= 10.0
            continue
        camera_step_size = 6 * len(variable_camera_ids)
        candidate_cameras = camera_variables.copy()
        candidate_points = point_params.copy()
        if camera_step_size:
            candidate_cameras += step[:camera_step_size].reshape(-1, 6)
        candidate_points += step[camera_step_size:].reshape(-1, 3)
        candidate_params = _compose_camera_params(
            camera_ids,
            variable_camera_ids,
            fixed_camera_params,
            candidate_cameras,
        )
        candidate_residual = _residual_vector(
            camera_ids,
            point_ids,
            observations,
            reconstruction.intrinsic,
            candidate_params,
            candidate_points,
        )
        candidate_loss = _robust_loss_value(
            candidate_residual,
            loss=robust_loss,
            scale=robust_scale_px,
        )
        if candidate_loss < best_loss:
            camera_variables = candidate_cameras
            point_params = candidate_points
            residual = candidate_residual
            best_loss = candidate_loss
            damping = max(damping * 0.4, 1e-10)
            iterations += 1
            if np.linalg.norm(step) < 1e-9:
                break
        else:
            damping *= 8.0

    refined = _unpack(
        reconstruction,
        camera_ids,
        variable_camera_ids,
        point_ids,
        fixed_camera_params,
        camera_variables,
        point_params,
    )
    final_rmse = refined.reprojection_rmse()
    refined = refined.with_updates(
        initial_reprojection_rmse_px=initial_rmse,
        final_reprojection_rmse_px=final_rmse,
    )
    return BundleAdjustmentResult(
        refined,
        initial_rmse,
        final_rmse,
        iterations,
        used_schur_complement=True,
    )
