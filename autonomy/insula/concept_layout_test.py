import unittest
from pathlib import Path


class InsulaConceptLayoutTests(unittest.TestCase):
    def test_live_gate_launcher_uses_the_shared_sandbox_plan(self):
        from insula.entry import launch_plan
        from insula.sandbox_plan import live_gate_plan

        rootfs = Path("/rootfs")
        experiment = Path("/experiment")
        source = Path("/source-tree")
        output = Path("/outputs-dir")
        command = ["python", "-V"]

        self.assertEqual(
            launch_plan(rootfs, experiment, source, output, command),
            live_gate_plan(rootfs, experiment, source, output, command).argv,
        )

    def test_insula_scope_modules_are_importable_from_the_concept_package(self):
        import importlib

        for module in (
            "insula.entry",
            "insula.m0_probe",
            "insula.m0_receipt",
            "insula.m0_validate",
            "insula.runtime_identity",
            "insula.sandbox_plan",
            "insula.staging_lease",
        ):
            with self.subTest(module=module):
                self.assertIsNotNone(importlib.import_module(module))

    def test_m0_receipt_uses_the_evidence_digest_helper(self):
        from insula import m0_receipt

        digest = "a" * 64
        calls = []
        original_digest = m0_receipt.file_sha256
        original_verify = m0_receipt.verify_rootfs
        try:
            m0_receipt.file_sha256 = lambda path: calls.append(Path(path)) or digest
            m0_receipt.verify_rootfs = lambda path, expected: None
            import json
            import tempfile

            with tempfile.TemporaryDirectory() as directory:
                actual_run = Path(directory) / "run"
                actual_experiment = Path(directory) / "experiment"
                actual_rootfs = Path(directory) / "rootfs"
                actual_run.mkdir()
                actual_experiment.mkdir()
                actual_rootfs.mkdir()
                files = {
                    *(str(path.relative_to(actual_experiment)) for path in m0_receipt.candidate_files(actual_experiment)),
                    "producer-0.log",
                    "validator-0.log",
                    "producer-1.log",
                    "validator-1.log",
                    "wrong-lock.log",
                    "missing-rootfs.log",
                    "failed-assertion.log",
                    "failed-command.log",
                    "run-0/matrix.npy",
                    "run-0/synthetic.parquet",
                    "run-0/synthetic.png",
                    "run-0/observed.json",
                    "run-1/matrix.npy",
                    "run-1/synthetic.parquet",
                    "run-1/synthetic.png",
                    "run-1/observed.json",
                }
                Path(str(actual_rootfs) + ".lock.json").write_text(
                    json.dumps({"rootfs_sha256": digest}) + "\n"
                )
                for relative in files:
                    base = actual_experiment if relative.startswith(("enter.sh", "verify-m0.py", "insula/")) else actual_run
                    path = base / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("PASS\n")
                (actual_run / "input").mkdir()
                (actual_run / "input/sentinel").write_text("readonly input\n")
                checks = [
                    {"name": "host_listener_positive_control", "passed": True},
                    *[
                        {"name": name, "exit_code": 0}
                        for name in ("producer-0", "validator-0", "producer-1", "validator-1")
                    ],
                    *[
                        {"name": name, "exit_code": 1}
                        for name in ("wrong-lock", "missing-rootfs", "failed-assertion", "failed-command")
                    ],
                ]
                artifacts = {
                    str(number): {
                        "matrix.npy": digest,
                        "synthetic.parquet": digest,
                        "synthetic.png": digest,
                        "observed.json": digest,
                    }
                    for number in (0, 1)
                }
                receipt = {
                    "schema_version": 1,
                    "milestone": "M0",
                    "runtime_lock": {"rootfs_sha256": digest},
                    "code_hashes": {
                        str(path.relative_to(actual_experiment)): digest
                        for path in m0_receipt.candidate_files(actual_experiment)
                    },
                    "log_hashes": {
                        name + ".log": digest
                        for name in (
                            "producer-0",
                            "validator-0",
                            "producer-1",
                            "validator-1",
                            "wrong-lock",
                            "missing-rootfs",
                            "failed-assertion",
                            "failed-command",
                        )
                    },
                    "checks": checks,
                    "artifacts": artifacts,
                }
                (actual_run / "receipt.json").write_text(json.dumps(receipt) + "\n")

                self.assertEqual(
                    m0_receipt.validate_receipt(actual_run, actual_rootfs, actual_experiment),
                    receipt,
                )
                self.assertIn(actual_run / "producer-0.log", calls)
                self.assertIn(actual_experiment / "insula/m0_receipt.py", calls)
                self.assertIn(actual_run / "run-1/observed.json", calls)
        finally:
            m0_receipt.file_sha256 = original_digest
            m0_receipt.verify_rootfs = original_verify


if __name__ == "__main__":
    unittest.main()
