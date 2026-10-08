"""Test-only parity harnesses for migrating old oriented-box copies."""

import math

import numpy as np

from geometry.oriented_box import count_points_in_box


def assert_point_count_parity(testcase, old_count, *, seed=20261008):
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

    for _ in range(16):
        center = rng.uniform([-20.0, -20.0, -2.0], [20.0, 20.0, 4.0])
        size = rng.uniform([0.2, 0.2, 0.2], [12.0, 6.0, 4.0])
        heading = rng.uniform(-8.0 * math.pi, 8.0 * math.pi)
        box = np.concatenate((center, size, [heading])).astype(np.float64)
        points = rng.uniform([-25.0, -25.0, -5.0], [25.0, 25.0, 8.0], size=(128, 3))
        cases.append((points, box))

    for points, box in cases:
        testcase.assertEqual(old_count(points, box), count_points_in_box(points, box))

    invalid_cases = [
        (np.array([[math.nan, 0.0, 0.0]], dtype=np.float64), np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0])),
        (np.zeros((1, 3), dtype=np.float64), np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0])),
        (np.zeros((1, 3), dtype=np.float64), np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, math.inf])),
    ]
    for points, box in invalid_cases:
        testcase.assertTrue(_rejects(old_count, points, box))
        testcase.assertTrue(_rejects(count_points_in_box, points, box))


def _rejects(fn, points, box):
    try:
        fn(points, box)
    except Exception:
        return True
    return False
