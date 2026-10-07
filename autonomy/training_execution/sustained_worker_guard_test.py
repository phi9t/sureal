import runpy,unittest
from pathlib import Path
import torch

class SustainedWorkerGuardTests(unittest.TestCase):
 def test_cpu_runtime_refused_before_inputs_or_outputs(self):
  self.assertFalse(torch.cuda.is_available())
  before=sorted(str(p) for p in Path('/outputs').rglob('*'))
  for worker in ['train_sustained.py','replay_sustained.py']:
   with self.assertRaisesRegex(ValueError,'one native GPU'):
    runpy.run_path(str(Path(__file__).with_name(worker)),run_name='__main__')
  self.assertEqual(before,sorted(str(p) for p in Path('/outputs').rglob('*')))

if __name__=='__main__':unittest.main()
