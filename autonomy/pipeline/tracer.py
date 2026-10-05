"""Real-data tracer: inspect all available native components and validate lineage.

No training, point conversion, image export, or SDK execution. Payload summaries
cover every row; raw data stays in the verified local/HDFS acquisition slice.
"""
import argparse
from collections import defaultdict
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import resource
import shutil
import tempfile
import time

import numpy as np
from PIL import Image
import pyarrow as pa
import pyarrow.parquet as pq
from jsonschema import Draft202012Validator, ValidationError

from .tracer_contracts import (FRAME, KEYS, canonical, native_keys, sha256_file,
                               summarize_array, validate_transform)


def _source_path(root, entry):
    relative = Path(entry["relative_path"])
    path = (root / relative).resolve()
    if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root.resolve()):
        raise ValueError("unsafe source path")
    expected = Path("raw") / entry.get("split", "validation") / entry["component"] / (entry["context"] + ".parquet")
    if relative != expected:
        raise ValueError("source path disagrees with component/context")
    return path


def _verify_sources(root, receipt):
    if receipt["release"] != "v2.0.1" or receipt["split"] not in ("training", "validation", "testing"):
        raise ValueError("unsupported release/split")
    entries = receipt["objects"]
    if not entries or len({e["relative_path"] for e in entries}) != len(entries):
        raise ValueError("empty or duplicate source inventory")
    if (sum(e["size_bytes"] for e in entries) != receipt["total_bytes"]
            or receipt["total_bytes"] > receipt["local_byte_limit"]):
        raise ValueError("source byte budget/inventory mismatch")
    if set(e["context"] for e in entries) != set(receipt["contexts"]):
        raise ValueError("source context inventory mismatch")
    if set(e["component"] for e in entries) != set(receipt["components"]):
        raise ValueError("source component inventory mismatch")
    for entry in entries:
        path = _source_path(root, dict(entry, split=receipt["split"]))
        if not path.is_file() or path.stat().st_size != entry["size_bytes"] or sha256_file(path) != entry["sha256"]:
            raise ValueError(f"source integrity mismatch: {entry['relative_path']}")


def _image_summary(payload):
    with Image.open(io.BytesIO(payload)) as image:
        image.load()
        return {"state": "present", "format": image.format, "mode": image.mode,
                "width": image.width, "height": image.height,
                "encoded_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def _payloads(parquet, component, keys):
    names = parquet.schema_arrow.names
    large = [n for n in names if pa.types.is_binary(parquet.schema_arrow.field(n).type)
             or (n.endswith(".values") and component in
                 ("lidar", "lidar_pose", "lidar_camera_projection", "lidar_segmentation"))]
    if not large:
        return {}, large
    shapes = [n[:-6] + "shape" for n in large if n.endswith("values")]
    columns = list(keys) + large + shapes
    divisor = "[CameraSegmentationLabelComponent].panoptic_label_divisor"
    if component == "camera_segmentation":
        columns.append(divisor)
    summaries = {}
    for batch in parquet.iter_batches(batch_size=1, columns=columns):
        key = tuple(batch.column(batch.schema.get_field_index(n))[0].as_py() for n in keys)
        summary = {}
        for name in large:
            scalar = batch.column(batch.schema.get_field_index(name))[0]
            if not scalar.is_valid:
                summary[name] = {"state": "unknown", "reason": "null source payload"}
            elif name.endswith(".values"):
                shape = batch.column(batch.schema.get_field_index(name[:-6] + "shape"))[0].as_py()
                summary[name] = summarize_array(component, scalar.values.to_numpy(zero_copy_only=False), shape)
            else:
                payload = scalar.as_py()
                info = _image_summary(payload)
                if component == "camera_segmentation" and name.endswith(".panoptic_label"):
                    d = batch.column(batch.schema.get_field_index(divisor))[0].as_py()
                    if not d or d <= 0:
                        raise ValueError("invalid panoptic divisor")
                    with Image.open(io.BytesIO(payload)) as image:
                        values = np.asarray(image)
                        codes, counts = np.unique(values // d, return_counts=True)
                        info["semantic_counts"] = {str(int(k)): int(v) for k, v in zip(codes, counts)}
                        info["instance_ids"] = int(len(np.unique(values % d)))
                summary[name] = info
        summaries[key] = summary
    return summaries, large


def _inspect_source(root, entry, receipt, sink):
    path = _source_path(root, dict(entry, split=receipt["split"]))
    component = entry["component"]
    keys = native_keys(component)
    with pq.ParquetFile(path) as parquet:
        schema = parquet.schema_arrow
        if set(n for n in schema.names if n.startswith("key.")) != set(keys):
            raise ValueError(f"key schema mismatch: {component}")
        if schema.field(FRAME[0]).type != pa.string():
            raise ValueError("context key type mismatch")
        if FRAME[1] in keys and schema.field(FRAME[1]).type != pa.int64():
            raise ValueError("timestamp key must be int64 microseconds")
        key_rows = parquet.read(columns=list(keys)).to_pylist()
        native = [tuple(row[k] for k in keys) for row in key_rows]
        if any(any(v is None for v in k) for k in native):
            raise ValueError(f"null native key: {component}")
        if len(set(native)) != len(native):
            raise ValueError(f"duplicate native key: {component}")
        if any(k[0] != entry["context"] for k in native):
            raise ValueError("context/path mismatch")
        for sensor in ("key.camera_name", "key.laser_name"):
            if sensor in keys and any(k[keys.index(sensor)] not in range(1, 6) for k in native):
                raise ValueError("unknown sensor enum")
        payloads, excluded = _payloads(parquet, component, keys)
        metadata_names = [n for n in schema.names if n not in excluded and n != "index"]
        metadata = parquet.read(columns=metadata_names).to_pylist()
        max_transform_error = 0.0
        records = []
        for row in metadata:
            key = tuple(row[k] for k in keys)
            for name, value in row.items():
                if name.endswith(".transform"):
                    max_transform_error = max(max_transform_error, validate_transform(value))
            record = {"schema_version": 1, "component": component,
                      "release": receipt["release"], "split": receipt["split"],
                      "key": {name: row[name] for name in keys},
                      "source_sha256": entry["sha256"],
                      "values": {n: v for n, v in row.items() if n not in keys},
                      "payloads": payloads.get(key, {})}
            record["id"] = hashlib.sha256(canonical(
                [receipt["release"], receipt["split"], component, *key])).hexdigest()
            records.append((key, record))
        for _, record in sorted(records, key=lambda pair: pair[0]):
            sink.write(canonical(record))
        frames = set((k[0], k[keys.index(FRAME[1])]) for k in native) if FRAME[1] in keys else set()
        return {"component": component, "context": entry["context"],
                "rows": len(native), "frames": len(frames),
                "native_keys": list(keys), "schema": str(schema),
                "schema_sha256": hashlib.sha256(str(schema).encode()).hexdigest(),
                "max_transform_orthogonality_error": max_transform_error,
                "payload_rows_inspected": len(payloads),
                "source_bytes": entry["size_bytes"]}, set(native), frames


def _joins(key_sets, frames):
    result = {}
    pose_frames = key_sets.get("vehicle_pose", set())
    union = set().union(*frames.values()) if frames else set()
    orphans = {c: len(v - pose_frames) for c, v in frames.items()}
    result.update(frame_union_count=len(union), vehicle_pose_frames=len(pose_frames),
                  orphan_frame_counts=orphans)
    if any(orphans.values()):
        raise ValueError(f"frame keys without vehicle pose: {orphans}")
    camera = key_sets.get("camera_box", set())
    lidar = key_sets.get("lidar_box", set())
    associations = key_sets.get("camera_to_lidar_box_association", set())
    result["associations"] = {"rows": len(associations),
        "unmatched_camera_boxes": sum(k[:4] not in camera for k in associations),
        "unmatched_lidar_boxes": sum(k[:2] + k[4:] not in lidar for k in associations),
        "target_state": "unknown_when_unmatched"}
    missing = [k for k in associations if k[:2] + k[4:] not in lidar]
    object_ids = {(k[0], k[-1]) for k in lidar}
    result["associations"]["unmatched_lidar_object_seen_other_frames"] = sum(
        (k[0], k[-1]) in object_ids for k in missing)
    result["associations"]["unmatched_by_context"] = {
        context: sum(k[0] == context for k in missing) for context in sorted({k[0] for k in associations})}
    if result["associations"]["unmatched_camera_boxes"]:
        raise ValueError("association references absent camera boxes")
    for sensor_component, calibration, sensor in [
            ("camera_image", "camera_calibration", 2), ("lidar", "lidar_calibration", 2)]:
        missing = sum((k[0], k[sensor]) not in key_sets.get(calibration, set())
                      for k in key_sets.get(sensor_component, set()))
        result[sensor_component + "_missing_calibrations"] = missing
        if missing:
            raise ValueError("sensor record without calibration")
    result["join_strategy"] = "native-key references; no sensor/object cross product"
    return result


def inspect_slice(root, output, *, output_byte_limit=512 * 1024 * 1024):
    root, output = Path(root).resolve(), Path(output).absolute()
    if output.exists():
        raise FileExistsError(output)
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("output path overlaps source slice")
    t0 = time.monotonic()
    receipt = json.loads((root / "slice.json").read_text())
    receipt_digest = sha256_file(root / "slice.json")
    _verify_sources(root, receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="." + output.name + ".staging-", dir=output.parent))
    key_sets, frames = defaultdict(set), defaultdict(set)
    summaries = []
    try:
        with (staging / "manifest.jsonl").open("wb") as sink:
            for entry in sorted(receipt["objects"], key=lambda e: (e["component"], e["context"])):
                summary, keys, source_frames = _inspect_source(root, entry, receipt, sink)
                summaries.append(summary)
                key_sets[entry["component"]].update(keys)
                frames[entry["component"]].update(source_frames)
                if sink.tell() > output_byte_limit:
                    raise ValueError("output byte budget exceeded")
                print(f"inspected {entry['component']} {entry['context']}: {summary['rows']} rows", flush=True)
        joins = _joins(key_sets, frames)
        _verify_sources(root, receipt)
        if sha256_file(root / "slice.json") != receipt_digest:
            raise ValueError("source receipt changed during processing")
        environment = {n: importlib.metadata.version(n) for n in ("pyarrow", "numpy", "pillow", "jsonschema")}
        forbidden = [d.metadata["Name"] for d in importlib.metadata.distributions()
                     if "tensorflow" in d.metadata["Name"].lower() or "waymo-open-dataset" in d.metadata["Name"].lower()]
        if forbidden:
            raise ValueError("forbidden SDK/TensorFlow runtime")
        report = {"schema_version": 1, "passed": True, "scope": "real-data schema/geometry/payload plumbing",
                  "release": receipt["release"], "split": receipt["split"],
                  "contexts": receipt["contexts"], "component_count": len(receipt["components"]),
                  "absent_component_families": sorted(set(KEYS) - set(receipt["components"])),
                  "source_files": len(receipt["objects"]), "source_bytes": receipt["total_bytes"],
                  "manifest_rows": sum(s["rows"] for s in summaries),
                  "component_summaries": summaries, "joins": joins,
                  "environment": environment, "duration_seconds": time.monotonic() - t0,
                  "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                  "memory_scope": "Linux process peak RSS, including Arrow decompression",
                  "network_mode": "bwrap unshare-all; no credential mounts" if os.environ.get("WAYMO_TRACER_OFFLINE") == "1" else "caller-enforced; see isolated runner",
                  "association_resolution": "incomplete" if joins["associations"]["unmatched_lidar_boxes"] else "complete",
                  "issues": [{"code": "association_target_unresolved", "severity": "warning",
                              "count": joins["associations"]["unmatched_lidar_boxes"],
                              "state": "unknown", "behavior": "preserved; no cross-frame substitution"}]
                            if joins["associations"]["unmatched_lidar_boxes"] else [],
                  "limitations": ["no point conversion or motion compensation", "no model or task metrics",
                                   "sparse modalities preserve native coverage", "no payload export"]}
        (staging / "sources.json").write_bytes(canonical(receipt))
        (staging / "report.json").write_bytes(canonical(report))
        artifacts = {n: {"sha256": sha256_file(staging / n), "bytes": (staging / n).stat().st_size}
                     for n in ("manifest.jsonl", "sources.json", "report.json")}
        experiment = Path(__file__).parent.parent
        implementation = [*Path(__file__).parent.glob("tracer*.py"),
                          *experiment.glob("tracer-*.schema.json"),
                          experiment / "tracer.sh", experiment / "requirements-tracer.lock"]
        code_hashes = {str(p.relative_to(experiment)): sha256_file(p) for p in implementation}
        (staging / "result.json").write_bytes(canonical({"schema_version": 1,
            "source_receipt_sha256": receipt_digest, "artifacts": artifacts,
            "implementation_hashes": code_hashes, "environment": environment}))
        if sum(p.stat().st_size for p in staging.iterdir()) > output_byte_limit:
            raise ValueError("output byte budget exceeded")
        validate_run(staging, root)
        # mkdir reservation prevents concurrent workers replacing the same run.
        output.mkdir()
        try:
            os.rename(staging, output)
        except BaseException:
            output.rmdir()
            raise
        return report
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def validate_run(output, root=None):
    output = Path(output)
    experiment = Path(__file__).parent.parent
    validators = {name: Draft202012Validator(json.loads(
        (experiment / f"tracer-{name}.schema.json").read_text()))
        for name in ("manifest", "report", "result")}
    def check_schema(name, value):
        try:
            validators[name].validate(value)
        except ValidationError as error:
            raise ValueError(f"{name} schema validation failed: {error.message}") from error
    result = json.loads((output / "result.json").read_text())
    check_schema("result", result)
    for name, expected in result["artifacts"].items():
        if name not in ("manifest.jsonl", "sources.json", "report.json"):
            raise ValueError("unsafe artifact name")
        if sha256_file(output / name) != expected["sha256"] or (output / name).stat().st_size != expected["bytes"]:
            raise ValueError("output artifact integrity mismatch")
    report = json.loads((output / "report.json").read_text())
    check_schema("report", report)
    receipt = json.loads((output / "sources.json").read_text())
    sources = {(e["component"], e["context"]): e for e in receipt["objects"]}
    if len(sources) != len(receipt["objects"]):
        raise ValueError("duplicate source component/context")
    observed = defaultdict(set)
    count = 0
    dimensions, range_shapes = {}, {}
    with (output / "manifest.jsonl").open() as handle:
        for line in handle:
            row = json.loads(line)
            check_schema("manifest", row)
            keys = native_keys(row["component"])
            if set(row["key"]) != set(keys):
                raise ValueError("native key fields mismatch")
            expected = hashlib.sha256(canonical([row["release"], row["split"], row["component"],
                                                *(row["key"][k] for k in keys)])).hexdigest()
            if row["id"] != expected:
                raise ValueError("record identity mismatch")
            component = row["component"]
            source_key = (component, row["key"][FRAME[0]])
            source = sources.get(source_key)
            if (source is None or row["source_sha256"] != source["sha256"]
                    or row["release"] != receipt["release"] or row["split"] != receipt["split"]):
                raise ValueError("manifest source lineage mismatch")
            native_key = tuple(row["key"][k] for k in keys)
            if native_key in observed[source_key]:
                raise ValueError("duplicate manifest native key")
            observed[source_key].add(native_key)
            if component == "camera_calibration":
                dimensions[(row["key"][FRAME[0]], row["key"]["key.camera_name"])] = (
                    row["values"]["[CameraCalibrationComponent].width"],
                    row["values"]["[CameraCalibrationComponent].height"])
            if component in ("camera_image", "camera_segmentation"):
                expected_dimensions = dimensions.get((row["key"][FRAME[0]], row["key"]["key.camera_name"]))
                for payload in row["payloads"].values():
                    if payload["state"] == "present" and (payload["width"], payload["height"]) != expected_dimensions:
                        raise ValueError("image/segmentation dimensions disagree with calibration")
            if component in ("lidar", "lidar_pose", "lidar_segmentation", "lidar_camera_projection"):
                sensor_key = tuple(row["key"][k] for k in native_keys("lidar"))
                for name, payload in row["payloads"].items():
                    return_name = name.split("range_image_", 1)[1].split(".", 1)[0]
                    if payload["state"] != "present":
                        continue
                    if component == "lidar":
                        range_shapes[(sensor_key, return_name)] = payload["shape"][:2]
                    elif payload["shape"][:2] != range_shapes.get((sensor_key, return_name)):
                        raise ValueError("auxiliary range shape disagrees with LiDAR return")
            count += 1
    if count != report["manifest_rows"] or not report["passed"]:
        raise ValueError("manifest/report count mismatch")
    if root is not None:
        if receipt != json.loads((Path(root) / "slice.json").read_text()):
            raise ValueError("stored source receipt disagrees with source")
        if sha256_file(Path(root) / "slice.json") != result["source_receipt_sha256"]:
            raise ValueError("source receipt integrity mismatch")
        _verify_sources(Path(root), receipt)
        for source_key, entry in sources.items():
            keys = native_keys(entry["component"])
            table = pq.read_table(_source_path(Path(root), dict(entry, split=receipt["split"])),
                                  columns=list(keys))
            expected_keys = {tuple(row[k] for k in keys) for row in table.to_pylist()}
            if len(expected_keys) != table.num_rows or observed[source_key] != expected_keys:
                raise ValueError("manifest/source native keys mismatch")
    return {"passed": True, "manifest_rows": count, "source_revalidated": root is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "validate"))
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "inspect":
        result = inspect_slice(args.sample, args.output)
        print(json.dumps({k: result[k] for k in ("passed", "manifest_rows", "duration_seconds", "peak_rss_bytes")}))
    else:
        print(json.dumps(validate_run(args.output, args.sample)))


if __name__ == "__main__":
    main()
