import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from insula.live_gate import LiveGate, run_live_gate


class LiveGateTests(unittest.TestCase):
    def test_plan_uses_structured_mounts_and_records_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            rootfs=root/'rootfs';rootfs.mkdir()
            lock=root/'rootfs.lock.json';lock.write_text(json.dumps({'rootfs_sha256':'1'*64}))
            experiment=root/'experiment';experiment.mkdir()
            fixture=root/'fixture';fixture.mkdir()
            output=root/'output'
            records=root/'records'
            gate=LiveGate(
                label='//autonomy/example:gate_test',
                rootfs=rootfs,
                lock=lock,
                experiment=experiment,
                fixture=fixture,
                command=['python3','-m','unittest','example.gate_test','-v'],
                expected_tests=3,
            )

            def fake_run(argv, *, text, capture_output, timeout):
                self.assertEqual(argv[0],'bwrap')
                self.assertIn(str(rootfs.resolve()),argv)
                self.assertIn(str(fixture.resolve()),argv)
                class Result:
                    returncode=0
                    stdout='Ran 3 tests in 0.001s\n\nOK\n'
                    stderr=''
                return Result()

            with patch('insula.live_gate.subprocess.run',side_effect=fake_run):
                receipt=run_live_gate(gate,records,output=output,timeout=10)

            self.assertEqual(receipt['verdict'],'pass')
            self.assertEqual(receipt['executed_tests'],3)
            self.assertEqual(receipt['label'],'//autonomy/example:gate_test')
            self.assertEqual(receipt['fixture'],str(fixture.resolve()))
            self.assertTrue(Path(receipt['raw_log']).is_file())
            self.assertTrue((records/'autonomy_example__gate_test.json').is_file())


if __name__ == '__main__':
    unittest.main()
