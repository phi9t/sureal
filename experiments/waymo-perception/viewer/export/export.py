"""Export one Waymo Perception v2 context from a Waystone slice into a viewer bundle.

Usage: python -m export.export --slice SLICE_DIR --context NAME --out CACHE_DIR
       [--frames N] [--no-proj] [--force]

Output: CACHE_DIR/bundles/{slice_id}/{context}/ (written to a .partial dir, then renamed).
"""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np

from . import constants as C
from .boxes import associations, camera_boxes, group_by_frame, lidar_boxes_to_tracks, projected_boxes, synced_boxes
from .images import decode_jpeg_half, first_projection, image_size, png_mode, sample_rgb
from .keypoints import camera_keypoints, lidar_keypoints
from .manifest import dump_json, mat4, mat4_list, sha256_bytes, sha256_file
from .quantize import encode_elongation, encode_intensity, pack_flags, quantize_xyz
from .range_image import azimuths, inclinations, range_image_to_vehicle
from .slice_reader import FrameCursor, SliceReceipt, array_field, read_rows
from .wpc import Section, write_wpc

LC = "[LiDARCalibrationComponent]."
CC = "[CameraCalibrationComponent]."
CI = "[CameraImageComponent]."
LI = "[LiDARComponent]."
LP = "[LiDARPoseComponent]."
PR = "[LiDARCameraProjectionComponent]."
LS = "[LiDARSegmentationLabelComponent]."
CS = "[CameraSegmentationLabelComponent]."
ST = "[StatsComponent]."
VP = "[VehiclePoseComponent]."


def load_calibrations(receipt, context):
    cams = {}
    for r in read_rows(receipt.path("camera_calibration", context)):
        name = int(r["key.camera_name"])
        cams[name] = {
            "name": C.CAMERA_NAMES[name],
            "width": int(r[CC + "width"]),
            "height": int(r[CC + "height"]),
            "intrinsics": {k: float(r[CC + "intrinsic." + k]) for k in ("f_u", "f_v", "c_u", "c_v", "k1", "k2", "p1", "p2", "k3")},
            "vehicle_from_camera": mat4_list(mat4(r[CC + "extrinsic.transform"])),
            "rolling_shutter_direction": int(r[CC + "rolling_shutter_direction"]),
        }
    lasers = {}
    for r in read_rows(receipt.path("lidar_calibration", context)):
        name = int(r["key.laser_name"])
        vals = r[LC + "beam_inclination.values"]
        lasers[name] = {
            "name": C.LIDAR_NAMES[name],
            "vehicle_from_lidar": mat4_list(mat4(r[LC + "extrinsic.transform"])),
            "inclination_min": float(r[LC + "beam_inclination.min"]),
            "inclination_max": float(r[LC + "beam_inclination.max"]),
            "inclination_values": [float(v) for v in vals] if vals is not None and len(vals) else None,
            "intensity_cap": C.INTENSITY_CAP[name],
        }
    return cams, lasers


def recentre(m, origin):
    out = np.array(m, dtype=np.float64)
    out[:3, 3] -= origin
    return out


def export_context(slice_dir, context, out_root, frame_limit=None, with_proj=True, force=False, log=print):
    receipt = SliceReceipt(slice_dir)
    if context not in receipt.contexts:
        raise SystemExit("context not in slice: " + context)
    final = Path(out_root) / "bundles" / receipt.slice_id / context
    partial = final.with_name(final.name + ".partial")
    if final.exists():
        if not force:
            raise SystemExit("bundle exists (use --force): " + str(final))
        shutil.rmtree(final)
    if partial.exists():
        shutil.rmtree(partial)
    for sub in ("frames", "images", "panoptic"):
        (partial / sub).mkdir(parents=True)
    files = {}

    def emit(rel, data):
        p = partial / rel
        p.write_bytes(data)
        files[rel] = {"bytes": len(data), "sha256": sha256_bytes(data)}

    cams, lasers = load_calibrations(receipt, context)
    poses = read_rows(receipt.path("vehicle_pose", context))
    poses.sort(key=lambda r: r["key.frame_timestamp_micros"])
    timestamps = [int(r["key.frame_timestamp_micros"]) for r in poses]
    if len(set(timestamps)) != len(timestamps):
        raise ValueError("duplicate vehicle pose timestamps")
    if frame_limit is not None:
        timestamps = timestamps[:frame_limit]
        poses = poses[:frame_limit]
    frame_index = {ts: i for i, ts in enumerate(timestamps)}
    world_from_vehicle = {int(r["key.frame_timestamp_micros"]): mat4(r[VP + "world_from_vehicle.transform"]) for r in poses}
    origin = world_from_vehicle[timestamps[0]][:3, 3].copy()

    stats = {int(r["key.frame_timestamp_micros"]): r for r in read_rows(receipt.path("stats", context))}
    tracks = lidar_boxes_to_tracks(read_rows(receipt.path("lidar_box", context)), frame_index)
    emit("tracks.json", dump_json(tracks, partial / "tracks.json"))
    small = {}
    for comp in ("camera_box", "projected_lidar_box", "lidar_camera_synced_box", "camera_to_lidar_box_association", "camera_hkp", "lidar_hkp"):
        path = receipt.path(comp, context)
        small[comp] = group_by_frame(read_rows(path)) if path else {}

    lidar_cur = FrameCursor(receipt.path("lidar", context))
    pose_cur = FrameCursor(receipt.path("lidar_pose", context))
    proj_cur = FrameCursor(receipt.path("lidar_camera_projection", context))
    seg_cur = FrameCursor(receipt.path("lidar_segmentation", context))
    img_cur = FrameCursor(receipt.path("camera_image", context))
    cseg_cur = FrameCursor(receipt.path("camera_segmentation", context))

    tables = {}
    for name, cal in lasers.items():
        tables[name] = (np.asarray(cal["vehicle_from_lidar"]).reshape(4, 4), cal)
    frames_out = []
    intensity_max = {name: 0.0 for name in lasers}
    clipped = 0
    panoptic_modes = set()
    t_start = time.monotonic()
    for i, ts in enumerate(timestamps):
        wfv = world_from_vehicle[ts]
        img_rows = img_cur.get(ts)
        images = {}
        frame_cams = {}
        for r in sorted(img_rows, key=lambda r: r["key.camera_name"]):
            name = int(r["key.camera_name"])
            data = r[CI + "image"]
            rel = "images/%04d_%d.jpg" % (i, name)
            emit(rel, data)
            images[name] = decode_jpeg_half(data)
            w, h = images[name][1]
            if (w, h) != (cams[name]["width"], cams[name]["height"]):
                raise ValueError("image size differs from calibration for camera %d" % name)
            frame_cams[str(name)] = {
                "image": rel,
                "panoptic": None,
                "world_from_vehicle": mat4_list(recentre(mat4(r[CI + "pose.transform"]), origin)),
                "pose_timestamp": float(r[CI + "pose_timestamp"]),
                "velocity": [float(r[CI + "velocity.linear_velocity." + a]) for a in "xyz"] + [float(r[CI + "velocity.angular_velocity." + a]) for a in "xyz"],
                "shutter": {
                    "shutter": float(r[CI + "rolling_shutter_params.shutter"]),
                    "trigger_time": float(r[CI + "rolling_shutter_params.camera_trigger_time"]),
                    "readout_done_time": float(r[CI + "rolling_shutter_params.camera_readout_done_time"]),
                },
            }
        for r in cseg_cur.get(ts):
            name = int(r["key.camera_name"])
            data = r[CS + "panoptic_label"]
            rel = "panoptic/%04d_%d.png" % (i, name)
            emit(rel, data)
            panoptic_modes.add(png_mode(data))
            divisor = int(r[CS + "panoptic_label_divisor"])
            if divisor != C.PANOPTIC_LABEL_DIVISOR_EXPECTED:
                raise ValueError("unexpected panoptic divisor %d" % divisor)
            frame_cams.setdefault(str(name), {})["panoptic"] = rel
            frame_cams[str(name)]["panoptic_divisor"] = divisor
            frame_cams[str(name)]["panoptic_sequence_id"] = r[CS + "sequence_id"]

        pose_rows = {int(r["key.laser_name"]): r for r in pose_cur.get(ts)}
        proj_rows = {int(r["key.laser_name"]): r for r in proj_cur.get(ts)}
        seg_rows = {int(r["key.laser_name"]): r for r in seg_cur.get(ts)}
        sections = []
        counts = {}
        for r in lidar_cur.get(ts):
            name = int(r["key.laser_name"])
            ext, cal = tables[name]
            pixel_pose = None
            if name == 1:
                prow = pose_rows.get(1)
                if prow is None:
                    raise ValueError("TOP lidar pose missing at frame %d" % i)
                pixel_pose = array_field(prow, LP + "range_image_return1")
            for ret in (1, 2):
                ri = array_field(r, LI + "range_image_return%d" % ret)
                if ri is None:
                    continue
                incl = inclinations(ri.shape[0], cal["inclination_min"], cal["inclination_max"], cal["inclination_values"])
                azim = azimuths(ri.shape[1], ext)
                pts = range_image_to_vehicle(ri, ext, incl, azim, pixel_pose=pixel_pose, world_from_vehicle=wfv)
                n = pts["xyz"].shape[0]
                counts["%d/%d" % (name, ret)] = n
                if n == 0:
                    continue
                proj = array_field(proj_rows[name], PR + "range_image_return%d" % ret) if name in proj_rows else None
                if proj is not None:
                    cam, u, v = first_projection(proj, pts["rows"], pts["cols"])
                    rgb, has = sample_rgb(cam, u, v, images)
                else:
                    cam = np.zeros(n, dtype=np.int64)
                    u = v = np.zeros(n)
                    rgb = np.zeros((n, 3), dtype=np.uint8)
                    has = np.zeros(n, dtype=bool)
                cap = cal["intensity_cap"]
                imax = float(pts["intensity"].max())
                intensity_max[name] = max(intensity_max[name], imax)
                clipped += int((pts["intensity"] > cap).sum())
                sections += [
                    Section(name, ret, C.KIND_XYZ, quantize_xyz(pts["xyz"])),
                    Section(name, ret, C.KIND_INTENSITY, encode_intensity(pts["intensity"], cap)),
                    Section(name, ret, C.KIND_ELONGATION, encode_elongation(pts["elongation"], C.ELONGATION_MAX)),
                    Section(name, ret, C.KIND_FLAGS, pack_flags(pts["nlz"], ret, name, has)),
                    Section(name, ret, C.KIND_RGB, rgb),
                ]
                if with_proj and proj is not None:
                    sections += [
                        Section(name, ret, C.KIND_PROJ_CAM, np.clip(cam, 0, 255).astype(np.uint8)),
                        Section(name, ret, C.KIND_PROJ_U, np.clip(np.rint(u), 0, 65535).astype(np.uint16)),
                        Section(name, ret, C.KIND_PROJ_V, np.clip(np.rint(v), 0, 65535).astype(np.uint16)),
                    ]
                if name in seg_rows:
                    seg = array_field(seg_rows[name], LS + "range_image_return%d" % ret)
                    if seg is not None:
                        lab = seg[pts["rows"], pts["cols"]]
                        sections += [
                            Section(name, ret, C.KIND_SEMANTIC, np.clip(lab[:, 1], 0, 255).astype(np.uint8)),
                            Section(name, ret, C.KIND_INSTANCE, np.clip(lab[:, 0], 0, 65535).astype(np.uint16)),
                        ]
        rel = "frames/%04d.wpc" % i
        write_wpc(partial / rel, i, ts, C.XYZ_SCALE_M, sections)
        files[rel] = {"bytes": (partial / rel).stat().st_size, "sha256": sha256_file(partial / rel)}

        ann = {
            "camera_boxes": camera_boxes(small["camera_box"].get(ts, [])),
            "projected_boxes": projected_boxes(small["projected_lidar_box"].get(ts, [])),
            "synced_boxes": synced_boxes(small["lidar_camera_synced_box"].get(ts, [])),
            "associations": associations(small["camera_to_lidar_box_association"].get(ts, [])),
            "camera_keypoints": camera_keypoints(small["camera_hkp"].get(ts, [])),
            "lidar_keypoints": lidar_keypoints(small["lidar_hkp"].get(ts, [])),
        }
        rel_ann = "frames/%04d.json" % i
        emit(rel_ann, dump_json(ann, partial / rel_ann))
        st = stats.get(ts)
        frames_out.append({
            "index": i,
            "timestamp_micros": ts,
            "world_from_vehicle": mat4_list(recentre(wfv, origin)),
            "points": rel,
            "annotations": rel_ann,
            "point_counts": counts,
            "has_lidar_segmentation": 1 in seg_rows,
            "cameras": dict(sorted(frame_cams.items())),
            "stats": None if st is None else {
                "time_of_day": st[ST + "time_of_day"],
                "location": st[ST + "location"],
                "weather": st[ST + "weather"],
                "lidar_object_counts": _counts(st[ST + "lidar_object_counts.types"], st[ST + "lidar_object_counts.counts"]),
                "camera_object_counts": _counts(st[ST + "camera_object_counts.types"], st[ST + "camera_object_counts.counts"]),
            },
        })
        if i % 10 == 0 or i == len(timestamps) - 1:
            log("frame %d/%d  %.1fs" % (i + 1, len(timestamps), time.monotonic() - t_start))

    scene = {
        "bundle_format": C.BUNDLE_FORMAT,
        "exporter": {"name": C.EXPORTER_NAME, "version": C.EXPORTER_VERSION},
        "lineage": {
            "slice_id": receipt.slice_id, "release": receipt.release, "split": receipt.split, "context": context,
            "sources": {comp: {"path": receipt.objects[(comp, context)]["relative_path"], "sha256": receipt.sha256(comp, context)} for comp in receipt.components(context)},
        },
        "frames_declaration": {
            "vehicle": "Waymo vehicle frame: +x forward, +y left, +z up, right-handed, metres",
            "world": "Waymo world frame translated so the frame-0 vehicle origin is (0,0,0); rotation unchanged",
            "world_origin_waymo": [float(v) for v in origin],
            "points_frame": "vehicle frame of each frame; TOP LiDAR motion-compensated to the frame pose",
            "camera": "Waymo camera frame: +x out of the lens, +y left, +z up",
            "three_from_waymo": [[0, -1, 0], [0, 0, 1], [-1, 0, 0]],
        },
        "quantization": {
            "xyz": {"dtype": "int16", "scale_m": C.XYZ_SCALE_M},
            "intensity": {"encoding": "u8 = round(255*log1p(min(I,cap))/log1p(cap))", "cap_by_sensor": {str(k): v for k, v in C.INTENSITY_CAP.items()}, "observed_max_by_sensor": {str(k): v for k, v in intensity_max.items()}, "clipped_points": clipped},
            "elongation": {"encoding": "u8 = round(255*clamp(e/max,0,1))", "max": C.ELONGATION_MAX},
            "flags": {"bit0": "in_no_label_zone", "bit1": "return2", "bits2-4": "sensor id", "bit5": "has_projection"},
            "rgb": "baked from the frame's JPEG at the point's first lidar_camera_projection, half-resolution nearest",
            "point_order": "row-major over valid range pixels (range > 0), per sensor and return",
        },
        "cameras": {str(k): v for k, v in sorted(cams.items())},
        "lidars": {str(k): v for k, v in sorted(lasers.items())},
        "frames": frames_out,
        "tracks": "tracks.json",
        "palettes": {
            "box_types": C.BOX_TYPES, "box_colors": C.BOX_COLORS,
            "lidar_semantic_classes": C.LIDAR_SEMANTIC_CLASSES, "lidar_semantic_colors": C.LIDAR_SEMANTIC_COLORS,
            "camera_semantic_classes": C.CAMERA_SEMANTIC_CLASSES, "camera_semantic_colors": C.CAMERA_SEMANTIC_COLORS,
            "keypoint_types": {str(k): v for k, v in C.KEYPOINT_TYPES.items()}, "keypoint_edges": C.KEYPOINT_EDGES,
        },
        "panoptic_png_modes": sorted(panoptic_modes),
        "frame_limit": frame_limit,
        "files": dict(sorted(files.items())),
    }
    dump_json(scene, partial / "scene.json")
    os.replace(partial, final)
    log("bundle written: %s (%d files, %.1f MB)" % (final, len(files) + 1, sum(f["bytes"] for f in files.values()) / 1e6))
    return final


def _counts(types, counts):
    if types is None or counts is None:
        return {}
    return {C.BOX_TYPES.get(int(t), str(t)): int(c) for t, c in zip(types, counts)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slice", required=True)
    ap.add_argument("--context", required=True)
    ap.add_argument("--out", required=True, help="viewer cache root; bundle goes under bundles/{slice_id}/{context}")
    ap.add_argument("--frames", type=int, default=None)
    ap.add_argument("--no-proj", action="store_true", help="omit proj_cam/proj_u/proj_v sections")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    export_context(a.slice, a.context, a.out, frame_limit=a.frames, with_proj=not a.no_proj, force=a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
