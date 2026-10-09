import json,tempfile,unittest
from pathlib import Path
from training_execution.sustained_stage_inputs import freeze_inputs,bind_stage_paths
class StageInputTests(unittest.TestCase):
 def test_old_stage_replay_keeps_original_target_and_audit(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=root/'source';source.mkdir();(source/'manifest.json').write_text('{}');(source/'job.json').write_text('{"target_step":0}')
   first,hashes=freeze_inputs(source,root/'first')
   (source/'job.json').write_text('{"target_step":35}');(source/'audit.json').write_text('{"pilot_reference":true}')
   final,_=freeze_inputs(source,root/'final')
   self.assertEqual(json.loads((first/'job.json').read_text())['target_step'],0);self.assertEqual(json.loads((final/'job.json').read_text())['target_step'],35);self.assertFalse((first/'audit.json').exists());self.assertEqual(set(hashes),{str(first/'manifest.json'),str(first/'job.json')})
   with self.assertRaises(FileExistsError):freeze_inputs(source,root/'first')
 def test_receipt_alias_binds_frozen_bytes_after_template_changes(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=root/'input';source.mkdir();(source/'manifest.json').write_text('{}');(source/'expected.json').write_text('original');frozen,_=freeze_inputs(source,root/'frozen');(source/'expected.json').write_text('later')
   inputs=bind_stage_paths({'/tmp/expected.json':source/'expected.json','/tmp/root':'/unrelated/root'},source,frozen)
   self.assertEqual(Path(inputs['/tmp/expected.json']).read_text(),'original');self.assertEqual(inputs['/tmp/root'],Path('/unrelated/root'))
 def test_symlinked_or_missing_manifest_refused_before_copy(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=root/'source';source.mkdir()
   with self.assertRaises(ValueError):freeze_inputs(source,root/'out')
   (root/'manifest').write_text('{}');(source/'manifest.json').symlink_to(root/'manifest')
   with self.assertRaises(ValueError):freeze_inputs(source,root/'out')
   self.assertFalse((root/'out').exists())
if __name__=='__main__':unittest.main()
