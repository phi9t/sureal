import hashlib
import json
import os
import runpy
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


BREAKDOWNS = (
    "OBJECT_TYPE_TYPE_VEHICLE_LEVEL_1",
    "OBJECT_TYPE_TYPE_VEHICLE_LEVEL_2",
    "OBJECT_TYPE_TYPE_PEDESTRIAN_LEVEL_1",
    "OBJECT_TYPE_TYPE_PEDESTRIAN_LEVEL_2",
    "OBJECT_TYPE_TYPE_SIGN_LEVEL_1",
    "OBJECT_TYPE_TYPE_SIGN_LEVEL_2",
    "OBJECT_TYPE_TYPE_CYCLIST_LEVEL_1",
    "OBJECT_TYPE_TYPE_CYCLIST_LEVEL_2",
    "RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_1",
    "RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_2",
    "RANGE_TYPE_VEHICLE_[30, 50)_LEVEL_1",
    "RANGE_TYPE_VEHICLE_[30, 50)_LEVEL_2",
    "RANGE_TYPE_VEHICLE_[50, +inf)_LEVEL_1",
    "RANGE_TYPE_VEHICLE_[50, +inf)_LEVEL_2",
    "RANGE_TYPE_PEDESTRIAN_[0, 30)_LEVEL_1",
    "RANGE_TYPE_PEDESTRIAN_[0, 30)_LEVEL_2",
    "RANGE_TYPE_PEDESTRIAN_[30, 50)_LEVEL_1",
    "RANGE_TYPE_PEDESTRIAN_[30, 50)_LEVEL_2",
    "RANGE_TYPE_PEDESTRIAN_[50, +inf)_LEVEL_1",
    "RANGE_TYPE_PEDESTRIAN_[50, +inf)_LEVEL_2",
    "RANGE_TYPE_SIGN_[0, 30)_LEVEL_1",
    "RANGE_TYPE_SIGN_[0, 30)_LEVEL_2",
    "RANGE_TYPE_SIGN_[30, 50)_LEVEL_1",
    "RANGE_TYPE_SIGN_[30, 50)_LEVEL_2",
    "RANGE_TYPE_SIGN_[50, +inf)_LEVEL_1",
    "RANGE_TYPE_SIGN_[50, +inf)_LEVEL_2",
    "RANGE_TYPE_CYCLIST_[0, 30)_LEVEL_1",
    "RANGE_TYPE_CYCLIST_[0, 30)_LEVEL_2",
    "RANGE_TYPE_CYCLIST_[30, 50)_LEVEL_1",
    "RANGE_TYPE_CYCLIST_[30, 50)_LEVEL_2",
    "RANGE_TYPE_CYCLIST_[50, +inf)_LEVEL_1",
    "RANGE_TYPE_CYCLIST_[50, +inf)_LEVEL_2",
)

LEVEL2_SCORES = {
    "OBJECT_TYPE_TYPE_VEHICLE_LEVEL_2": (0.81, 0.82),
    "OBJECT_TYPE_TYPE_PEDESTRIAN_LEVEL_2": (0.71, 0.72),
    "OBJECT_TYPE_TYPE_SIGN_LEVEL_2": (0.61, 0.62),
    "OBJECT_TYPE_TYPE_CYCLIST_LEVEL_2": (0.51, 0.52),
    "RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_1": (0.31, 0.32),
}

KNOWN_STDERR = """WARNING: Logging before InitGoogleLogging() is written to STDERR
W20261003 07:16:14.727084     5 iou.cc:172] Tiny box dim seen, return 0.0 IOU.
b1: center_x: 16.576610254024722
center_y: 15.012704453096376
center_z: 12.068397189884765
width: 0.0018523699306077972
length: 1.0424807764507029e-14
height: 2.6744237701485357e-13
heading: 2.76738943655627

b2: center_x: -22.493484775371144
center_y: 9.195233822244063
center_z: 0.74115756813910139
width: 1.9570524265672498
length: 4.9495852117525452
height: 1.5099999999999909
heading: 3.0167059680111592
"""


def native_stdout():
    lines = ["7 examples found.", ""]
    for name in BREAKDOWNS:
        ap, aph = LEVEL2_SCORES.get(name, (0.0, 0.0))
        lines.append(f"{name}: [mAP {ap}] [mAPH {aph}]")
    return "\n".join(lines) + "\n"


def native_metrics():
    return {
        name: {"AP": LEVEL2_SCORES.get(name, (0.0, 0.0))[0],
               "APH": LEVEL2_SCORES.get(name, (0.0, 0.0))[1]}
        for name in BREAKDOWNS
    }


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PlainDetectionScorerTests(unittest.TestCase):
    def execute(self, *, groundtruth_by_class=None, stderr=KNOWN_STDERR):
        temp_root = os.environ.get("TEST_TMPDIR")
        with tempfile.TemporaryDirectory(dir=temp_root) as temp:
            worker = Path(__file__).with_name("metrics.py")
            root = Path(temp)
            out = root / "outputs"
            source = root / "source"
            out.mkdir()
            source.mkdir()
            (source / "predictions.json").write_text("[]")
            (source / "groundtruth.json").write_text("[]")
            preparation = {
                "groundtruth_by_class": groundtruth_by_class
                or {"1": 3, "2": 0, "3": 4, "4": 0},
            }
            (source / "preparation.json").write_text(json.dumps(preparation))
            result = types.SimpleNamespace(
                returncode=0, stdout=native_stdout(), stderr=stderr
            )
            real_path = Path

            def paths(value):
                if value == "/outputs":
                    return out
                if value.startswith("/source/"):
                    return source / value.split("/")[-1]
                return real_path(value)

            with patch("pathlib.Path", side_effect=paths), patch(
                "detection.detection_export.export_objects", return_value=b"fixture"
            ), patch("subprocess.run", return_value=result):
                runpy.run_path(str(worker), run_name="__main__")
            return json.loads((out / "check.json").read_text())

    def test_strict_reader_result_is_recorded_without_changing_level2_scores(self):
        report = self.execute()

        self.assertEqual(
            report["LEVEL2_per_class"],
            {
                "1": {"AP": 0.81, "APH": 0.82},
                "3": {"AP": 0.61, "APH": 0.62},
            },
        )
        self.assertAlmostEqual(report["mean_populated_class_APH"], 0.72)
        self.assertEqual(report["mean_scope"], "populated classes")
        self.assertEqual(report["diagnostics"]["glog_preinit"], 1)
        self.assertEqual(report["diagnostics"]["iou.cc:172 Tiny box dim seen"], 1)
        self.assertEqual(
            report["metrics"]["RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_1"],
            {"AP": 0.31, "APH": 0.32},
        )
        self.assertNotIn("30)_LEVEL_1", report["metrics"])

    def test_empty_populated_scope_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no populated detection classes"):
            self.execute(groundtruth_by_class={"1": 0, "2": 0, "3": 0, "4": 0})


class DetectionMetricAuditTests(unittest.TestCase):
    def test_metric_audit_rereads_strict_report_and_records_diagnostics(self):
        temp_root = os.environ.get("TEST_TMPDIR")
        with tempfile.TemporaryDirectory(dir=temp_root) as temp:
            from evidence import source_snapshot  # noqa: F401

            worker = Path(__file__).with_name("audit_metrics.py")
            root = Path(temp)
            source = root / "source"
            scored = root / "scored"
            tmp = root / "tmp"
            out = root / "outputs"
            for directory in (source, scored, tmp, out):
                directory.mkdir()
            for name in ("predictions", "groundtruth"):
                (source / f"{name}.json").write_text("[]")
                (scored / f"{name}.bin").write_bytes(b"fixture")
            validation = {
                "metrics": native_metrics(),
                "diagnostics": {
                    "glog_preinit": 1,
                    "iou.cc:172 Tiny box dim seen": 1,
                },
                "LEVEL2_per_class": {
                    "1": {"AP": 0.81, "APH": 0.82},
                    "3": {"AP": 0.61, "APH": 0.62},
                },
                "mean_populated_class_APH": 0.72,
                "APH_gate_passed": False,
            }
            receipt = {
                "artifacts": {
                    "prepared/predictions.json": sha256(source / "predictions.json"),
                    "prepared/groundtruth.json": sha256(source / "groundtruth.json"),
                    "scored/predictions.bin": sha256(scored / "predictions.bin"),
                    "scored/groundtruth.bin": sha256(scored / "groundtruth.bin"),
                },
                "validation": validation,
            }
            score_receipt = tmp / "score-receipt.json"
            score_receipt.write_text(json.dumps(receipt, sort_keys=True))
            (tmp / "expected.json").write_text(
                json.dumps(
                    {"receipt": receipt, "receipt_sha256": sha256(score_receipt)},
                    sort_keys=True,
                )
            )
            real_path = Path

            def paths(value):
                text = os.fspath(value)
                if text == "/outputs":
                    return out
                if text.startswith("/outputs/"):
                    return out / text.split("/")[-1]
                if text == "/tmp/expected.json":
                    return tmp / "expected.json"
                if text == "/tmp/score-receipt.json":
                    return score_receipt
                if text == "/tmp/scored":
                    return scored
                if text == "/source":
                    return source
                if text.startswith("/tmp/scored/"):
                    return scored / text.split("/")[-1]
                if text.startswith("/source/"):
                    return source / text.split("/")[-1]
                return real_path(value)

            def run_side_effect(command, **kwargs):
                if command[0] == "protoc":
                    return types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
                return types.SimpleNamespace(
                    returncode=0, stdout=native_stdout(), stderr=KNOWN_STDERR
                )

            def audit_sha(value):
                text = os.fspath(value)
                if text == "/tmp/score-receipt.json":
                    return sha256(score_receipt)
                if text.startswith("/tmp/scored/"):
                    return sha256(scored / text.split("/")[-1])
                if text.startswith("/source/"):
                    return sha256(source / text.split("/")[-1])
                return sha256(real_path(text))

            with patch("pathlib.Path", side_effect=paths), patch(
                "subprocess.run", side_effect=run_side_effect
            ), patch("evidence.source_snapshot.file_sha256", side_effect=audit_sha):
                runpy.run_path(str(worker), run_name="__main__")

            report = json.loads((real_path(out) / "check.json").read_text())
            self.assertTrue(report["native_metric_replay_exact"])
            self.assertEqual(report["diagnostics"]["glog_preinit"], 1)
            self.assertEqual(
                report["diagnostics"]["iou.cc:172 Tiny box dim seen"], 1
            )


class RealDetectionExportCheckTests(unittest.TestCase):
    def test_real_export_check_rejects_duplicate_metric_breakdown(self):
        temp_root = os.environ.get("TEST_TMPDIR")
        with tempfile.TemporaryDirectory(dir=temp_root) as temp:
            worker = Path(__file__).with_name("real-detection-export-check.py")
            root = Path(temp)
            source = root / "source"
            out = root / "outputs"
            source.mkdir()
            out.mkdir()
            record = {
                "context_name": "ctx",
                "frame_timestamp_micros": 123,
                "object_id": "obj",
                "type": 1,
                "box": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 0.5],
                "num_lidar_points_in_box": 7,
            }
            (source / "real-boxes.json").write_text(json.dumps([record]))
            decoded = b"""objects {
context_name: "ctx"
frame_timestamp_micros: 123
id: "obj"
type: TYPE_VEHICLE
center_x: 1
center_y: 2
center_z: 3
length: 4
width: 5
height: 6
heading: 0.5
score: 1
num_lidar_points_in_box: 7
overlap_with_nlz: false
}
"""
            real_path = Path

            def paths(value):
                text = os.fspath(value)
                if text == "/outputs":
                    return out
                if text == "/source/real-boxes.json":
                    return source / "real-boxes.json"
                return real_path(value)

            def run_side_effect(command, **kwargs):
                if command[0] == "protoc":
                    return types.SimpleNamespace(returncode=0, stdout=decoded, stderr=b"")
                lines = ["7 examples found.", ""]
                for name in BREAKDOWNS:
                    ap, aph = (1.0, 1.0) if name == (
                        "OBJECT_TYPE_TYPE_VEHICLE_LEVEL_2"
                    ) else (0.0, 0.0)
                    lines.append(f"{name}: [mAP {ap}] [mAPH {aph}]")
                lines.append("OBJECT_TYPE_TYPE_VEHICLE_LEVEL_2: [mAP 1] [mAPH 1]")
                duplicate = "\n".join(lines) + "\n"
                return types.SimpleNamespace(returncode=0, stdout=duplicate, stderr="")

            with patch("pathlib.Path", side_effect=paths), patch(
                "detection.detection_export.export_objects", return_value=b"fixture"
            ), patch("subprocess.run", side_effect=run_side_effect):
                with self.assertRaises(ValueError):
                    runpy.run_path(str(worker), run_name="__main__")


if __name__ == "__main__":
    unittest.main()
