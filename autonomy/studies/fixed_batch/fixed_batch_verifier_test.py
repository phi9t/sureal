import json
import tempfile
import unittest
from pathlib import Path

from evidence.source_snapshot import file_sha256
from studies.fixed_batch.fixed_batch_verifier import verify


def score_record(include_ap=True):
    rows = {}
    for key in ["1", "2", "3", "4"]:
        rows[key] = {"APH": 0.9}
        if include_ap:
            rows[key]["AP"] = 0.9
    return rows


class FixedBatchVerifierTests(unittest.TestCase):
    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return str(path)

    def receipt(self, root, metadata_sha, name, validation):
        path = root / f"{name}.json"
        self.write_json(
            path,
            {
                "name": name,
                "metadata_sha256": metadata_sha,
                "exit_code": 0,
                "elapsed_seconds": 1,
                "artifacts": {},
                "validation": validation,
            },
        )
        return {"receipt": str(path), "sha256": file_sha256(path)}

    def write_result_fixture(self, root, scores):
        cache = root / "cache"
        run = cache / "insula" / "fixed"
        source = run / "source"
        output = run / "baseline" / "training-output"
        (cache / "scientific-processing").mkdir(parents=True)
        checkpoint = output / "checkpoint.pt"
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_text("checkpoint")
        meta = {"source_sha256": {}, "matrix": {"baseline": {"architecture": "baseline"}}}
        run_json = run / "run.json"
        self.write_json(run_json, meta)
        metadata_sha = file_sha256(run_json)
        curve = [
            {"step": 0, "LEVEL2_per_class": scores, "all_class_quality_passed": True, "cumulative_train_seconds": 0},
            {"step": 1000, "LEVEL2_per_class": scores, "all_class_quality_passed": True, "cumulative_train_seconds": 10},
        ]
        self.write_json(
            output / "check.json",
            {
                "checkpoint_sha256": file_sha256(checkpoint),
                "case": meta["matrix"]["baseline"],
                "updates": 1000,
                "checkpoint_curve": curve,
                "parameters": {"learning_rate": 0.01},
                "cumulative_train_seconds": 10,
                "clipped_steps": [],
            },
        )
        release = run / "baseline" / "snapshot-release.json"
        self.write_json(release, {"released": []})
        receipts = [
            self.receipt(root, metadata_sha, "baseline-score-0", {"LEVEL2_per_class": scores}),
            self.receipt(root, metadata_sha, "baseline-score-1000", {"LEVEL2_per_class": scores}),
            self.receipt(root, metadata_sha, "baseline-metric-audit-0", {"native_metric_replay_exact": True, "all_export_fields_independently_reread": True}),
            self.receipt(root, metadata_sha, "baseline-metric-audit-1000", {"native_metric_replay_exact": True, "all_export_fields_independently_reread": True}),
            self.receipt(root, metadata_sha, "baseline-proposal-audit-0", {"literal_score_first_decode_nms_and_measurement_metadata": True, "all_native_eligible_GT_retained": True, "eligible_groundtruth": 73}),
            self.receipt(root, metadata_sha, "baseline-proposal-audit-1000", {"literal_score_first_decode_nms_and_measurement_metadata": True, "all_native_eligible_GT_retained": True, "eligible_groundtruth": 73}),
            self.receipt(root, metadata_sha, "baseline-loss-1000", {"literal_checkpoint_losses": 2}),
            self.receipt(root, metadata_sha, "baseline-replay-1000", {"exact_terminal_model_and_adam": True, "exact_all_checkpoint_heads": True, "exact_rng": True}),
        ]
        result = {
            "run_directory": str(run),
            "metadata_sha256": metadata_sha,
            "finished": True,
            "cases": {
                "baseline": {
                    "status": "sustained native overfit",
                    "updates": 1000,
                    "curve": curve,
                    "snapshot_release_sha256": file_sha256(release),
                    "verification_receipts": receipts,
                    "output_directory": str(output),
                    "parameters": {"learning_rate": 0.01},
                    "cumulative_train_seconds": 10,
                    "clipped_steps": [],
                }
            },
        }
        result_path = root / "result.json"
        self.write_json(result_path, result)
        return result_path

    def test_verifier_rejects_score_record_missing_ap(self):
        with tempfile.TemporaryDirectory() as directory:
            result_path = self.write_result_fixture(Path(directory), score_record(include_ap=False))

            with self.assertRaises((AssertionError, ValueError)):
                verify(result_path)


if __name__ == "__main__":
    unittest.main()
