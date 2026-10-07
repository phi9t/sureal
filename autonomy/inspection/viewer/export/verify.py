"""Independently verify an exported bundle against its source slice.

(a) scalar re-derivation of sampled points with plain math (no NumPy vector path);
(b) exported points inside every lidar_box versus Waymo's num_lidar_points_in_box;
(c) every manifest hash and lineage entry;
(d) informational: which frame the box `speed` field lives in.

Usage: python -m export.verify --slice DIR --context NAME --bundle DIR [--sample 20] [--frame-stride 10]
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import numpy as np

from . import constants as C
from .boxes import points_in_box
from .manifest import sha256_file
from .quantize import decode_elongation, decode_intensity, dequantize_xyz, unpack_flags
from .slice_reader import FrameCursor, SliceReceipt, array_field
from .wpc import read_wpc

LI = "[LiDARComponent]."
LP = "[LiDARPoseComponent]."


def scalar_point(ri, row, col, cal, pixel_pose, frame_pose):
    h, w = ri.shape[:2]
    r = float(ri[row, col, 0])
    vals = cal["inclination_values"]
    if vals:
        e = float(vals[h - 1 - row])
    else:
        e = cal["inclination_min"] + (h - row - 0.5) / h * (cal["inclination_max"] - cal["inclination_min"])
    ext = cal["vehicle_from_lidar"]
    a = ((w - col - 0.5) / w * 2 - 1) * math.pi - math.atan2(ext[4], ext[0])
    p = [r * math.cos(e) * math.cos(a), r * math.cos(e) * math.sin(a), r * math.sin(e)]
    v = [ext[4 * i] * p[0] + ext[4 * i + 1] * p[1] + ext[4 * i + 2] * p[2] + ext[4 * i + 3] for i in range(3)]
    if pixel_pose is not None:
        roll, pitch, yaw, tx, ty, tz = [float(x) for x in pixel_pose[row, col]]
        cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
        rx = [[1, 0, 0], [0, cr, -sr], [0, sr, cr]]
        ry = [[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]]
        rz = [[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]
        m = _mm(rz, _mm(ry, rx))
        wpt = [sum(m[i][j] * v[j] for j in range(3)) + [tx, ty, tz][i] for i in range(3)]
        fp = frame_pose
        d = [wpt[i] - fp[4 * i + 3] for i in range(3)]
        v = [sum(fp[4 * j + i] * d[j] for j in range(3)) for i in range(3)]  # R^T (p - t)
    return v


def _mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def verify(slice_dir, context, bundle, sample=20, frame_stride=10, log=print):
    bundle = Path(bundle)
    scene = json.loads((bundle / "scene.json").read_text())
    receipt = SliceReceipt(slice_dir)
    failures = []

    # (c) hashes and lineage
    listed = set(scene["files"])
    for rel, info in scene["files"].items():
        p = bundle / rel
        if not p.exists():
            failures.append("missing file " + rel)
            continue
        if p.stat().st_size != info["bytes"] or sha256_file(p) != info["sha256"]:
            failures.append("hash mismatch " + rel)
    actual = {str(p.relative_to(bundle)) for p in bundle.rglob("*") if p.is_file()} - {"scene.json"}
    for extra in sorted(actual - listed):
        failures.append("unlisted file " + extra)
    for comp, src in scene["lineage"]["sources"].items():
        if receipt.sha256(comp, context) != src["sha256"]:
            failures.append("source sha256 differs for " + comp)
    log("(c) files: %d listed, %d failures so far" % (len(listed), len(failures)))

    # Load the world origin and tracks.
    origin = np.asarray(scene["frames_declaration"]["world_origin_waymo"])
    tracks = json.loads((bundle / scene["tracks"]).read_text())
    col = {name: i for i, name in enumerate(tracks["columns"])}
    boxes_by_frame = {}
    for oid, t in tracks["tracks"].items():
        for row in t["rows"]:
            boxes_by_frame.setdefault(row[col["frame"]], []).append((oid, row))

    frames = scene["frames"]
    selected = [f for f in frames if f["index"] % frame_stride == 0]
    ts_selected = {f["timestamp_micros"] for f in selected}
    lidar_cur = FrameCursor(receipt.path("lidar", context))
    pose_cur = FrameCursor(receipt.path("lidar_pose", context))
    vp_rows = {}
    for r in _rows_for(receipt.path("vehicle_pose", context)):
        vp_rows[int(r["key.frame_timestamp_micros"])] = r["[VehiclePoseComponent].world_from_vehicle.transform"]
    rng = random.Random(1234)
    max_err = 0.0
    checks = 0
    ours_all, waymo_all, ours_top, waymo_top = [], [], [], []
    for f in frames:
        ts = f["timestamp_micros"]
        if ts not in ts_selected:
            continue
        header, sections = read_wpc(bundle / f["points"])
        if header["frame_index"] != f["index"] or header["timestamp_micros"] != ts:
            failures.append("wpc header mismatch at frame %d" % f["index"])
        frame_pose = vp_rows[ts]
        pose_rows = {int(r["key.laser_name"]): r for r in pose_cur.get(ts)}
        frame_xyz, top_xyz = [], []
        for r in lidar_cur.get(ts):
            name = int(r["key.laser_name"])
            cal = scene["lidars"][str(name)]
            pixel_pose = array_field(pose_rows[1], LP + "range_image_return1") if name == 1 else None
            for ret in (1, 2):
                ri = array_field(r, LI + "range_image_return%d" % ret)
                if ri is None:
                    continue
                key = (name, ret, C.KIND_XYZ)
                if key not in sections:
                    if (ri[..., 0] > 0).any():
                        failures.append("missing xyz section %s at frame %d" % (key, f["index"]))
                    continue
                xyz = dequantize_xyz(sections[key], header["xyz_scale"])
                valid = np.argwhere(np.isfinite(ri[..., 0]) & (ri[..., 0] > 0))
                if xyz.shape[0] != valid.shape[0]:
                    failures.append("point count mismatch %s at frame %d" % (key, f["index"]))
                    continue
                flags = unpack_flags(sections[(name, ret, C.KIND_FLAGS)])
                if not (flags["sensor"] == name).all() or not (flags["return_index"] == ret).all():
                    failures.append("flag sensor/return mismatch %s at frame %d" % (key, f["index"]))
                nlz = ri[valid[:, 0], valid[:, 1], 3] > 0
                if not np.array_equal(flags["nlz"], nlz):
                    failures.append("nlz flag mismatch %s at frame %d" % (key, f["index"]))
                inten = decode_intensity(sections[(name, ret, C.KIND_INTENSITY)], cal["intensity_cap"])
                src_i = np.clip(ri[valid[:, 0], valid[:, 1], 1], 0, cal["intensity_cap"])
                step = np.log1p(cal["intensity_cap"]) / 255.0
                if (np.abs(np.log1p(inten) - np.log1p(src_i)) > step).any():
                    failures.append("intensity decode error %s at frame %d" % (key, f["index"]))
                elong = decode_elongation(sections[(name, ret, C.KIND_ELONGATION)], C.ELONGATION_MAX)
                src_e = np.clip(ri[valid[:, 0], valid[:, 1], 2], 0, C.ELONGATION_MAX)
                if (np.abs(elong - src_e) > C.ELONGATION_MAX / 255.0).any():
                    failures.append("elongation decode error %s at frame %d" % (key, f["index"]))
                for k in rng.sample(range(valid.shape[0]), min(sample, valid.shape[0])):
                    row, c = int(valid[k, 0]), int(valid[k, 1])
                    ref = scalar_point(ri, row, c, cal, pixel_pose, frame_pose)
                    err = max(abs(ref[j] - xyz[k, j]) for j in range(3))
                    max_err = max(max_err, err)
                    checks += 1
                    if err > header["xyz_scale"] / 2 + 1e-6:
                        failures.append("scalar mismatch %.4f m %s frame %d pixel (%d,%d)" % (err, key, f["index"], row, c))
                frame_xyz.append(xyz)
                if name == 1:
                    top_xyz.append(xyz)
        if frame_xyz:
            pts = np.concatenate(frame_xyz)
            top = np.concatenate(top_xyz) if top_xyz else np.zeros((0, 3))
            for oid, row in boxes_by_frame.get(f["index"], []):
                center = row[col["cx"]:col["cz"] + 1]
                size = row[col["length"]:col["height"] + 1]
                ours_all.append(points_in_box(pts, center, size, row[col["heading"]]))
                waymo_all.append(row[col["num_points"]] or 0)
                ours_top.append(points_in_box(top, center, size, row[col["heading"]]))
                waymo_top.append(row[col["num_top_points"]] or 0)
    log("(a) scalar checks: %d samples, max error %.5f m" % (checks, max_err))
    result = {"scalar_checks": checks, "scalar_max_error_m": max_err}
    if ours_all:
        o, wv = np.asarray(ours_all, float), np.asarray(waymo_all, float)
        ot, wt = np.asarray(ours_top, float), np.asarray(waymo_top, float)
        r_all = float(np.corrcoef(o, wv)[0, 1]) if wv.std() > 0 else float("nan")
        r_top = float(np.corrcoef(ot, wt)[0, 1]) if wt.std() > 0 else float("nan")
        big = wv >= 20
        ratio = float(np.median(o[big] / wv[big])) if big.any() else float("nan")
        log("(b) boxes: %d, r(all)=%.5f r(top)=%.5f median ratio (>=20 pts)=%.3f" % (len(o), r_all, r_top, ratio))
        result.update({"boxes": len(o), "corr_all": r_all, "corr_top": r_top, "median_ratio": ratio})
        if not (r_all >= 0.999):
            failures.append("box-count correlation %.4f below 0.999" % r_all)
        if not (0.93 <= ratio <= 1.02):
            failures.append("box-count median ratio %.3f outside [0.93, 1.02]" % ratio)

    # (d) speed frame, informational
    votes = {"vehicle": 0.0, "world": 0.0, "n": 0}
    wfv = {f["index"]: np.asarray(f["world_from_vehicle"]).reshape(4, 4) for f in frames}
    for oid, t in tracks["tracks"].items():
        rows = t["rows"]
        for a, b in zip(rows[:-1], rows[1:]):
            if b[col["frame"]] != a[col["frame"]] + 1 or a[col["vx"]] is None:
                continue
            ca = wfv[a[col["frame"]]] @ np.r_[a[col["cx"]:col["cz"] + 1], 1.0]
            cb = wfv[b[col["frame"]]] @ np.r_[b[col["cx"]:col["cz"] + 1], 1.0]
            dt = (frames[b[col["frame"]]]["timestamp_micros"] - frames[a[col["frame"]]]["timestamp_micros"]) / 1e6
            vel_world = (cb[:3] - ca[:3]) / dt
            v = np.asarray(a[col["vx"]:col["vz"] + 1])
            if np.linalg.norm(v) < 1.0:
                continue
            votes["vehicle"] += np.linalg.norm(wfv[a[col["frame"]]][:3, :3] @ v - vel_world)
            votes["world"] += np.linalg.norm(v - vel_world)
            votes["n"] += 1
    if votes["n"]:
        which = "vehicle" if votes["vehicle"] < votes["world"] else "world"
        log("(d) speed frame: %s (mean residual vehicle=%.2f world=%.2f m/s over %d pairs)" % (which, votes["vehicle"] / votes["n"], votes["world"] / votes["n"], votes["n"]))
        result["speed_frame"] = which
    result["failures"] = failures
    result["passed"] = not failures
    for fail in failures[:20]:
        log("FAIL " + fail)
    log("PASS" if not failures else "FAILED (%d)" % len(failures))
    return result


def _rows_for(path):
    from .slice_reader import read_rows
    return read_rows(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slice", required=True)
    ap.add_argument("--context", required=True)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--sample", type=int, default=20)
    ap.add_argument("--frame-stride", type=int, default=10)
    ap.add_argument("--json", default=None, help="write the result JSON here")
    a = ap.parse_args(argv)
    result = verify(a.slice, a.context, a.bundle, a.sample, a.frame_stride)
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
