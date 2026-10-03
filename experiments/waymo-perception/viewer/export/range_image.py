"""Range image -> vehicle-frame points, following the pinned upstream conventions.

No TensorFlow. Equations mirror waymo_open_dataset.utils.range_image_utils at
commit 99a4cb3: half-pixel inclination sampling, row reversal (row 0 is the
top beam), azimuth from column index corrected by the extrinsic yaw, and
Rz(yaw) Ry(pitch) Rx(roll) per-pixel motion compensation for the TOP LiDAR.
"""
import numpy as np

from .manifest import inverse_rigid


def inclinations(height, incl_min, incl_max, values=None):
    """Beam inclinations per image row, reversed so row 0 is the top beam."""
    if values is not None and len(values) > 0:
        inc = np.asarray(values, dtype=np.float64)
        if inc.shape != (height,):
            raise ValueError("beam inclination count does not match range image height")
    else:
        if not np.isfinite([incl_min, incl_max]).all() or incl_min > incl_max:
            raise ValueError("invalid inclination bounds")
        inc = (np.arange(height, dtype=np.float64) + 0.5) / height * (incl_max - incl_min) + incl_min
    if not np.isfinite(inc).all():
        raise ValueError("non-finite inclinations")
    return inc[::-1].copy()


def azimuths(width, extrinsic):
    """Azimuth per image column in the sensor frame, including the extrinsic yaw correction."""
    ext = np.asarray(extrinsic, dtype=np.float64).reshape(4, 4)
    correction = np.arctan2(ext[1, 0], ext[0, 0])
    ratios = (np.arange(width, 0, -1, dtype=np.float64) - 0.5) / width
    return (ratios * 2.0 - 1.0) * np.pi - correction


def rotation_rpy(roll, pitch, yaw):
    """Batched Rz(yaw) @ Ry(pitch) @ Rx(roll), shape (n, 3, 3)."""
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    rot = np.stack(
        (
            cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr,
            sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr,
            -sp, cp * sr, cp * cr,
        ),
        axis=-1,
    )
    return rot.reshape(-1, 3, 3)


def range_image_to_vehicle(range_image, extrinsic, incl, azim, pixel_pose=None, world_from_vehicle=None):
    """Convert one range image return into vehicle-frame points.

    Returns a dict with row-major valid-pixel ordering (np.argwhere order):
    xyz (n,3) float64 vehicle metres, rows, cols, range, intensity, elongation, nlz.
    """
    ri = np.asarray(range_image, dtype=np.float64)
    if ri.ndim != 3 or ri.shape[2] != 4:
        raise ValueError("range image must have shape (H, W, 4)")
    h, w = ri.shape[:2]
    if incl.shape != (h,) or azim.shape != (w,):
        raise ValueError("inclination/azimuth tables do not match the range image")
    ext = np.asarray(extrinsic, dtype=np.float64).reshape(4, 4)
    rng = ri[..., 0]
    valid = np.isfinite(rng) & (rng > 0)
    pixels = np.argwhere(valid)
    rows, cols = pixels[:, 0], pixels[:, 1]
    r = rng[rows, cols]
    e = incl[rows]
    a = azim[cols]
    cos_e = np.cos(e)
    xyz = np.column_stack((r * cos_e * np.cos(a), r * cos_e * np.sin(a), r * np.sin(e)))
    xyz = xyz @ ext[:3, :3].T + ext[:3, 3]
    if pixel_pose is not None:
        if world_from_vehicle is None:
            raise ValueError("motion compensation needs the frame pose")
        pp = np.asarray(pixel_pose, dtype=np.float64)
        if pp.shape != (h, w, 6):
            raise ValueError("pixel pose must have shape (H, W, 6)")
        sel = pp[rows, cols]
        if not np.isfinite(sel).all():
            raise ValueError("non-finite pixel poses on valid pixels")
        rot = rotation_rpy(sel[:, 0], sel[:, 1], sel[:, 2])
        xyz = np.einsum("nij,nj->ni", rot, xyz) + sel[:, 3:6]
        inv = inverse_rigid(np.asarray(world_from_vehicle, dtype=np.float64).reshape(4, 4))
        xyz = xyz @ inv[:3, :3].T + inv[:3, 3]
    return {
        "xyz": xyz,
        "rows": rows,
        "cols": cols,
        "range": r,
        "intensity": ri[rows, cols, 1],
        "elongation": ri[rows, cols, 2],
        "nlz": ri[rows, cols, 3] > 0,
    }
