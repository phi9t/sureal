import os
import unittest

import retained_receipt_sweep


class RetainedReceiptSweepHostTests(unittest.TestCase):
    def _skip_or_fail(self, message):
        if os.environ.get("SUREAL_RETAINED_RECEIPT_REQUIRE_HOST_DATA") == "1":
            self.fail(message)
        self.skipTest(message)

    def test_default_retained_receipts_verify_offline(self):
        if not retained_receipt_sweep.DEFAULT_BS122_PROGRESS.exists():
            self._skip_or_fail("balanced16 bs122 progress receipt not present")

        case_dirs = retained_receipt_sweep._case_dirs(
            retained_receipt_sweep.DEFAULT_BS122_PROGRESS
        )
        missing_case_dirs = [path for path in case_dirs if not path.exists()]
        if missing_case_dirs:
            self._skip_or_fail(
                "retained case directories are not visible from this Bazel test: "
                + ", ".join(str(path) for path in missing_case_dirs[:3])
            )

        host_cache = retained_receipt_sweep.DEFAULT_HOST_CACHE
        for path in case_dirs:
            if path.parent.name == "insula":
                host_cache = path.parent.parent
                break
        if not (host_cache / "insula").exists():
            self._skip_or_fail(f"retained host cache not visible: {host_cache}")

        report = retained_receipt_sweep.run_sweep(
            progress_path=retained_receipt_sweep.DEFAULT_BS122_PROGRESS,
            research_root=retained_receipt_sweep.DEFAULT_RECEIPT_RESEARCH,
            host_cache=host_cache,
            temp_root=retained_receipt_sweep._temp_root(os.environ.get("TEST_TMPDIR")),
        )

        failures = sum(counts["failed"] for counts in report["verifiers"].values())
        skips = sum(counts["skipped"] for counts in report["verifiers"].values())
        self.assertEqual(failures, 0, report)
        self.assertEqual(skips, 0, report)
        self.assertEqual(report["verifiers"]["balanced16_stage_check"]["passed"], 14)
        self.assertEqual(report["verifiers"]["resource_stage_proof_validation"]["passed"], 14)
        self.assertEqual(report["verifiers"]["resource_checkpoint_validation"]["passed"], 2)
        self.assertEqual(report["verifiers"]["legacy_resource_publication_validation"]["passed"], 9)
        self.assertGreater(report["verifiers"]["launch_plan_receipt_readers"]["passed"], 0)


if __name__ == "__main__":
    unittest.main()
