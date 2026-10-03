import tempfile,unittest
from pathlib import Path
from cohort.checkpoint_retention_policy import checkpoint_case
class CheckpointRetentionPolicyTests(unittest.TestCase):
 def test_exact_scientific_case_step_directory(self):
  with tempfile.TemporaryDirectory() as temp:
   w=Path(temp)
   for step in [0,789,1000,32000]:
    root=w/'balanced16-sustained-baseline-run1'/f'update-{step:02d}';root.mkdir(parents=True,exist_ok=True);self.assertEqual(checkpoint_case(w,root,step),'balanced16-sustained-baseline-run1')
 def test_time_censored_checkpoint_keeps_original_requested_output_path(self):
  with tempfile.TemporaryDirectory() as temp:
   w=Path(temp);root=w/'balanced16-sustained-case/update-1000';root.mkdir(parents=True)
   self.assertEqual(checkpoint_case(w,root,789,requested_step=1000),'balanced16-sustained-case')
   with self.assertRaises(ValueError):checkpoint_case(w,root,1001,requested_step=1000)
 def test_foreign_nested_mismatched_and_boolean_step_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   w=Path(temp)
   for root,step in [(w/'historical-case/update-1000',1000),(w/'balanced16-sustained-case/deeper/update-1000',1000),(w/'balanced16-sustained-case/update-1000',2000),(w/'balanced16-sustained-case/update-True',True),(w/'balanced16-sustained-case/update-32001',32001),(w/'balanced16-sustained-../update-1000',1000)]:
    root.mkdir(parents=True,exist_ok=True)
    with self.assertRaises(ValueError):checkpoint_case(w,root,step)
 def test_symlinked_case_or_checkpoint_refused(self):
  with tempfile.TemporaryDirectory() as temp:
   w=Path(temp);case=w/'balanced16-sustained-case';case.mkdir();real=w/'real';real.mkdir();(case/'update-1000').symlink_to(real,target_is_directory=True)
   with self.assertRaises(ValueError):checkpoint_case(w,case/'update-1000',1000)
   linked=w/'balanced16-sustained-linked';linked.symlink_to(case,target_is_directory=True)
   with self.assertRaises(ValueError):checkpoint_case(w,linked/'update-1000',1000)
if __name__=='__main__':unittest.main()
