"""Pinned enums, palettes and encoding constants for the viewer bundle.

Enum values come from the upstream Waymo Open Dataset protos at commit
99a4cb3ff07e2fe06c2ce73da001f850f628e45a (dataset.proto, label.proto,
segmentation.proto, camera_segmentation.proto, keypoint.proto).
"""

EXPORTER_NAME = "waymo-viewer-export"
EXPORTER_VERSION = "1.0.0"
BUNDLE_FORMAT = "waymo-viewer-bundle/1"

CAMERA_NAMES = {1: "FRONT", 2: "FRONT_LEFT", 3: "FRONT_RIGHT", 4: "SIDE_LEFT", 5: "SIDE_RIGHT"}
LIDAR_NAMES = {1: "TOP", 2: "FRONT", 3: "SIDE_LEFT", 4: "SIDE_RIGHT", 5: "REAR"}
BOX_TYPES = {0: "UNKNOWN", 1: "VEHICLE", 2: "PEDESTRIAN", 3: "SIGN", 4: "CYCLIST"}
BOX_COLORS = {0: "#90A4AE", 1: "#4FC3F7", 2: "#FFB74D", 3: "#81C784", 4: "#BA68C8"}

LIDAR_SEMANTIC_CLASSES = [
    "UNDEFINED", "CAR", "TRUCK", "BUS", "OTHER_VEHICLE", "MOTORCYCLIST", "BICYCLIST",
    "PEDESTRIAN", "SIGN", "TRAFFIC_LIGHT", "POLE", "CONSTRUCTION_CONE", "BICYCLE",
    "MOTORCYCLE", "BUILDING", "VEGETATION", "TREE_TRUNK", "CURB", "ROAD", "LANE_MARKER",
    "OTHER_GROUND", "WALKABLE", "SIDEWALK",
]
LIDAR_SEMANTIC_COLORS = [
    "#3A3F4B", "#4FC3F7", "#29B6F6", "#0288D1", "#4DD0E1", "#EF5350", "#EC407A",
    "#FFB74D", "#81C784", "#FFEE58", "#B0BEC5", "#FF7043", "#AB47BC",
    "#7E57C2", "#8D6E63", "#66BB6A", "#A1887F", "#CFD8DC", "#546E7A", "#FFF176",
    "#78909C", "#90A4AE", "#B39DDB",
]
CAMERA_SEMANTIC_CLASSES = [
    "UNDEFINED", "EGO_VEHICLE", "CAR", "TRUCK", "BUS", "OTHER_LARGE_VEHICLE", "BICYCLE",
    "MOTORCYCLE", "TRAILER", "PEDESTRIAN", "CYCLIST", "MOTORCYCLIST", "BIRD", "GROUND_ANIMAL",
    "CONSTRUCTION_CONE_POLE", "POLE", "PEDESTRIAN_OBJECT", "SIGN", "TRAFFIC_LIGHT", "BUILDING",
    "ROAD", "LANE_MARKER", "ROAD_MARKER", "SIDEWALK", "VEGETATION", "SKY", "GROUND", "DYNAMIC",
    "STATIC",
]
CAMERA_SEMANTIC_COLORS = [
    "#000000", "#263238", "#4FC3F7", "#0288D1", "#29B6F6", "#4DD0E1", "#AB47BC",
    "#7E57C2", "#5C6BC0", "#FFB74D", "#BA68C8", "#EF5350", "#FFF59D", "#D4E157",
    "#FF7043", "#B0BEC5", "#FFCC80", "#81C784", "#FFEE58", "#8D6E63",
    "#546E7A", "#FFF176", "#FFE082", "#B39DDB", "#66BB6A", "#1A237E", "#78909C", "#EC407A",
    "#90A4AE",
]
PANOPTIC_LABEL_DIVISOR_EXPECTED = 1000

KEYPOINT_TYPES = {
    1: "NOSE", 5: "LEFT_SHOULDER", 6: "LEFT_ELBOW", 7: "LEFT_WRIST", 8: "LEFT_HIP",
    9: "LEFT_KNEE", 10: "LEFT_ANKLE", 13: "RIGHT_SHOULDER", 14: "RIGHT_ELBOW",
    15: "RIGHT_WRIST", 16: "RIGHT_HIP", 17: "RIGHT_KNEE", 18: "RIGHT_ANKLE",
    19: "FOREHEAD", 20: "HEAD_CENTER",
}
KEYPOINT_EDGES = [
    (1, 20), (19, 20), (5, 13), (5, 6), (6, 7), (13, 14), (14, 15), (5, 8), (13, 16),
    (8, 16), (8, 9), (9, 10), (16, 17), (17, 18),
]

# Point encoding.
XYZ_SCALE_M = 0.005
INTENSITY_CAP = {1: 32768.0, 2: 16.0, 3: 16.0, 4: 16.0, 5: 16.0}
ELONGATION_MAX = 2.0
FLAG_NLZ = 1
FLAG_RETURN2 = 2
FLAG_SENSOR_SHIFT = 2  # bits 2-4
FLAG_HAS_PROJ = 32

# .wpc section kinds and dtypes.
KIND_XYZ, KIND_INTENSITY, KIND_ELONGATION, KIND_FLAGS, KIND_RGB = 1, 2, 3, 4, 5
KIND_PROJ_CAM, KIND_PROJ_U, KIND_PROJ_V, KIND_SEMANTIC, KIND_INSTANCE = 6, 7, 8, 9, 10
KIND_PIXEL_ROW, KIND_PIXEL_COL = 11, 12
KIND_NAMES = {
    KIND_XYZ: "xyz", KIND_INTENSITY: "intensity", KIND_ELONGATION: "elongation",
    KIND_FLAGS: "flags", KIND_RGB: "rgb", KIND_PROJ_CAM: "proj_cam", KIND_PROJ_U: "proj_u",
    KIND_PROJ_V: "proj_v", KIND_SEMANTIC: "semantic", KIND_INSTANCE: "instance",
    KIND_PIXEL_ROW: "pixel_row", KIND_PIXEL_COL: "pixel_col",
}
DTYPE_U8, DTYPE_I16, DTYPE_U16, DTYPE_I32, DTYPE_F32 = 1, 2, 3, 4, 5

COMPONENTS = [
    "camera_box", "camera_calibration", "camera_hkp", "camera_image", "camera_segmentation",
    "camera_to_lidar_box_association", "lidar", "lidar_box", "lidar_calibration",
    "lidar_camera_projection", "lidar_camera_synced_box", "lidar_hkp", "lidar_pose",
    "lidar_segmentation", "projected_lidar_box", "stats", "vehicle_pose",
]
