import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from insula.launch_plan import load_runtime_lock, plan_data, render_plan
from insula.runtime_roots import default_lock
from training_execution import sustained_controller_backend


HOST_GPU_ROOT = Path("/data02/home/philip.yang/.cache/waystone/waymo-perception/gpu-rootfs-v7")


class SustainedLaunchPlanGPUSmokeTests(unittest.TestCase):
    def test_trivial_stage_runs_through_controller_gpu_one_plan(self):
        rootfs = Path(os.environ.get("WAYMO_GPU_INSULA_ROOT", HOST_GPU_ROOT)).resolve()
        lock = Path(os.environ.get("WAYMO_GPU_INSULA_LOCK", default_lock(rootfs))).resolve()
        runtime = load_runtime_lock(rootfs, lock)
        if Path("/driver").is_dir():
            os.environ.setdefault("SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS", "/driver")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
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
            ]:
                path = root / name
                path.mkdir()
                (path / "fixture.txt").write_text(name + "\n")
                paths[name] = path
            runtime_lock = root / "runtime-lock.json"
            runtime_lock.write_text(json.dumps(runtime.data, sort_keys=True) + "\n")
            plan = sustained_controller_backend.build_sustained_stage_plan(
                runtime,
                package=paths["package"],
                stage_source=paths["stage-input"],
                output=paths["output"],
                worker=None,
                command=[
                    "/opt/waymo/bin/python",
                    "-c",
                    (
                        "import json, torch; "
                        "from pathlib import Path; "
                        "ok=torch.cuda.is_available() and torch.cuda.device_count()==1; "
                        "Path('/outputs/gpu-smoke.json').write_text(json.dumps("
                        "{'cuda': torch.cuda.is_available(), 'count': torch.cuda.device_count(), "
                        "'device': torch.cuda.get_device_name(0)})); "
                        "raise SystemExit(0 if ok else 1)"
                    ),
                ],
                native=paths["native"],
                physical=paths["physical"],
                boxes=paths["boxes"],
                runtime_lock_path=runtime_lock,
                scientific_root=paths["scientific"],
                source_snapshot_store=paths["source-snapshots"],
                gpu_index=sustained_controller_backend.GPU_INDEX,
            )
            self.assertEqual(plan_data(plan)["gpu"]["requested_index"], 1)
            argv = render_plan(plan)
            argv[0] = os.environ.get("SUREAL_LIVE_GATE_BWRAP", argv[0])
            result = subprocess.run(argv, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((paths["output"] / "gpu-smoke.json").read_text())
            self.assertEqual(report["count"], 1)
            self.assertTrue(report["cuda"])


if __name__ == "__main__":
    unittest.main()
