"""3D and 2D label tables -> compact JSON structures."""
from collections import defaultdict

import numpy as np

from geometry.oriented_box import count_points_in_box

TRACK_COLUMNS = [
    "frame", "cx", "cy", "cz", "length", "width", "height", "heading",
    "vx", "vy", "vz", "ax", "ay", "az", "num_points", "num_top_points",
    "difficulty_detection", "difficulty_tracking",
]
P = "[LiDARBoxComponent]."


def lidar_boxes_to_tracks(rows, frame_index):
    """rows: lidar_box rows; frame_index: timestamp -> frame index. Returns tracks dict."""
    tracks = {}
    for r in rows:
        ts = r["key.frame_timestamp_micros"]
        if ts not in frame_index:
            continue
        oid = r["key.laser_object_id"]
        t = tracks.setdefault(oid, {"type": int(r[P + "type"]), "rows": []})
        if t["type"] != int(r[P + "type"]):
            raise ValueError("track type changes within a scene: " + oid)
        t["rows"].append([
            frame_index[ts],
            float(r[P + "box.center.x"]), float(r[P + "box.center.y"]), float(r[P + "box.center.z"]),
            float(r[P + "box.size.x"]), float(r[P + "box.size.y"]), float(r[P + "box.size.z"]),
            float(r[P + "box.heading"]),
            _f(r[P + "speed.x"]), _f(r[P + "speed.y"]), _f(r[P + "speed.z"]),
            _f(r[P + "acceleration.x"]), _f(r[P + "acceleration.y"]), _f(r[P + "acceleration.z"]),
            _i(r[P + "num_lidar_points_in_box"]), _i(r[P + "num_top_lidar_points_in_box"]),
            _i(r[P + "difficulty_level.detection"]), _i(r[P + "difficulty_level.tracking"]),
        ])
    for t in tracks.values():
        t["rows"].sort(key=lambda row: row[0])
        frames = [row[0] for row in t["rows"]]
        if len(set(frames)) != len(frames):
            raise ValueError("duplicate box for one track in one frame")
    return {"columns": TRACK_COLUMNS, "tracks": dict(sorted(tracks.items()))}


def _f(v):
    return None if v is None else float(v)


def _i(v):
    return None if v is None else int(v)


def group_by_frame(rows):
    out = defaultdict(list)
    for r in rows:
        out[r["key.frame_timestamp_micros"]].append(r)
    return out


def camera_boxes(rows):
    pre = "[CameraBoxComponent]."
    out = defaultdict(list)
    for r in rows:
        out[str(r["key.camera_name"])].append([
            r["key.camera_object_id"], float(r[pre + "box.center.x"]), float(r[pre + "box.center.y"]),
            float(r[pre + "box.size.x"]), float(r[pre + "box.size.y"]), int(r[pre + "type"]),
        ])
    return {k: sorted(v) for k, v in out.items()}


def projected_boxes(rows):
    pre = "[ProjectedLiDARBoxComponent]."
    out = defaultdict(list)
    for r in rows:
        out[str(r["key.camera_name"])].append([
            r["key.laser_object_id"], float(r[pre + "box.center.x"]), float(r[pre + "box.center.y"]),
            float(r[pre + "box.size.x"]), float(r[pre + "box.size.y"]), int(r[pre + "type"]),
        ])
    return {k: sorted(v) for k, v in out.items()}


def synced_boxes(rows):
    pre = "[LiDARCameraSyncedBoxComponent]."
    return sorted([
        r["key.laser_object_id"], int(r[pre + "most_visible_camera_name"]),
        float(r[pre + "camera_synced_box.center.x"]), float(r[pre + "camera_synced_box.center.y"]),
        float(r[pre + "camera_synced_box.center.z"]), float(r[pre + "camera_synced_box.size.x"]),
        float(r[pre + "camera_synced_box.size.y"]), float(r[pre + "camera_synced_box.size.z"]),
        float(r[pre + "camera_synced_box.heading"]),
    ] for r in rows)


def associations(rows):
    return sorted([r["key.camera_object_id"], r["key.laser_object_id"], int(r["key.camera_name"])] for r in rows)


def points_in_box(xyz, center, size, heading):
    """Count points inside an axis-aligned-in-box-frame box (length x, width y, height z)."""
    box = np.concatenate((np.asarray(center, dtype=np.float64), np.asarray(size, dtype=np.float64), [heading]))
    return count_points_in_box(xyz, box)
