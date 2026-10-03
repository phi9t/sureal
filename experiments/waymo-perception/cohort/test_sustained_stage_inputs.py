import json,tempfile,unittest
from pathlib import Path
from cohort.sustained_stage_inputs import freeze_inputs
class StageInputTests(unittest.TestCase):
 def test_old_stage_replay_keeps_original_target_and_audit(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=root/'source';source.mkdir();(source/'manifest.json').write_text('{}');(source/'job.json').write_text('{"target_step":0}')
   first,hashes=freeze_inputs(source,root/'first')
   (source/'job.json').write_text('{"target_step":35}');(source/'audit.json').write_text('{"pilot_reference":true}')
   final,_=freeze_inputs(source,root/'final')
   self.assertEqual(json.loads((first/'job.json').read_text())['target_step'],0);self.assertEqual(json.loads((final/'job.json').read_text())['target_step'],35);self.assertFalse((first/'audit.json').exists());self.assertEqual(set(hashes),{str(first/'manifest.json'),str(first/'job.json')})
   with self.assertRaises(FileExistsError):freeze_inputs(source,root/'first')
 def test_symlinked_or_missing_manifest_refused_before_copy(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=root/'source';source.mkdir()
   with self.assertRaises(ValueError):freeze_inputs(source,root/'out')
   (root/'manifest').write_text('{}');(source/'manifest.json').symlink_to(root/'manifest')
   with self.assertRaises(ValueError):freeze_inputs(source,root/'out')
   self.assertFalse((root/'out').exists())
if __name__=='__main__':unittest.main()
