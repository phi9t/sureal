"""Pinned native key grains and geometry/payload checks without SDK imports."""
import hashlib
import json

import numpy as np
from evidence.source_snapshot import file_sha256 as sha256_file


FRAME = ("key.segment_context_name", "key.frame_timestamp_micros")
CAMERA = FRAME + ("key.camera_name",)
LASER = FRAME + ("key.laser_name",)
CAMERA_OBJECT = CAMERA + ("key.camera_object_id",)
LASER_OBJECT = FRAME + ("key.laser_object_id",)
KEYS = {
    "camera_box": CAMERA_OBJECT, "camera_hkp": CAMERA_OBJECT,
    "camera_calibration": (FRAME[0], "key.camera_name"),
    "camera_image": CAMERA, "camera_segmentation": CAMERA,
    "camera_to_lidar_box_association": CAMERA_OBJECT + ("key.laser_object_id",),
    "lidar": LASER, "lidar_box": LASER_OBJECT,
    "lidar_calibration": (FRAME[0], "key.laser_name"),
    "lidar_camera_projection": LASER, "lidar_camera_synced_box": LASER_OBJECT,
    "lidar_hkp": LASER_OBJECT, "lidar_pose": LASER, "lidar_segmentation": LASER,
    "projected_lidar_box": CAMERA + ("key.laser_object_id",),
    "stats": FRAME, "vehicle_pose": FRAME,
}


def native_keys(component):
    if component not in KEYS:
        raise ValueError(f"unsupported component: {component}")
    return KEYS[component]


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def validate_transform(values):
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.size != 16 or not np.isfinite(matrix).all():
        raise ValueError("nonfinite or wrong-size transform")
    matrix = matrix.reshape(4, 4)
    rotation = matrix[:3, :3]
    error = float(np.max(abs(rotation.T @ rotation - np.eye(3))))
    if (error > 1e-6 or abs(np.linalg.det(rotation) - 1) > 1e-6
            or not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-6, rtol=0)):
        raise ValueError("nonrigid transform")
    return error


def summarize_array(component, values, shape):
    channels = {"lidar": 4, "lidar_pose": 6,
                "lidar_camera_projection": 6, "lidar_segmentation": 2}[component]
    if (len(shape) != 3 or any(not isinstance(v, int) or v <= 0 for v in shape)
            or shape[-1] != channels):
        raise ValueError(f"invalid {component} array shape: {shape}")
    values = np.asarray(values)
    if values.size != int(np.prod(shape)) or not np.isfinite(values).all():
        raise ValueError(f"invalid {component} array length or nonfinite values")
    image = values.reshape(shape)
    result = {"state": "present", "shape": shape, "finite_values": int(values.size)}
    if component == "lidar":
        ranges = image[:, :, 0]
        valid = ranges > 0
        result.update(valid_positive_ranges=int(valid.sum()),
                      range_min_m=float(ranges[valid].min()) if valid.any() else None,
                      range_max_m=float(ranges[valid].max()) if valid.any() else None)
        codes, counts = np.unique(image[:, :, 3][valid], return_counts=True)
        result["valid_nlz_counts"] = {str(int(k)): int(v) for k, v in zip(codes, counts)}
        result["unknown_nlz_codes"] = [int(k) for k in codes if k not in (-1, 1)]
    elif component == "lidar_segmentation":
        codes, counts = np.unique(image[:, :, 1], return_counts=True)
        result["semantic_counts"] = {str(int(k)): int(v) for k, v in zip(codes, counts)}
        result["instance_count"] = int(len(np.unique(image[:, :, 0])))
    elif component == "lidar_camera_projection":
        camera_ids = image[:, :, [0, 3]]
        if not np.isin(camera_ids, range(6)).all():
            raise ValueError("unknown camera projection sensor enum")
        result["projected_cells"] = int(np.any(camera_ids > 0, axis=2).sum())
    return result
