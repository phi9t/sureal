"""Compatibility exports for numerical camera, geometry and fusion primitives."""

from camera.pinhole import project, unproject
from camera.pose import camera_center, fundamental_from_poses, symmetric_epipolar_distance
from fusion.tsdf import fuse_tsdf
from geometry.align import (
    apply_transform,
    icp,
    normalize_rows,
    opencv_opengl_camera_transform,
    rigid_transform_svd,
)
from geometry.triangulate import (
    refine_point_gauss_newton,
    reprojection_residuals,
    reprojection_rmse,
    triangulate_point,
)


__all__ = [
    "apply_transform",
    "camera_center",
    "fundamental_from_poses",
    "fuse_tsdf",
    "icp",
    "normalize_rows",
    "opencv_opengl_camera_transform",
    "project",
    "refine_point_gauss_newton",
    "reprojection_residuals",
    "reprojection_rmse",
    "rigid_transform_svd",
    "symmetric_epipolar_distance",
    "triangulate_point",
    "unproject",
]
