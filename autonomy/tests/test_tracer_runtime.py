"""Exercise the actual bubblewrap boundary with the optional installed runtime."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
VENV = Path(os.environ.get("WAYMO_TRACER_VENV",
                         str(Path.home() / ".cache/waystone/waymo-perception/probe-venv")))


class RuntimeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("bwrap") and (VENV / "bin/python").exists(),
                         "requires bwrap and an installed tracer venv")
    def test_runtime_resolves_uv_interpreter_alias_and_enforces_network_boundary(self):
        result = subprocess.run([str(ROOT / "tracer.sh"), "verify-env"],
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("separate network namespace", result.stdout)
        self.assertIn("no GCS credential mount", result.stdout)


if __name__ == "__main__":
    unittest.main()
