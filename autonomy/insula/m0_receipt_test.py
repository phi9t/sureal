"""Tamper checks against real recorded evidence (no runtime mocking)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from insula.m0_receipt import validate_receipt

HERE=Path(__file__).resolve().parents[1]
ROOT=Path.home()/'.cache/waystone/waymo-perception/insula/rootfs-v2'
EVIDENCE=ROOT.parent/'m0-live-20260930-c'

class ReceiptTests(unittest.TestCase):
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
