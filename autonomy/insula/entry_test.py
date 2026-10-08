import json
import tempfile
import unittest
from pathlib import Path
from insula.entry import launch_plan
from insula.sandbox_plan import live_gate_plan

class EntryTests(unittest.TestCase):
    def test_launch_plan_uses_the_shared_sandbox_plan(self):
        rootfs = Path("/rootfs")
        experiment = Path("/experiment")
        source = Path("/source-tree")
        output = Path("/outputs-dir")
        command = ["python", "-V"]

        self.assertEqual(
            launch_plan(rootfs, experiment, source, output, command),
            live_gate_plan(rootfs, experiment, source, output, command).argv,
        )

    def test_plan_is_offline_and_readonly(self):
        plan = launch_plan(Path('/rootfs'), Path('/experiment'), Path('/input'), Path('/output'), ['python','-V'])
        self.assertIn('--unshare-all', plan)
        self.assertIn('--clearenv', plan)
        self.assertEqual(plan[plan.index('--ro-bind')+1:plan.index('--ro-bind')+3], ['/rootfs','/'])
        self.assertNotIn('/usr', plan)
        self.assertIn('/source', plan)
        self.assertIn('/outputs', plan)

    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):
            launch_plan(Path('/rootfs'),Path('/experiment'),Path('/input'),Path('/input/out'),['true'])

if __name__ == '__main__':
    unittest.main()
