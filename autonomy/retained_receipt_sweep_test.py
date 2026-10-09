import copy
import json
import tempfile
import unittest
from pathlib import Path

import retained_receipt_sweep
from evidence.source_snapshot import file_sha256
from insula.launch_plan import BAZEL_LINUX_X86_64_SHA256, BAZEL_VERSION
from insula.launch_plan import build_plan, load_runtime_lock, record_plan, render_plan
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import CURRENT_CPU_ROOTFS_NAME


AUTONOMY = Path(__file__).resolve().parent


def write_rootfs(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin/python").write_text("#!/bin/sh\n")
    (root / "bin/python").chmod(0o755)


def write_cpu_lock(path: Path, rootfs: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rootfs_sha256": rootfs_identity(rootfs),
                "dockerfile_sha256": file_sha256(AUTONOMY / "insula/Dockerfile"),
                "requirements_sha256": file_sha256(AUTONOMY / "requirements-tracer.lock"),
                "test_tools_requirements_sha256": file_sha256(
                    AUTONOMY / "insula/cpu-test-tools-requirements.lock"
                ),
                "bazel_version": BAZEL_VERSION,
                "bazel_linux_x86_64_sha256": BAZEL_LINUX_X86_64_SHA256,
            },
            sort_keys=True,
        )
        + "\n"
    )


class RetainedReceiptSweepTests(unittest.TestCase):
    def receipt_fixture(self, root: Path) -> Path:
        rootfs = root / CURRENT_CPU_ROOTFS_NAME
        write_rootfs(rootfs)
        lock = rootfs.with_name(rootfs.name + ".lock.json")
        write_cpu_lock(lock, rootfs)
        runtime = load_runtime_lock(rootfs, lock)

        code = root / "code"
        output = root / "output"
        code.mkdir()
        output.mkdir()
        (code / "worker.py").write_text("print('ok')\n")
        (output / "result.txt").write_text("ok\n")
        plan = build_plan(
            runtime,
            code=code,
            output=output,
            command=["python", "/experiment/worker.py"],
        )
        receipt = {
            "command": render_plan(plan),
            "launch_plan": record_plan(plan),
            "exit_code": 0,
            "artifacts": {"result.txt": file_sha256(output / "result.txt")},
        }
        path = output / "receipt.json"
        path.write_text(json.dumps(receipt, indent=2) + "\n")
        return path

    def test_extra_receipt_manifest_paths_are_relative_to_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt = self.receipt_fixture(root)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"receipts": [{"path": "output/receipt.json"}]}))

            self.assertEqual(
                retained_receipt_sweep._extra_receipts_from_manifest(manifest),
                [receipt],
            )

    def test_fresh_receipt_checks_artifacts_and_launch_plan_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt = self.receipt_fixture(root)

            report = retained_receipt_sweep.sweep_fresh_live_receipts([receipt], root)

            self.assertEqual(report.as_dict(), {"passed": 1, "failed": 0, "skipped": 0, "failures": [], "skips": []})

    def test_tampered_recorded_mount_digest_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt = self.receipt_fixture(root)
            tampered = copy.deepcopy(json.loads(receipt.read_text()))
            for mount in tampered["launch_plan"]["mounts"]:
                if mount["inside_path"] == "/experiment":
                    mount["digest"] = "0" * 64
                    break

            with self.assertRaisesRegex(ValueError, "mount digest differs"):
                retained_receipt_sweep._verify_recorded_mount_digests_from_command(tampered)


if __name__ == "__main__":
    unittest.main()
