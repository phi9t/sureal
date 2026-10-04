import json
import tempfile
import unittest
from pathlib import Path
from pipeline.training_box_replay_audit import verify_replay_receipt

class ReplayReceiptAuditTests(unittest.TestCase):
    def test_incomplete_selection_and_missing_pass_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'receipt.json').write_text('{}')
            for sources in [[],[{'scene':'same'}]*64]:
                with self.assertRaises(ValueError):
                    verify_replay_receipt(root,expected_receipt_sha256='0'*64,
                                          expected_job={},expected_sources=sources,
                                          expected_runtime_lock={},code_root=root)
