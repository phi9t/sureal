"""Test-only parity harnesses for migrating old oriented-box copies."""

import math
import itertools

import numpy as np

from geometry.oriented_box import count_points_in_box, point_membership


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


def _rejects(fn, points, box):
    try:
        fn(points, box)
    except Exception:
        return True
    return False
