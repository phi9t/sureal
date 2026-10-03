"""Human keypoint list columns -> JSON rows."""
from collections import defaultdict

CAM = "[CameraHumanKeypointsComponent].camera_keypoints[*]."
LID = "[LiDARHumanKeypointsComponent].lidar_keypoints[*]."


def _lists(row, prefix, names):
    cols = [row.get(prefix + n) for n in names]
    if any(c is None for c in cols):
        return []
    n = len(cols[0])
    if any(len(c) != n for c in cols):
        raise ValueError("ragged keypoint lists")
    return list(zip(*cols))


def camera_keypoints(rows):
    out = defaultdict(dict)
    for r in rows:
        pts = _lists(r, CAM, ["type", "keypoint_2d.location_px.x", "keypoint_2d.location_px.y", "keypoint_2d.visibility.is_occluded"])
        out[str(r["key.camera_name"])][r["key.camera_object_id"]] = [
            [int(t), float(x), float(y), int(bool(o))] for t, x, y, o in pts
        ]
    return {k: dict(sorted(v.items())) for k, v in sorted(out.items())}


def lidar_keypoints(rows):
    out = {}
    for r in rows:
        pts = _lists(r, LID, ["type", "keypoint_3d.location_m.x", "keypoint_3d.location_m.y", "keypoint_3d.location_m.z", "keypoint_3d.visibility.is_occluded"])
        out[r["key.laser_object_id"]] = [[int(t), float(x), float(y), float(z), int(bool(o))] for t, x, y, z, o in pts]
    return dict(sorted(out.items()))
