import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import re

from insula.launch_plan import RuntimeLock, plan_data
import insula.launch_plan as launch_plan_module
from training_execution import admit_sustained, sustained_controller_backend


class SustainedLaunchPlanTests(unittest.TestCase):
    def runtime(self, root, name, digest, *, form="recipe-digest"):
        rootfs = root / name
        rootfs.mkdir()
        return RuntimeLock(
            rootfs=rootfs,
            lock_path=Path(str(rootfs) + ".lock.json"),
            data={"schema_version": 1, "rootfs_sha256": digest},
            form=form,
            lock_sha256=digest,
        )

    def fake_gpu_environment(self, root):
        devices = root / "devices"
        drivers = root / "drivers"
        devices.mkdir()
        drivers.mkdir()
        for name in ["nvidia1", "nvidiactl", "nvidia-uvm"]:
            (devices / name).write_text(name + "\n")
        for name in [
            "libcuda.so.fixture",
            "libnvidia-ptxjitcompiler.so.fixture",
            "libnvidia-nvvm.so.fixture",
        ]:
            (drivers / name).write_text(name + "\n")
        pairs = [
            f"{devices / 'nvidia1'}=/dev/nvidia1",
            f"{devices / 'nvidiactl'}=/dev/nvidiactl",
            f"{devices / 'nvidia-uvm'}=/dev/nvidia-uvm",
        ]
        return {
            "SUREAL_BAZEL_GPU_DEVICES": ",".join(pairs),
            "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(drivers),
            "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-fixture-1",
        }

    def inputs(self, root):
        paths = {}
        for name in [
            "package",
            "stage-input",
            "output",
            "native",
            "physical",
            "boxes",
            "scientific",
            "source-snapshots",
            "retained",
            "previous",
            "verifier",
            "heads",
            "prepared",
            "scored",
        ]:
            path = root / name
            path.mkdir()
            (path / "file.txt").write_text(name + "\n")
            paths[name] = path
        runtime_lock = root / "runtime-lock.json"
        runtime_lock.write_text('{"rootfs_sha256":"%s"}\n' % ("a" * 64))
        score_receipt = root / "score-receipt.json"
        expected = root / "expected.json"
        score_receipt.write_text("{}\n")
        expected.write_text("{}\n")
        paths.update(
            {
                "runtime_lock": runtime_lock,
                "score_receipt": score_receipt,
                "expected": expected,
            }
        )
        return paths

    def build(self, runtime, paths, *, worker, extra=(), gpu_index=None):
        return sustained_controller_backend.build_sustained_stage_plan(
            runtime,
            package=paths["package"],
            stage_source=paths["stage-input"],
            output=paths["output"],
            worker=worker,
            native=paths["native"],
            physical=paths["physical"],
            boxes=paths["boxes"],
            runtime_lock_path=paths["runtime_lock"],
            scientific_root=paths["scientific"],
            source_snapshot_store=paths["source-snapshots"],
            extra=extra,
            gpu_index=gpu_index,
            source_snapshot_digest="c" * 64,
        )

    def test_gpu_stage_plan_declares_common_inputs_environment_and_gpu_one(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root)
            runtime = self.runtime(root, "gpu-rootfs-v7", "1" * 64)
            with patch.dict("os.environ", self.fake_gpu_environment(root), clear=False):
                plan = self.build(
                    runtime,
                    paths,
                    worker="train_sustained.py",
                    gpu_index=sustained_controller_backend.GPU_INDEX,
                )

            data = plan_data(plan)
            mounts = {mount["inside_path"]: mount for mount in data["mounts"]}
            for inside in [
                "/tmp/inputs",
                "/tmp/native",
                "/tmp/physical",
                "/tmp/boxes",
                "/tmp/runtime-lock.json",
                "/tmp/scientific",
                "/tmp/source-snapshots",
            ]:
                self.assertEqual(mounts[inside]["role"], f"input:{inside}")
            self.assertNotIn("/source", mounts)
            environment = {item[1]: item[2] for item in data["environment"]}
            self.assertEqual(environment["SUREAL_SOURCE_SNAPSHOT_STORE"], "/tmp/source-snapshots")
            self.assertEqual(environment["CUBLAS_WORKSPACE_CONFIG"], ":4096:8")
            self.assertEqual(data["gpu"], {"requested_index": 1, "device_uuid": "GPU-fixture-1"})
            self.assertEqual(
                data["command"],
                ["python", "/experiment/training_execution/train_sustained.py"],
            )

    def test_recording_sustained_plan_does_not_digest_live_scientific_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root)
            output = paths["scientific"] / "balanced16-sustained-baseline-run1" / "update-1000"
            output.mkdir(parents=True)
            (output / "just-created-output.tmp").write_text("new output must not enter input digest\n")
            runtime = self.runtime(root, "gpu-rootfs-v7", "1" * 64)
            original_content_digest = launch_plan_module._content_digest

            def guarded_content_digest(path):
                if Path(path) == paths["scientific"]:
                    raise AssertionError("recording must not hash the live scientific root")
                return original_content_digest(path)

            with patch.dict("os.environ", self.fake_gpu_environment(root), clear=False):
                plan = sustained_controller_backend.build_sustained_stage_plan(
                    runtime,
                    package=paths["package"],
                    stage_source=paths["stage-input"],
                    output=output,
                    worker="train_sustained.py",
                    native=paths["native"],
                    physical=paths["physical"],
                    boxes=paths["boxes"],
                    runtime_lock_path=paths["runtime_lock"],
                    scientific_root=paths["scientific"],
                    source_snapshot_store=paths["source-snapshots"],
                    gpu_index=sustained_controller_backend.GPU_INDEX,
                    source_snapshot_digest="c" * 64,
                )
                with patch("insula.launch_plan._content_digest", side_effect=guarded_content_digest):
                    record = sustained_controller_backend.record_plan(plan)

            mounts = {mount["inside_path"]: mount for mount in record["mounts"]}
            self.assertRegex(mounts["/tmp/scientific"]["digest"], re.compile(r"^[0-9a-f]{64}$"))
            self.assertEqual(mounts["/tmp/scientific"]["mode"], "read_only")

    def test_each_sustained_stage_shape_has_a_structured_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.inputs(root)
            gpu_runtime = self.runtime(root, "gpu-rootfs-v7", "1" * 64)
            cpu_runtime = self.runtime(root, "rootfs-v5", "2" * 64)
            metrics_runtime = self.runtime(root, "metrics-rootfs-v2", "3" * 64, form="image")
            cases = [
                (
                    "audit_sustained_transition.py",
                    gpu_runtime,
                    {
                        "/tmp/verifier": paths["verifier"],
                        "/tmp/retained": paths["retained"],
                        "/tmp/previous": paths["previous"],
                    },
                    1,
                    None,
                    {
                        "/tmp/verifier",
                        "/tmp/retained",
                        "/tmp/previous",
                    },
                    ["python", "/tmp/verifier/audit_sustained_transition.py"],
                ),
                (
                    "audit_sustained_loss.py",
                    cpu_runtime,
                    {"/source": paths["retained"]},
                    None,
                    "/source",
                    set(),
                    ["python", "/experiment/training_execution/audit_sustained_loss.py"],
                ),
                (
                    "prepare_sustained_v3.py",
                    cpu_runtime,
                    {"/source": paths["heads"]},
                    None,
                    "/source",
                    set(),
                    ["python", "/experiment/evaluation/prepare_sustained_v3.py"],
                ),
                (
                    "audit_proposals_sustained_v3.py",
                    cpu_runtime,
                    {
                        "/source": paths["prepared"],
                        "/tmp/heads": paths["heads"],
                        "/tmp/score-receipt.json": paths["score_receipt"],
                        "/tmp/expected.json": paths["expected"],
                    },
                    None,
                    "/source",
                    {"/tmp/heads", "/tmp/score-receipt.json", "/tmp/expected.json"},
                    ["python", "/experiment/evaluation/audit_proposals_sustained_v3.py"],
                ),
                (
                    "metrics_sustained_v3.py",
                    metrics_runtime,
                    {"/source": paths["prepared"]},
                    None,
                    "/source",
                    set(),
                    ["python", "/experiment/evaluation/metrics_sustained_v3.py"],
                ),
                (
                    "audit_metrics_sustained_v3.py",
                    metrics_runtime,
                    {
                        "/source": paths["prepared"],
                        "/tmp/scored": paths["scored"],
                        "/tmp/score-receipt.json": paths["score_receipt"],
                        "/tmp/expected.json": paths["expected"],
                    },
                    None,
                    "/source",
                    {"/tmp/scored", "/tmp/score-receipt.json", "/tmp/expected.json"},
                    ["python", "/experiment/evaluation/audit_metrics_sustained_v3.py"],
                ),
            ]
            with patch.dict("os.environ", self.fake_gpu_environment(root), clear=False):
                for worker, runtime, extra, gpu_index, source_path, expected_inputs, command in cases:
                    with self.subTest(worker=worker):
                        data = plan_data(
                            self.build(
                                runtime,
                                paths,
                                worker=worker,
                                extra=extra,
                                gpu_index=gpu_index,
                            )
                        )
                        mounts = {mount["inside_path"]: mount for mount in data["mounts"]}
                        self.assertEqual(data["runtime"]["rootfs"], str(runtime.rootfs))
                        self.assertEqual(data["command"], command)
                        self.assertEqual(("/source" in mounts), source_path is not None)
                        for inside in expected_inputs | {"/tmp/inputs"}:
                            self.assertEqual(mounts[inside]["role"], f"input:{inside}")
                        if gpu_index is None:
                            self.assertNotIn("gpu", data)
                        else:
                            self.assertEqual(data["gpu"]["requested_index"], gpu_index)

    def test_sustained_callers_do_not_replay_detector_gpu_receipt_or_entry_launcher(self):
        forbidden = [
            "detector-gpu-live-a/receipt.json",
            "rebind_rootfs_mount",
            "old['checks']",
            'old["checks"]',
            "from insula.entry import launch_plan",
            "verify_rootfs(",
        ]
        for module in [admit_sustained, sustained_controller_backend]:
            source = Path(module.__file__).read_text()
            with self.subTest(module=module.__name__):
                for token in forbidden:
                    self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
