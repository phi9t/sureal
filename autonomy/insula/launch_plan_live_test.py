import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from insula.launch_plan import build_plan, load_runtime_lock, render_plan
from insula.runtime_roots import current_cpu_rootfs, default_lock


AUTONOMY = Path(__file__).resolve().parents[1]


class LaunchPlanLiveTests(unittest.TestCase):
    def test_trivial_command_runs_through_current_cpu_rootfs(self):
        rootfs = Path(os.environ.get("WAYMO_INSULA_ROOT", current_cpu_rootfs())).resolve()
        lock = Path(os.environ.get("WAYMO_INSULA_LOCK", default_lock(rootfs))).resolve()
        runtime = load_runtime_lock(rootfs, lock)

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "outputs"
            output.mkdir()
            plan = build_plan(
                runtime,
                code=AUTONOMY,
                output=output,
                command=[
                    "python",
                    "-c",
                    "from pathlib import Path; Path('/outputs/launch-plan-live.txt').write_text('ok\\n')",
                ],
            )
            argv = render_plan(plan)
            argv[0] = os.environ.get("SUREAL_LIVE_GATE_BWRAP", argv[0])
            result = subprocess.run(argv, text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((output / "launch-plan-live.txt").read_text(), "ok\n")


if __name__ == "__main__":
    unittest.main()
