"""Track graph tests for incremental SfM."""

from __future__ import annotations

import unittest

from sfm.tracks import TrackGraph


class TrackGraphTest(unittest.TestCase):
    def test_same_view_conflict_is_rejected(self) -> None:
        """Catches merged tracks with two feature observations from one view."""
        graph = TrackGraph()

        track_id = graph.add_match("view-a", 0, [0.0, 0.0], "view-b", 0, [1.0, 0.0])
        conflict = graph.add_match(
            "view-a",
            1,
            [0.2, 0.0],
            "view-b",
            0,
            [1.0, 0.0],
        )

        self.assertIsNone(conflict)
        observations = graph.tracks()[graph.find(track_id)]
        self.assertEqual(
            [(observation.view_id, observation.feature_index) for observation in observations],
            [("view-a", 0), ("view-b", 0)],
        )
        self.assertEqual(graph.conflict_count, 1)


if __name__ == "__main__":
    unittest.main()
