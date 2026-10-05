import runpy,unittest
from pathlib import Path
import torch
class TransitionWorkerGuardTests(unittest.TestCase):
 def test_cpu_refused_before_source_or_checkpoint_access(self):
  self.assertFalse(torch.cuda.is_available())
  before=sorted(str(p) for p in Path('/outputs').rglob('*'))
  with self.assertRaisesRegex(ValueError,'one native GPU'):
   runpy.run_path('/experiment/cohort/audit_sustained_transition.py',run_name='__main__')
  self.assertEqual(before,sorted(str(p) for p in Path('/outputs').rglob('*')))
if __name__=='__main__':unittest.main()
