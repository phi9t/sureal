"""Parity fixtures for detection producers migrated to geometry.oriented_box."""
import math
import unittest

import numpy as np

from geometry import oriented_box_test_support as support


def _old_decoded_heading_wrap(angles):
    return (np.asarray(angles, dtype=np.float64) + np.pi) % (2 * np.pi) - np.pi


def _old_v3_canonical_wrap(angles):
    return (np.asarray(angles, dtype=np.float64) + np.pi) % (2 * np.pi) - np.pi


def _old_sustained_groundtruth_wrap(angles):
    return (np.asarray(angles, dtype=np.float64) + math.pi) % (2 * math.pi) - math.pi


def _old_overfit_target_wrap(angles):
    return (np.asarray(angles, dtype=np.float64) + np.pi) % (2 * np.pi) - np.pi


def _old_prediction_record_point_count(points, box):
    points = np.asarray(points, dtype=np.float64)
    box = np.asarray(box, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError("aligned finite points required")
    if box.shape != (7,) or not np.isfinite(box).all() or np.any(box[3:6] <= 0):
        raise ValueError("finite positive native box required")
    c, s = math.cos(box[6]), math.sin(box[6])
    delta = points - box[:3]
    local_x = c * delta[:, 0] + s * delta[:, 1]
    local_y = -s * delta[:, 0] + c * delta[:, 1]
    inside = (
        (np.abs(local_x) <= box[3] / 2)
        & (np.abs(local_y) <= box[4] / 2)
        & (np.abs(delta[:, 2]) <= box[5] / 2)
    )
    return int(np.count_nonzero(inside))


def _old_boxes(boxes):
    boxes = np.asarray(boxes, dtype=np.float64)
    if boxes.ndim != 2 or boxes.shape[1] != 7 or not np.isfinite(boxes).all() or np.any(boxes[:, 3:6] <= 0):
        raise ValueError("finite native center-Z Nx7 boxes with positive dimensions required")
    return boxes


def _old_nearest_rectangles(boxes):
    boxes = _old_boxes(boxes)
    yaw = np.abs((boxes[:, 6] + np.pi / 2) % np.pi - np.pi / 2)
    extent = np.where((yaw > np.pi / 4)[:, None], boxes[:, [4, 3]], boxes[:, 3:5])
    return np.concatenate((boxes[:, :2] - extent / 2, boxes[:, :2] + extent / 2), axis=1)


def _old_enclosing_rectangles(boxes):
    boxes = _old_boxes(boxes)
    c = np.abs(np.cos(boxes[:, 6]))
    s = np.abs(np.sin(boxes[:, 6]))
    extent = np.stack((c * boxes[:, 3] + s * boxes[:, 4], s * boxes[:, 3] + c * boxes[:, 4]), axis=1)
    return np.concatenate((boxes[:, :2] - extent / 2, boxes[:, :2] + extent / 2), axis=1)


def _old_iou(first, second):
    lower = np.maximum(first[:, None, :2], second[None, :, :2])
    upper = np.minimum(first[:, None, 2:], second[None, :, 2:])
    intersection = np.maximum(upper - lower, 0).prod(axis=-1)
    area_first = (first[:, 2:] - first[:, :2]).prod(axis=-1)
    area_second = (second[:, 2:] - second[:, :2]).prod(axis=-1)
    union = area_first[:, None] + area_second[None, :] - intersection
    return np.divide(intersection, union, out=np.zeros_like(intersection), where=union > 0)


class DetectionBoxGeometryParityTests(unittest.TestCase):
    def test_box_coding_decoded_heading_wrap_matches_box_module(self):
        support.assert_heading_wrap_parity(self, _old_decoded_heading_wrap)

    def test_v3_canonical_heading_wrap_matches_box_module(self):
        support.assert_heading_wrap_parity(self, _old_v3_canonical_wrap)

    def test_sustained_groundtruth_heading_wrap_matches_box_module(self):
        support.assert_heading_wrap_parity(self, _old_sustained_groundtruth_wrap)

    def test_overfit_target_heading_wrap_matches_box_module(self):
        support.assert_heading_wrap_parity(self, _old_overfit_target_wrap)

    def test_prediction_record_point_count_matches_box_module(self):
        support.assert_point_count_parity(self, _old_prediction_record_point_count)

    def test_detector_bev_rectangles_and_iou_match_box_module(self):
        support.assert_bev_rectangle_parity(self, _old_nearest_rectangles, _old_enclosing_rectangles, _old_iou)


if __name__ == "__main__":
    unittest.main()
