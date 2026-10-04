import json
import tempfile
import unittest
from pathlib import Path
from pipeline.insula_entry import launch_plan

class EntryTests(unittest.TestCase):
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
