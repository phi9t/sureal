"""Guard: no Waymo-derived payloads or generated trees may be tracked under the viewer."""
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORBIDDEN_SUFFIXES = (".jpg", ".jpeg", ".png", ".wpc", ".parquet", ".ply", ".log")
FORBIDDEN_PARTS = ("node_modules", "dist", ".venv", "tmp", "__pycache__", "bundles")


class RepoHygieneTest(unittest.TestCase):
    def test_no_payloads_or_generated_files_tracked(self):
        try:
            out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", str(HERE)],
                                 cwd=HERE, check=True, capture_output=True, text=True).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git unavailable")
        for line in out.splitlines():
            p = Path(line)
            self.assertFalse(p.suffix.lower() in FORBIDDEN_SUFFIXES, line)
            self.assertFalse(any(part in FORBIDDEN_PARTS for part in p.parts), line)


if __name__ == "__main__":
    unittest.main()
