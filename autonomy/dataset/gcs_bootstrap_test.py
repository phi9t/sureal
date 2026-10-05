"""Offline bootstrap checks; Google login is deliberately never exercised."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def run_script(self, script, args, root, **extra):
        env = dict(os.environ, GCS_TOOL_ROOT=str(root), **extra)
        return subprocess.run(
            ["bash", str(ROOT / script), *args], env=env,
            input="", text=True, capture_output=True, timeout=10,
        )

    def test_help_does_not_create_cache_or_auth_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "absent"
            for script in ["gcs.sh", "setup-gcs.sh"]:
                result = self.run_script(script, ["--help"], cache)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("GCS_TOOL_ROOT", result.stdout)
            self.assertFalse(cache.exists())

    def test_auth_requires_interactive_input_before_installing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "absent"
            result = self.run_script("gcs.sh", ["auth"], cache)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("terminal", result.stderr)
            self.assertFalse(cache.exists())

    def test_wizard_rejects_piped_input_before_installing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "absent"
            result = self.run_script("setup-gcs.sh", [], cache)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("terminal", result.stderr)
            self.assertFalse(cache.exists())

    def test_corrupt_cached_archive_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache with spaces"
            downloads = cache / "downloads"
            downloads.mkdir(parents=True)
            archive = downloads / "google-cloud-cli-587.0.0-linux-x86_64.tar.gz"
            archive.write_bytes(b"corrupt archive")
            result = self.run_script("gcs.sh", ["install"], cache)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("checksum", result.stderr.lower())
            self.assertFalse((cache / "sdk" / "587.0.0").exists())

    def test_existing_runtime_uses_private_config_and_clears_host_injection(self):
        # Stub only the external CLI boundary; shell isolation executes for real.
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache with spaces"
            sdk = cache / "sdk" / "587.0.0" / "google-cloud-sdk"
            (sdk / "bin").mkdir(parents=True)
            (sdk / "platform" / "bundledpythonunix" / "bin").mkdir(parents=True)
            python = sdk / "platform" / "bundledpythonunix" / "bin" / "python3"
            python.write_text("#!/bin/sh\nexit 0\n")
            python.chmod(0o755)
            (sdk / "VERSION").write_text("587.0.0\n")
            cli = sdk / "bin" / "gcloud"
            cli.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$CLOUDSDK_CONFIG" '
                '"${PYTHONPATH-unset}" "${GOOGLE_APPLICATION_CREDENTIALS-unset}" '
                '"${LD_PRELOAD-unset}" "${CLOUDSDK_PYTHON_SITEPACKAGES-unset}" '
                '"$CLOUDSDK_PYTHON" "$@"\n'
            )
            cli.chmod(0o755)
            result = self.run_script(
                "gcs.sh", ["--", "storage", "ls", "gs://one object/"], cache,
                CLOUDSDK_CONFIG="/wrong/config", PYTHONPATH="/injected",
                GOOGLE_APPLICATION_CREDENTIALS="/wrong/credentials",
                CLOUDSDK_PYTHON_SITEPACKAGES="1", VIRTUAL_ENV="/wrong/venv",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [
                str(cache / "config"), "unset", "unset", "unset", "unset", str(python),
                "storage", "ls", "gs://one object/",
            ])
            self.assertEqual((cache / "config").stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
