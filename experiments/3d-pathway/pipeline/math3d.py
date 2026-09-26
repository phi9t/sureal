"""Numerical camera and fusion primitives used by the repo-owned concept labs."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


def _points(value: ArrayLike) -> FloatArray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must have shape (N, 3)")
    return array


def project(points: ArrayLike, K: ArrayLike, R: ArrayLike, t: ArrayLike) -> tuple[FloatArray, FloatArray]:
    world = _points(points)
    intrinsic = np.asarray(K, dtype=np.float64)
    rotation = np.asarray(R, dtype=np.float64)
    translation = np.asarray(t, dtype=np.float64)
    camera = (rotation @ world.T).T + translation
    if np.any(camera[:, 2] <= 0.0):
        raise ValueError("points must lie in front of the camera")
    homogeneous = (intrinsic @ camera.T).T
    return homogeneous[:, :2] / homogeneous[:, 2, None], camera[:, 2].copy()


def unproject(pixels: ArrayLike, depth: ArrayLike, K: ArrayLike, R: ArrayLike, t: ArrayLike) -> FloatArray:
    image = np.asarray(pixels, dtype=np.float64)
    depths = np.asarray(depth, dtype=np.float64).reshape(-1)
    if image.ndim != 2 or image.shape[1] != 2 or len(image) != len(depths):
        raise ValueError("pixels and depth must have shapes (N, 2) and (N,)")
    rays = (np.linalg.inv(np.asarray(K, dtype=np.float64)) @ np.c_[image, np.ones(len(image))].T).T
    camera = rays * depths[:, None]
    rotation = np.asarray(R, dtype=np.float64)
    translation = np.asarray(t, dtype=np.float64)
    return (rotation.T @ (camera - translation).T).T


def camera_center(R: ArrayLike, t: ArrayLike) -> FloatArray:
    rotation = np.asarray(R, dtype=np.float64)
    return -rotation.T @ np.asarray(t, dtype=np.float64)


def _skew(vector: ArrayLike) -> FloatArray:
    x, y, z = np.asarray(vector, dtype=np.float64)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def fundamental_from_poses(
    K1: ArrayLike, R1: ArrayLike, t1: ArrayLike,
    K2: ArrayLike, R2: ArrayLike, t2: ArrayLike,
) -> FloatArray:
    intrinsic1 = np.asarray(K1, dtype=np.float64)
    intrinsic2 = np.asarray(K2, dtype=np.float64)
    rotation1 = np.asarray(R1, dtype=np.float64)
    rotation2 = np.asarray(R2, dtype=np.float64)
    translation1 = np.asarray(t1, dtype=np.float64)
    translation2 = np.asarray(t2, dtype=np.float64)
    relative_rotation = rotation2 @ rotation1.T
    relative_translation = translation2 - relative_rotation @ translation1
    essential = _skew(relative_translation) @ relative_rotation
    fundamental = np.linalg.inv(intrinsic2).T @ essential @ np.linalg.inv(intrinsic1)
    norm = np.linalg.norm(fundamental)
    return fundamental / norm if norm else fundamental


def symmetric_epipolar_distance(F: ArrayLike, pixel1: ArrayLike, pixel2: ArrayLike) -> float:
    fundamental = np.asarray(F, dtype=np.float64)
    point1 = np.r_[np.asarray(pixel1, dtype=np.float64), 1.0]
    point2 = np.r_[np.asarray(pixel2, dtype=np.float64), 1.0]
    line2 = fundamental @ point1
    line1 = fundamental.T @ point2
    numerator = float(point2 @ fundamental @ point1) ** 2
    denominator = 1.0 / (line1[0] ** 2 + line1[1] ** 2) + 1.0 / (line2[0] ** 2 + line2[1] ** 2)
    return float(np.sqrt(numerator * denominator))


def triangulate_point(
    pixel1: ArrayLike, pixel2: ArrayLike,
    K1: ArrayLike, R1: ArrayLike, t1: ArrayLike,
    K2: ArrayLike, R2: ArrayLike, t2: ArrayLike,
) -> FloatArray:
    projection1 = np.asarray(K1, dtype=np.float64) @ np.c_[np.asarray(R1, dtype=np.float64), np.asarray(t1, dtype=np.float64)]
    projection2 = np.asarray(K2, dtype=np.float64) @ np.c_[np.asarray(R2, dtype=np.float64), np.asarray(t2, dtype=np.float64)]
    u1, v1 = np.asarray(pixel1, dtype=np.float64)
    u2, v2 = np.asarray(pixel2, dtype=np.float64)
    system = np.stack([
        u1 * projection1[2] - projection1[0],
        v1 * projection1[2] - projection1[1],
        u2 * projection2[2] - projection2[0],
        v2 * projection2[2] - projection2[1],
    ])
    _, _, right = np.linalg.svd(system)
    homogeneous = right[-1]
    if abs(homogeneous[3]) < 1e-15:
        raise ValueError("triangulation is degenerate")
    return homogeneous[:3] / homogeneous[3]


def reprojection_residuals(point: ArrayLike, observations: ArrayLike, cameras: list[tuple[ArrayLike, ArrayLike, ArrayLike]]) -> FloatArray:
    world = np.asarray(point, dtype=np.float64).reshape(1, 3)
    predicted = np.array([project(world, *camera)[0][0] for camera in cameras])
    return (predicted - np.asarray(observations, dtype=np.float64)).reshape(-1)


def reprojection_rmse(point: ArrayLike, observations: ArrayLike, cameras: list[tuple[ArrayLike, ArrayLike, ArrayLike]]) -> float:
    residuals = reprojection_residuals(point, observations, cameras)
    return float(np.sqrt(np.mean(residuals * residuals)))


def refine_point_gauss_newton(
    initial: ArrayLike,
    observations: ArrayLike,
    cameras: list[tuple[ArrayLike, ArrayLike, ArrayLike]],
    iterations: int = 10,
) -> tuple[FloatArray, list[float]]:
    point = np.asarray(initial, dtype=np.float64).copy()
    history = [reprojection_rmse(point, observations, cameras)]
    epsilon = 1e-6
    damping = 1e-8
    for _ in range(iterations):
        residual = reprojection_residuals(point, observations, cameras)
        jacobian = np.empty((len(residual), 3), dtype=np.float64)
        for axis in range(3):
            shifted = point.copy()
            shifted[axis] += epsilon
            jacobian[:, axis] = (reprojection_residuals(shifted, observations, cameras) - residual) / epsilon
        step = np.linalg.solve(jacobian.T @ jacobian + damping * np.eye(3), -jacobian.T @ residual)
        point += step
        history.append(reprojection_rmse(point, observations, cameras))
        if np.linalg.norm(step) < 1e-12:
            break
    return point, history


def apply_transform(points: ArrayLike, rotation: ArrayLike, translation: ArrayLike) -> FloatArray:
    return (np.asarray(rotation, dtype=np.float64) @ _points(points).T).T + np.asarray(translation, dtype=np.float64)


def rigid_transform_svd(source: ArrayLike, target: ArrayLike) -> tuple[FloatArray, FloatArray]:
    left = _points(source)
    right = _points(target)
    if left.shape != right.shape or len(left) < 3:
        raise ValueError("paired point arrays must share shape and contain at least three points")
    left_center = left.mean(axis=0)
    right_center = right.mean(axis=0)
    covariance = (left - left_center).T @ (right - right_center)
    u, _, vt = np.linalg.svd(covariance)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0.0:
        vt[-1] *= -1.0
        rotation = vt.T @ u.T
    translation = right_center - rotation @ left_center
    return rotation, translation


def icp(source: ArrayLike, target: ArrayLike, iterations: int = 20) -> tuple[FloatArray, FloatArray, list[float]]:
    source_points = _points(source)
    target_points = _points(target)
    rotation = np.eye(3)
    translation = np.zeros(3)
    history: list[float] = []
    for _ in range(iterations):
        transformed = apply_transform(source_points, rotation, translation)
        distances = np.linalg.norm(transformed[:, None, :] - target_points[None, :, :], axis=2)
        matches = target_points[np.argmin(distances, axis=1)]
        history.append(float(np.sqrt(np.mean(np.min(distances, axis=1) ** 2))))
        delta_rotation, delta_translation = rigid_transform_svd(transformed, matches)
        rotation = delta_rotation @ rotation
        translation = delta_rotation @ translation + delta_translation
        if len(history) > 1 and abs(history[-2] - history[-1]) < 1e-12:
            break
    transformed = apply_transform(source_points, rotation, translation)
    distances = np.linalg.norm(transformed[:, None, :] - target_points[None, :, :], axis=2)
    history.append(float(np.sqrt(np.mean(np.min(distances, axis=1) ** 2))))
    return rotation, translation, history


def fuse_tsdf(previous: float, previous_weight: float, observation: float, observation_weight: float) -> tuple[float, float]:
    if previous_weight < 0.0 or observation_weight < 0.0:
        raise ValueError("TSDF weights must be non-negative")
    total = previous_weight + observation_weight
    if total == 0.0:
        return 0.0, 0.0
    return (previous * previous_weight + observation * observation_weight) / total, total


def normalize_rows(vectors: ArrayLike) -> FloatArray:
    values = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(norms == 0.0):
        raise ValueError("zero vector cannot be normalized")
    return values / norms


def opencv_opengl_camera_transform(matrix: ArrayLike) -> FloatArray:
    value = np.asarray(matrix, dtype=np.float64)
    if value.shape != (4, 4):
        raise ValueError("camera matrix must have shape (4, 4)")
    axis_flip = np.diag([1.0, -1.0, -1.0, 1.0])
    return axis_flip @ value
