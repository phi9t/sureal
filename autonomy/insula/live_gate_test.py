import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidence.source_snapshot import file_sha256
from insula.launch_plan import BAZEL_LINUX_X86_64_SHA256, BAZEL_VERSION
from insula.live_gate import LiveGate, run_live_gate
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import CURRENT_CPU_ROOTFS_NAME


AUTONOMY = Path(__file__).resolve().parents[1]


class LiveGateTests(unittest.TestCase):
    def test_plan_uses_structured_mounts_and_records_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            rootfs=root/CURRENT_CPU_ROOTFS_NAME;rootfs.mkdir()
            lock=rootfs.with_name(rootfs.name+'.lock.json')
            lock.write_text(json.dumps({
                'schema_version':1,
                'rootfs_sha256':rootfs_identity(rootfs),
                'dockerfile_sha256':file_sha256(AUTONOMY/'insula/Dockerfile'),
                'requirements_sha256':file_sha256(AUTONOMY/'requirements-tracer.lock'),
                'test_tools_requirements_sha256':file_sha256(AUTONOMY/'insula/cpu-test-tools-requirements.lock'),
                'bazel_version':BAZEL_VERSION,
                'bazel_linux_x86_64_sha256':BAZEL_LINUX_X86_64_SHA256,
            }))
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
            self.assertNotIn('argv',receipt)
            self.assertNotIn('mounts',receipt)
            self.assertIn('launch_plan',receipt)
            self.assertEqual(receipt['launch_plan']['command'],gate.command)
            raw_plan=json.dumps(receipt['launch_plan'],sort_keys=True)
            self.assertNotIn(str(root),raw_plan)
            mounts={mount['role']:mount for mount in receipt['launch_plan']['mounts']}
            self.assertEqual(mounts['code']['inside_path'],'/experiment')
            self.assertEqual(mounts['source']['inside_path'],'/source')
            self.assertTrue(Path(receipt['raw_log']).is_file())
            self.assertTrue((records/'autonomy_example__gate_test.json').is_file())


if __name__ == '__main__':
    unittest.main()
