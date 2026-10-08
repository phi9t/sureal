"""Numpy oriented-box geometry in the vehicle frame.

An oriented box is ``[center_x, center_y, center_z, length, width, height,
heading]`` in metres and radians, with z at the box centre, length along local
x, width along local y, and heading wrapped by producers to ``[-pi, pi)``.
BEV corners are returned in local-box order ``(-x,-y), (+x,-y), (+x,+y),
(-x,+y)`` transformed into the vehicle frame.
"""

import numpy as np


def wrap_heading(angles):
    """Wrap finite headings with ``(a + pi) % 2pi - pi``; ``-pi`` and ``pi`` both become ``-pi``."""
    angles = np.asarray(angles, dtype=np.float64)
    if not np.isfinite(angles).all():
        raise ValueError("finite oriented-box headings required")
    return (angles + np.pi) % (2 * np.pi) - np.pi


def point_membership(points, box):
    """Return the inclusive no-tolerance membership mask for one oriented box."""
    points = _points(points)
    box = _box(box)
    delta = points - box[:3]
    c, s = np.cos(box[6]), np.sin(box[6])
    local_x = delta[:, 0] * c + delta[:, 1] * s
    local_y = -delta[:, 0] * s + delta[:, 1] * c
    return (
        (np.abs(local_x) <= box[3] / 2)
        & (np.abs(local_y) <= box[4] / 2)
        & (np.abs(delta[:, 2]) <= box[5] / 2)
    )


def count_points_in_box(points, box):
    """Count points whose coordinates are inside or exactly on one oriented box."""
    return int(np.count_nonzero(point_membership(points, box)))


def point_membership_many(points, boxes):
    """Return a ``len(boxes) x len(points)`` inclusive membership mask."""
    points = _points(points)
    boxes = _boxes(boxes)
    if len(boxes) == 0:
        return np.zeros((0, len(points)), dtype=bool)
    return np.stack([point_membership(points, box) for box in boxes], axis=0)


def bev_corners(boxes):
    """Return BEV corners in local order ``(-x,-y), (+x,-y), (+x,+y), (-x,+y)``."""
    boxes = np.asarray(boxes, dtype=np.float64)
    single = boxes.shape == (7,)
    boxes = _boxes(boxes)
    local = np.array(
        [
            [-0.5, -0.5],
            [0.5, -0.5],
            [0.5, 0.5],
            [-0.5, 0.5],
        ],
        dtype=np.float64,
    )
    offsets = local[None, :, :] * boxes[:, None, 3:5]
    c = np.cos(boxes[:, 6])[:, None]
    s = np.sin(boxes[:, 6])[:, None]
    corners = np.empty((len(boxes), 4, 2), dtype=np.float64)
    corners[:, :, 0] = boxes[:, None, 0] + offsets[:, :, 0] * c - offsets[:, :, 1] * s
    corners[:, :, 1] = boxes[:, None, 1] + offsets[:, :, 0] * s + offsets[:, :, 1] * c
    return corners[0] if single else corners


def nearest_bev_rectangles(boxes):
    """Return nearest axis-aligned BEV rectangles as ``[min_x, min_y, max_x, max_y]``."""
    boxes = _boxes(boxes)
    yaw = np.abs((boxes[:, 6] + np.pi / 2) % np.pi - np.pi / 2)
    extent = np.where((yaw > np.pi / 4)[:, None], boxes[:, [4, 3]], boxes[:, 3:5])
    return _rectangles_from_extent(boxes, extent)


def enclosing_bev_rectangles(boxes):
    """Return enclosing axis-aligned BEV rectangles as ``[min_x, min_y, max_x, max_y]``."""
    boxes = _boxes(boxes)
    c = np.abs(np.cos(boxes[:, 6]))
    s = np.abs(np.sin(boxes[:, 6]))
    extent = np.stack((c * boxes[:, 3] + s * boxes[:, 4], s * boxes[:, 3] + c * boxes[:, 4]), axis=1)
    return _rectangles_from_extent(boxes, extent)


def axis_aligned_bev_iou(first, second):
    """Return pairwise IoU for axis-aligned BEV rectangles, zero when union is empty."""
    first = _rectangles(first)
    second = _rectangles(second)
    lower = np.maximum(first[:, None, :2], second[None, :, :2])
    upper = np.minimum(first[:, None, 2:], second[None, :, 2:])
    intersection = np.maximum(upper - lower, 0).prod(axis=-1)
    area_first = np.maximum(first[:, 2:] - first[:, :2], 0).prod(axis=-1)
    area_second = np.maximum(second[:, 2:] - second[:, :2], 0).prod(axis=-1)
    union = area_first[:, None] + area_second[None, :] - intersection
    return np.divide(intersection, union, out=np.zeros_like(intersection), where=union > 0)


def _points(points):
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError("finite Nx3 oriented-box points required")
    return points


def _box(box):
    box = np.asarray(box, dtype=np.float64)
    if box.shape != (7,) or not np.isfinite(box).all() or np.any(box[3:6] <= 0):
        raise ValueError("finite oriented box [x,y,z,length,width,height,heading] with positive dimensions required")
    return box


def _boxes(boxes):
    boxes = np.asarray(boxes, dtype=np.float64)
    if boxes.shape == (7,):
        boxes = boxes.reshape(1, 7)
    if boxes.ndim != 2 or boxes.shape[1] != 7 or not np.isfinite(boxes).all() or np.any(boxes[:, 3:6] <= 0):
        raise ValueError("finite oriented-box Nx7 array with positive dimensions required")
    return boxes


def _rectangles(rectangles):
    rectangles = np.asarray(rectangles, dtype=np.float64)
    if rectangles.shape == (4,):
        rectangles = rectangles.reshape(1, 4)
    if rectangles.ndim != 2 or rectangles.shape[1] != 4 or not np.isfinite(rectangles).all():
        raise ValueError("finite BEV rectangle Nx4 array required")
    if np.any(rectangles[:, :2] > rectangles[:, 2:]):
        raise ValueError("ordered BEV rectangles required")
    return rectangles


def _rectangles_from_extent(boxes, extent):
    return np.concatenate((boxes[:, :2] - extent / 2, boxes[:, :2] + extent / 2), axis=1)
