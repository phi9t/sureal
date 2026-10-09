import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


CLASSES = [
    "TYPE_TRAFFIC_LIGHT",
    "TYPE_BUILDING",
    "TYPE_OTHER_VEHICLE",
    "TYPE_MOTORCYCLE",
    "TYPE_ROAD",
    "TYPE_BUS",
    "TYPE_SIGN",
    "TYPE_CURB",
    "TYPE_SIDEWALK",
    "TYPE_PEDESTRIAN",
    "TYPE_BICYCLE",
    "TYPE_TRUCK",
    "TYPE_WALKABLE",
    "TYPE_CONSTRUCTION_CONE",
    "TYPE_TREE_TRUNK",
    "TYPE_CAR",
    "TYPE_BICYCLIST",
    "TYPE_OTHER_GROUND",
    "TYPE_VEGETATION",
    "TYPE_MOTORCYCLIST",
    "TYPE_POLE",
    "TYPE_LANE_MARKER",
]

FIXTURE_MEANS = {
    "perfect": 1.0,
    "undefined-predictions": 0.0,
    "wrong-class": 0.0,
    "ignored-groundtruth": 1.0,
    "absent-classes": 1.0,
}


def load_fixture_module():
    path = Path(__file__).with_name("segmentation-contract-fixtures.py")
    spec = importlib.util.spec_from_file_location("segmentation_contract_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report_for(mean, extra_line=None):
    lines = [
        "1 frames found in prediction.",
        "1 frames found in groundtruth.",
        "Processing example 0 out of 1",
    ]
    lines.extend(f"{name}:{mean:g}" for name in CLASSES)
    if extra_line is not None:
        lines.append(extra_line)
    lines.append(f"miou={mean:g}")
    return "\n".join(lines) + "\n"


class SegmentationContractFixturesTests(unittest.TestCase):
    def test_fixture_metric_report_with_nan_class_line_is_rejected(self):
        module = load_fixture_module()

        def fake_run(command, **kwargs):
            fixture = Path(command[1]).name.removesuffix("-pred.bin")
            extra = "TYPE_POLE:nan" if fixture == "perfect" else None
            return subprocess.CompletedProcess(
                command,
                0,
                report_for(FIXTURE_MEANS[fixture], extra),
                "",
            )

        with tempfile.TemporaryDirectory() as tmp:
            original_out = module.OUT
            original_frame = module.frame
            original_run = module.subprocess.run
            try:
                module.OUT = Path(tmp)
                module.frame = lambda labels: b"frame"
                module.subprocess.run = fake_run
                with self.assertRaises(ValueError):
                    module.main()
            finally:
                module.OUT = original_out
                module.frame = original_frame
                module.subprocess.run = original_run


if __name__ == "__main__":
    unittest.main()
