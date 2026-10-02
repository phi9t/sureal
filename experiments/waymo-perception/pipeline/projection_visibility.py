"""Sparse measured-depth visibility estimate, not dense occlusion ground truth."""
import math
import numpy as np


def measured_projection_visibility(projections, camera_forward_depths, image_shapes,
                                   *, depth_tolerance_m):
    """Retain N×2 native slots and compare depths only at identical camera pixels.

    Forward depth must be derived in the declared camera convention at the
    appropriate exposure time; this function does not validate calibration/time.
    Empty pixels convey no free-space evidence. No interpolation/dilation or
    annotation masks enter the estimate. Tolerance must be supplied explicitly
    and preregistered before scientific comparison.
    """
    p = np.asarray(projections)
    depths = np.asarray(camera_forward_depths, dtype=np.float64)
    if (p.ndim != 2 or p.shape[1] != 6 or p.dtype.kind not in 'iu'
            or depths.shape != (len(p), 2)
            or isinstance(depth_tolerance_m, bool) or not math.isfinite(depth_tolerance_m)
            or depth_tolerance_m < 0):
        raise ValueError('native integer projections, aligned depths and finite nonnegative tolerance required')
    for camera, shape in image_shapes.items():
        if (type(camera) is not int or camera <= 0 or len(shape) != 2
                or any(type(v) is not int or v <= 0 for v in shape)):
            raise ValueError('positive camera identity and native image shape required')
    slots = p.reshape(-1, 2, 3)
    reasons = np.full((len(p), 2), 'no_projection', dtype=object)
    valid = np.zeros((len(p), 2), dtype=bool)
    minimum = {}
    for row in range(len(p)):
        for slot in range(2):
            camera, u, v = map(int, slots[row, slot])
            if camera == 0:
                continue
            if camera not in image_shapes:
                reasons[row, slot] = 'camera_unavailable'
                continue
            height, width = image_shapes[camera]
            if not (0 <= u < width and 0 <= v < height):
                reasons[row, slot] = 'outside_image'
                continue
            depth = depths[row, slot]
            if not np.isfinite(depth) or depth <= 0:
                reasons[row, slot] = 'invalid_forward_depth'
                continue
            key = (camera, u, v)
            minimum[key] = min(depth, minimum.get(key, math.inf))
            valid[row, slot] = True
    supported = np.zeros_like(valid)
    for row, slot in np.argwhere(valid):
        key = tuple(map(int, slots[row, slot]))
        supported[row, slot] = depths[row, slot] <= minimum[key] + depth_tolerance_m
        reasons[row, slot] = 'nearest_measured_support' if supported[row, slot] else 'behind_measured_surface'
    return {'supported': supported, 'reasons': reasons,
            'scope': 'sparse measured support only; camera calibration and exposure timing external'}
