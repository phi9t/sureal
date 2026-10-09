"""Test-only parity harnesses for migrating old oriented-box copies."""

import math
import itertools

import numpy as np

from geometry.oriented_box import (
    axis_aligned_bev_iou,
    count_points_in_box,
    enclosing_bev_rectangles,
    nearest_bev_rectangles,
    point_membership,
    wrap_heading,
)


_BOUNDARY_HEADINGS = (
    -math.pi,
    math.pi,
    -math.pi / 2,
    math.pi / 2,
    4096.0 * 2.0 * math.pi,
    -4096.0 * 2.0 * math.pi,
)


def assert_point_count_parity(testcase, old_count, *, seed=20261008):
    for points, box in _parity_cases(seed):
        testcase.assertEqual(old_count(points, box), count_points_in_box(points, box))

    for points, box in _invalid_cases():
        testcase.assertTrue(_rejects(old_count, points, box))
        testcase.assertTrue(_rejects(count_points_in_box, points, box))


def assert_membership_parity(testcase, old_mask, *, seed=20261008):
    for points, box in _parity_cases(seed):
        observed = np.asarray(old_mask(points, box))
        expected = point_membership(points, box)
        testcase.assertEqual(observed.shape, expected.shape)
        testcase.assertEqual(observed.dtype, np.bool_)
        np.testing.assert_array_equal(observed, expected)

    for points, box in _invalid_cases():
        testcase.assertTrue(_rejects(old_mask, points, box))
        testcase.assertTrue(_rejects(point_membership, points, box))


def assert_heading_wrap_parity(testcase, old_wrap, *, seed=20261008):
    """Assert an old heading-wrap copy matches geometry exactly on edge cases."""
    for angles in _heading_cases(seed):
        np.testing.assert_array_equal(old_wrap(angles), wrap_heading(angles))


def assert_bev_rectangle_parity(testcase, old_nearest, old_enclosing, old_iou, *, seed=20261008):
    """Assert old nearest/enclosing BEV rectangle and IoU copies match geometry."""
    for first, second in _box_set_cases(seed):
        old_nearest_first = old_nearest(first)
        old_nearest_second = old_nearest(second)
        new_nearest_first = nearest_bev_rectangles(first)
        new_nearest_second = nearest_bev_rectangles(second)
        np.testing.assert_array_equal(old_nearest_first, new_nearest_first)
        np.testing.assert_array_equal(old_nearest_second, new_nearest_second)
        np.testing.assert_array_equal(old_iou(old_nearest_first, old_nearest_second), axis_aligned_bev_iou(new_nearest_first, new_nearest_second))

        old_enclosing_first = old_enclosing(first)
        old_enclosing_second = old_enclosing(second)
        new_enclosing_first = enclosing_bev_rectangles(first)
        new_enclosing_second = enclosing_bev_rectangles(second)
        np.testing.assert_array_equal(old_enclosing_first, new_enclosing_first)
        np.testing.assert_array_equal(old_enclosing_second, new_enclosing_second)
        np.testing.assert_array_equal(old_iou(old_enclosing_first, old_enclosing_second), axis_aligned_bev_iou(new_enclosing_first, new_enclosing_second))

    for boxes in _invalid_box_sets():
        testcase.assertTrue(_rejects_unary(old_nearest, boxes))
        testcase.assertTrue(_rejects_unary(nearest_bev_rectangles, boxes))
        testcase.assertTrue(_rejects_unary(old_enclosing, boxes))
        testcase.assertTrue(_rejects_unary(enclosing_bev_rectangles, boxes))


def _parity_cases(seed):
    rng = np.random.default_rng(seed)
    cases = []
    edge_box = np.array([1.0, -2.0, 0.5, 4.0, 2.0, 3.0, math.pi / 2])
    cases.append((
        np.array(
            [
                [1.0, -2.0, 0.5],
                [1.0, 0.0, 0.5],
                [2.0, 0.0, 0.5],
                [2.0, 0.0, 2.0],
                [np.nextafter(2.0, np.inf), 0.0, 2.0],
            ],
            dtype=np.float64,
        ),
        edge_box,
    ))
    cases.append((np.empty((0, 3), dtype=np.float64), np.array([0.0, 0.0, 0.0, 1e-6, 1e6, 2.0, -math.pi])))

    for index in range(16):
        center = rng.uniform([-20.0, -20.0, -2.0], [20.0, 20.0, 4.0])
        size = rng.uniform([0.2, 0.2, 0.2], [12.0, 6.0, 4.0])
        heading = _BOUNDARY_HEADINGS[index] if index < len(_BOUNDARY_HEADINGS) else rng.uniform(-8.0 * math.pi, 8.0 * math.pi)
        box = np.concatenate((center, size, [heading])).astype(np.float64)
        uniform = rng.uniform([-25.0, -25.0, -5.0], [25.0, 25.0, 8.0], size=(128, 3))
        points = np.vstack((uniform, _surface_points(box)))
        cases.append((points, box))
    return cases


def _heading_cases(seed):
    rng = np.random.default_rng(seed)
    return [
        np.array([], dtype=np.float64),
        np.array(
            [
                -math.pi,
                math.pi,
                0.0,
                np.nextafter(-math.pi, -math.inf),
                np.nextafter(-math.pi, math.inf),
                np.nextafter(math.pi, -math.inf),
                np.nextafter(math.pi, math.inf),
                -3.0 * math.pi,
                3.0 * math.pi,
                4096.0 * 2.0 * math.pi,
                -4096.0 * 2.0 * math.pi,
            ],
            dtype=np.float64,
        ),
        rng.uniform(-64.0 * math.pi, 64.0 * math.pi, size=64).astype(np.float64),
    ]


def _box_set_cases(seed):
    rng = np.random.default_rng(seed)
    first = np.array(
        [
            [0.0, 0.0, 0.0, 4.0, 2.0, 2.0, 0.0],
            [0.0, 0.0, 0.0, 4.0, 2.0, 2.0, math.pi / 4],
            [0.0, 0.0, 0.0, 4.0, 2.0, 2.0, math.pi / 2],
            [5.0, 0.0, 0.0, 4.0, 2.0, 2.0, math.pi],
            [8.0, -3.0, 0.0, 1e-6, 1e6, 2.0, -math.pi],
        ],
        dtype=np.float64,
    )
    second = np.array(
        [
            [0.0, 0.0, 0.0, 4.0, 2.0, 2.0, 0.0],
            [2.0, 0.0, 0.0, 4.0, 2.0, 2.0, -math.pi / 4],
            [20.0, 0.0, 0.0, 4.0, 2.0, 2.0, math.pi / 2],
        ],
        dtype=np.float64,
    )
    cases = [(first, second), (first, np.empty((0, 7), dtype=np.float64))]
    for _ in range(8):
        a = _random_boxes(rng, 9)
        b = _random_boxes(rng, 7)
        cases.append((a, b))
    return cases


def _random_boxes(rng, count):
    centers = rng.uniform([-20.0, -20.0, -2.0], [20.0, 20.0, 4.0], size=(count, 3))
    sizes = rng.uniform([0.2, 0.2, 0.2], [12.0, 6.0, 4.0], size=(count, 3))
    headings = rng.uniform(-8.0 * math.pi, 8.0 * math.pi, size=(count, 1))
    return np.concatenate((centers, sizes, headings), axis=1).astype(np.float64)


def _surface_points(box):
    local = []
    half = box[3:6] / 2
    for rank in (1, 2, 3):
        for axes in itertools.combinations(range(3), rank):
            for signs in itertools.product((-1.0, 1.0), repeat=rank):
                point = np.zeros(3, dtype=np.float64)
                for axis, sign in zip(axes, signs):
                    point[axis] = sign * half[axis]
                local.append(point)
                local.append(_nudged(point, axes, inside=True))
                local.append(_nudged(point, axes, inside=False))
    return _local_to_vehicle(np.asarray(local, dtype=np.float64), box)


def _nudged(point, axes, *, inside):
    nudged = point.copy()
    for axis in axes:
        target = 0.0 if inside else math.copysign(math.inf, point[axis])
        nudged[axis] = np.nextafter(point[axis], target)
    return nudged


def _local_to_vehicle(local, box):
    c, s = math.cos(box[6]), math.sin(box[6])
    vehicle = np.empty_like(local)
    vehicle[:, 0] = box[0] + local[:, 0] * c - local[:, 1] * s
    vehicle[:, 1] = box[1] + local[:, 0] * s + local[:, 1] * c
    vehicle[:, 2] = box[2] + local[:, 2]
    return vehicle


def _invalid_cases():
    return [
        (np.array([[math.nan, 0.0, 0.0]], dtype=np.float64), np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0])),
        (np.zeros((1, 3), dtype=np.float64), np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0])),
        (np.zeros((1, 3), dtype=np.float64), np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, math.inf])),
    ]


def _invalid_box_sets():
    return [
        np.array([[math.nan, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0]], dtype=np.float64),
        np.array([[0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0]], dtype=np.float64),
        np.zeros((1, 6), dtype=np.float64),
    ]


def _rejects(fn, points, box):
    try:
        fn(points, box)
    except Exception:
        return True
    return False


def _rejects_unary(fn, value):
    try:
        fn(value)
    except Exception:
        return True
    return False
