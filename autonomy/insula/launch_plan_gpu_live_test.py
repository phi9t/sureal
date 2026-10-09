import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from insula.launch_plan import build_plan, load_runtime_lock, plan_data, record_plan, render_plan
from insula.runtime_roots import current_gpu_rootfs, default_lock


AUTONOMY = Path(__file__).resolve().parents[1]


class LaunchPlanGPULiveTests(unittest.TestCase):
    def test_trivial_cuda_query_runs_through_gpu_one_plan(self):
        rootfs = Path(os.environ.get("WAYMO_GPU_INSULA_ROOT", current_gpu_rootfs())).resolve()
        lock = Path(os.environ.get("WAYMO_GPU_INSULA_LOCK", default_lock(rootfs))).resolve()
        runtime = load_runtime_lock(rootfs, lock)
        if Path("/driver").is_dir():
            os.environ.setdefault("SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS", "/driver")

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "outputs"
            output.mkdir()
            plan = build_plan(
                runtime,
                code=AUTONOMY,
                output=output,
                gpu_index=1,
                command=[
                    "/opt/waymo/bin/python",
                    "-c",
                    "\n".join(
                        [
                            "import json",
                            "from pathlib import Path",
                            "import torch",
                            "assert torch.cuda.is_available()",
                            "assert torch.cuda.device_count() == 1",
                            "tensor = torch.ones((1,), device='cuda')",
                            "Path('/outputs/cuda-query.json').write_text(json.dumps({'device_count': torch.cuda.device_count(), 'sum': float(tensor.sum().item())}) + '\\n')",
                        ]
                    ),
                ],
            )
            data = plan_data(plan)
            self.assertEqual(
                [device["inside_path"] for device in data["devices"]],
                ["/dev/nvidia1", "/dev/nvidiactl", "/dev/nvidia-uvm"],
            )
            self.assertEqual(data["gpu"]["requested_index"], 1)
            self.assertNotIn("/dev/nvidia0", json.dumps(data["devices"], sort_keys=True))
            record = record_plan(plan)
            self.assertEqual(record["gpu"]["requested_index"], data["gpu"]["requested_index"])
            self.assertEqual(record["gpu"]["device_uuid"], data["gpu"]["device_uuid"])
            self.assertEqual(record["gpu"]["device_minor"], 1)
            self.assertNotIn("/dev/nvidia", json.dumps(record, sort_keys=True))

            argv = render_plan(plan)
            argv[0] = os.environ.get("SUREAL_LIVE_GATE_BWRAP", argv[0])
            result = subprocess.run(argv, text=True, capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            cuda_query = json.loads((output / "cuda-query.json").read_text())
            self.assertEqual(cuda_query, {"device_count": 1, "sum": 1.0})


if __name__ == "__main__":
    unittest.main()
