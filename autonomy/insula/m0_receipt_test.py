"""Tamper checks against real recorded evidence (no runtime mocking)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from insula.m0_receipt import receipt_fixture_paths, validate_receipt

HERE=Path(__file__).resolve().parents[1]
ROOT,EVIDENCE=receipt_fixture_paths(os.environ)

class ReceiptTests(unittest.TestCase):
    def test_receipt_fixture_paths_accept_live_gate_environment(self):
        root,evidence=receipt_fixture_paths({
            'WAYMO_INSULA_ROOT':'/tmp/current-rootfs',
            'WAYMO_M0_RECEIPT':'/tmp/current-receipt',
        })
        self.assertEqual(root,Path('/tmp/current-rootfs'))
        self.assertEqual(evidence,Path('/tmp/current-receipt'))

    def test_valid_live_receipt(self):
        validate_receipt(EVIDENCE,ROOT,HERE)

    def test_tampered_log(self):
        self.check_mutation(lambda r,p:(p/'producer-0.log').write_text('PASS forged'))

    def check_mutation(self, mutate):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';shutil.copytree(EVIDENCE,run)
            r=json.loads((run/'receipt.json').read_text());mutate(r,run)
            (run/'receipt.json').write_text(json.dumps(r))
            with self.assertRaises(ValueError):validate_receipt(run,ROOT,HERE)

    def test_empty_candidate_inventory(self):
        self.check_mutation(lambda r,p:r.update(code_hashes={}))

    def test_missing_assertion(self):
        self.check_mutation(lambda r,p:r['checks'].pop())

    def test_tampered_artifact(self):
        self.check_mutation(lambda r,p:(p/'run-0/matrix.npy').write_bytes(b'wrong'))

    def test_omitted_expected_artifact(self):
        self.check_mutation(lambda r,p:r['artifacts']['0'].pop('matrix.npy'))

if __name__ == '__main__':
    unittest.main()
