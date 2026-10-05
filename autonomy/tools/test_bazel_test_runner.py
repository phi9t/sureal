import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import bazel_test_runner


class BazelTestRunnerTests(unittest.TestCase):
    def test_pytest_mode_invokes_pytest_module_instead_of_unittest_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sample").mkdir()
            (root / "sample/test_sample.py").write_text(
                "def test_function_style_case():\n"
                "    assert True\n"
            )
            (root / "pytest.py").write_text(
                "import pathlib, sys\n"
                "pathlib.Path('pytest-invocation.txt').write_text('\\n'.join(sys.argv[1:]))\n"
            )

            cwd = Path.cwd()
            try:
                with patch.object(bazel_test_runner, "PACKAGE", root):
                    result = bazel_test_runner.main(["--pytest", "sample/test_sample.py"])
            finally:
                os.chdir(cwd)

            self.assertEqual(result, 0)
            self.assertEqual(
                (root / "pytest-invocation.txt").read_text().splitlines(),
                ["-q", "sample/test_sample.py"],
            )


if __name__ == "__main__":
    unittest.main()
