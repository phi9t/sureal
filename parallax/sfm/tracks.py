"""Feature-track graph for incremental SfM."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]
FeatureKey = tuple[str, int]


@dataclass(frozen=True)
class TrackObservation:
    view_id: str
    feature_index: int
    pixel: FloatArray


class TrackGraph:
    """Union-find graph over per-view feature observations."""

    def __init__(self) -> None:
        self._parent: dict[int, int] = {}
        self._rank: dict[int, int] = {}
        self._features: dict[FeatureKey, int] = {}
        self._observations: dict[int, dict[FeatureKey, TrackObservation]] = {}
        self._next_track_id = 0
        self._conflict_count = 0

    @property
    def conflict_count(self) -> int:
        return self._conflict_count

    def add_feature(
        self,
        view_id: str,
        feature_index: int,
        pixel: ArrayLike,
    ) -> int:
        key = (str(view_id), int(feature_index))
        existing = self._features.get(key)
        if existing is not None:
            return self.find(existing)
        track_id = self._next_track_id
        self._next_track_id += 1
        self._parent[track_id] = track_id
        self._rank[track_id] = 0
        self._features[key] = track_id
        self._observations[track_id] = {
            key: TrackObservation(
                key[0],
                key[1],
                np.asarray(pixel, dtype=np.float64).reshape(2),
            )
        }
        return track_id

    def find(self, track_id: int) -> int:
        parent = self._parent[int(track_id)]
        if parent != track_id:
            parent = self.find(parent)
            self._parent[int(track_id)] = parent
        return parent

    def feature_track(self, view_id: str, feature_index: int) -> int | None:
        track_id = self._features.get((str(view_id), int(feature_index)))
        return None if track_id is None else self.find(track_id)

    def union(self, left: int, right: int) -> int:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return root_left
        left_views = {
            observation.view_id
            for observation in self._observations[root_left].values()
        }
        right_views = {
            observation.view_id
            for observation in self._observations[root_right].values()
        }
        if left_views & right_views:
            self._conflict_count += 1
            return root_left
        if self._rank[root_left] < self._rank[root_right]:
            root_left, root_right = root_right, root_left
        self._parent[root_right] = root_left
        self._observations[root_left].update(self._observations.pop(root_right))
        if self._rank[root_left] == self._rank[root_right]:
            self._rank[root_left] += 1
        return root_left

    def add_match(
        self,
        view1: str,
        feature1: int,
        pixel1: ArrayLike,
        view2: str,
        feature2: int,
        pixel2: ArrayLike,
    ) -> int | None:
        left = self.add_feature(view1, feature1, pixel1)
        right = self.add_feature(view2, feature2, pixel2)
        if self.find(left) != self.find(right):
            left_views = {
                observation.view_id
                for observation in self._observations[self.find(left)].values()
            }
            right_views = {
                observation.view_id
                for observation in self._observations[self.find(right)].values()
            }
            if left_views & right_views:
                self._conflict_count += 1
                return None
        return self.union(left, right)

    def canonicalize_points(
        self,
        points: dict[int, FloatArray],
    ) -> dict[int, FloatArray]:
        """Move point records onto canonical track IDs after unions."""
        buckets: dict[int, list[FloatArray]] = {}
        for track_id, point in points.items():
            buckets.setdefault(self.find(track_id), []).append(
                np.asarray(point, dtype=np.float64).reshape(3)
            )
        return {
            track_id: np.mean(np.vstack(values), axis=0)
            for track_id, values in buckets.items()
        }

    def tracks(self) -> dict[int, list[TrackObservation]]:
        """Return canonical tracks with two or more distinct views."""
        result: dict[int, list[TrackObservation]] = {}
        for track_id in list(self._observations):
            root = self.find(track_id)
            if root != track_id:
                continue
            observations = list(self._observations[root].values())
            if len({observation.view_id for observation in observations}) >= 2:
                result[root] = sorted(
                    observations,
                    key=lambda observation: (observation.view_id, observation.feature_index),
                )
        return result
