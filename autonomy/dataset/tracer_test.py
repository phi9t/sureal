"""Behavioral tests for the real-data investigation seam."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from dataset.tracer_contracts import validate_transform, summarize_array, native_keys
from dataset.tracer import inspect_slice, validate_run, _joins


def fixture(root, duplicate=False):
    raw = root / "raw/validation/vehicle_pose"
    raw.mkdir(parents=True)
    path = raw / "scene.parquet"
    pq.write_table(pa.table({
        "key.segment_context_name": ["scene", "scene"],
        "key.frame_timestamp_micros": [10, 10 if duplicate else 20],
        "[VehiclePoseComponent].world_from_vehicle.transform": [np.eye(4).ravel().tolist()] * 2,
    }), path)
    receipt = {
        "schema_version": 1, "release": "v2.0.1", "split": "validation",
        "slice_id": "fixture", "contexts": ["scene"], "components": ["vehicle_pose"],
        "total_bytes": path.stat().st_size, "local_byte_limit": 1000000,
        "objects": [{"component": "vehicle_pose", "context": "scene",
                     "relative_path": "raw/validation/vehicle_pose/scene.parquet",
                     "size_bytes": path.stat().st_size,
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}],
    }
    (root / "slice.json").write_text(json.dumps(receipt))
    return receipt


class ContractsTests(unittest.TestCase):
    def test_native_labels_are_not_sensor_grain(self):
        self.assertEqual(native_keys("lidar_box"), (
            "key.segment_context_name", "key.frame_timestamp_micros", "key.laser_object_id"))
        self.assertEqual(native_keys("camera_to_lidar_box_association")[-2:],
                         ("key.camera_object_id", "key.laser_object_id"))

    def test_transform_rejects_nonfinite_and_nonrigid_values(self):
        self.assertEqual(validate_transform(np.eye(4).ravel().tolist()), 0.0)
        for matrix in [np.full((4, 4), np.nan), np.diag([2, 1, 1, 1]), np.eye(3)]:
            with self.assertRaises(ValueError):
                validate_transform(matrix.ravel().tolist())

    def test_range_summary_filters_invalid_ranges_and_preserves_unknown_nlz(self):
        result = summarize_array("lidar", np.array([[-1, 0, 0, -1],
                                 [3, 0, 0, 1], [5, 0, 0, 7]]).ravel(), [1, 3, 4])
        self.assertEqual(result["valid_positive_ranges"], 2)
        self.assertEqual(result["range_min_m"], 3)
        self.assertEqual(result["range_max_m"], 5)
        self.assertEqual(result["valid_nlz_counts"], {"1": 1, "7": 1})
        empty = summarize_array("lidar", np.array([-1, 0, 0, -1]), [1, 1, 4])
        self.assertIsNone(empty["range_min_m"])
        self.assertIsNone(empty["range_max_m"])

    def test_associations_validate_references_without_multiplying_rows(self):
        camera = {("scene", 10, 1, "c1"), ("scene", 10, 2, "c2")}
        lidar = {("scene", 10, "l1"), ("scene", 10, "l2")}
        associations = {("scene", 10, 1, "c1", "l1"),
                        ("scene", 10, 2, "c2", "l2")}
        sets = {"vehicle_pose": {("scene", 10)}, "camera_box": camera,
                "lidar_box": lidar, "camera_to_lidar_box_association": associations}
        result = _joins(sets, {"camera_box": {("scene", 10)}})
        self.assertEqual(result["associations"]["rows"], 2)
        self.assertEqual(result["associations"]["unmatched_lidar_boxes"], 0)
        sets["lidar_box"] = set()
        unresolved = _joins(sets, {"camera_box": {("scene", 10)}})
        self.assertEqual(unresolved["associations"]["unmatched_lidar_boxes"], 2)
        self.assertEqual(unresolved["associations"]["target_state"], "unknown_when_unmatched")
        self.assertEqual(unresolved["associations"]["rows"], 2)
        sets["camera_box"] = set()
        with self.assertRaisesRegex(ValueError, "camera"):
            _joins(sets, {"camera_box": {("scene", 10)}})

    def test_array_shape_and_channel_mismatches_fail(self):
        for shape in [[1, 1, 3], [2, 2, 4], [0, 1, 4]]:
            with self.assertRaises(ValueError):
                summarize_array("lidar", np.ones(4), shape)


class TracerTests(unittest.TestCase):
    def test_real_parquet_end_to_end_is_deterministic_and_detects_output_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "slice"
            fixture(root)
            for name in ["first", "second"]:
                inspect_slice(root, Path(tmp) / name)
                self.assertTrue(validate_run(Path(tmp) / name, root)["passed"])
            first, second = Path(tmp) / "first", Path(tmp) / "second"
            self.assertEqual((first / "manifest.jsonl").read_bytes(),
                             (second / "manifest.jsonl").read_bytes())
            rows = [json.loads(x) for x in (first / "manifest.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertNotIn(str(root), (first / "manifest.jsonl").read_text())
            (first / "manifest.jsonl").write_text("{}\n")
            with self.assertRaises(ValueError):
                validate_run(first, root)

    def test_schema_version_is_validated_independently_from_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "slice"
            fixture(root)
            out = Path(tmp) / "run"
            inspect_slice(root, out)
            path = out / "manifest.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[0]["schema_version"] = 99
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            result = json.loads((out / "result.json").read_text())
            result["artifacts"]["manifest.jsonl"] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size}
            (out / "result.json").write_text(json.dumps(result))
            with self.assertRaises(ValueError):
                validate_run(out, root)

    def test_independent_validation_reconciles_native_keys_and_lineage(self):
        for mutation in ("duplicate", "lineage", "substitute"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "slice"
                fixture(root)
                out = Path(tmp) / "run"
                inspect_slice(root, out)
                path = out / "manifest.jsonl"
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                if mutation == "duplicate":
                    rows[1] = rows[0]
                elif mutation == "lineage":
                    rows[0]["source_sha256"] = "0" * 64
                else:
                    rows[1]["key"]["key.frame_timestamp_micros"] = 30
                    from dataset.tracer_contracts import canonical
                    rows[1]["id"] = hashlib.sha256(canonical([
                        rows[1]["release"], rows[1]["split"], "vehicle_pose", "scene", 30])).hexdigest()
                path.write_text("".join(json.dumps(row) + "\n" for row in rows))
                result = json.loads((out / "result.json").read_text())
                result["artifacts"]["manifest.jsonl"] = {
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size}
                (out / "result.json").write_text(json.dumps(result))
                with self.assertRaises(ValueError):
                    validate_run(out, root)

    def test_source_mutation_and_duplicate_keys_prevent_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "slice"
            receipt = fixture(root, duplicate=True)
            out = Path(tmp) / "run"
            with self.assertRaisesRegex(ValueError, "duplicate"):
                inspect_slice(root, out)
            self.assertFalse(out.exists())
            path = root / receipt["objects"][0]["relative_path"]
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "source"):
                inspect_slice(root, out)
            self.assertFalse(out.exists())

    def test_path_escape_and_existing_run_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "slice"
            receipt = fixture(root)
            out = Path(tmp) / "run"
            inspect_slice(root, out)
            with self.assertRaises(FileExistsError):
                inspect_slice(root, out)
            receipt["objects"][0]["relative_path"] = "../outside.parquet"
            (root / "slice.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "path"):
                inspect_slice(root, Path(tmp) / "other")


if __name__ == "__main__":
    unittest.main()
