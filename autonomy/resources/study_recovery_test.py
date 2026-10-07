import tempfile,unittest,json
from pathlib import Path
from resources.study_recovery import restore_curve,retain_admission,recover_checkpoint
from resources.scientific_payload import sha
class RecoveryTests(unittest.TestCase):
 def test_historical_scored_steps_survive_resuming_released_heads(self):
  case={'curve':[{'step':0,'all_class_quality_passed':False},{'step':300,'all_class_quality_passed':False}]}
  curve=restore_curve(case);self.assertEqual({v['step'] for v in curve},{0,300});curve.append({'step':500});self.assertEqual(len(case['curve']),2)
  with self.assertRaises(ValueError):restore_curve({'curve':[{'step':0},{'step':0}]})
 def test_admission_remains_readable_without_repository_mount(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);repo=root/'repo';repo.mkdir();run=root/'cache-run';run.mkdir();receipt=repo/'admission.json';receipt.write_text('{"verified":true}')
   reference=retain_admission(receipt,run);receipt.unlink();self.assertEqual(sha(reference['path']),reference['sha256']);self.assertTrue(Path(reference['path']).is_relative_to(run))
 def test_interrupted_checkpoint_rename_is_recovered_only_with_matching_hash(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'resume').mkdir();checkpoint=root/'resume/checkpoint.pt';checkpoint.write_bytes(b'unchanged model and Adam');(root/'check.json').write_text(json.dumps({'checkpoint_sha256':sha(checkpoint)}))
   self.assertTrue(recover_checkpoint(root));self.assertEqual((root/'checkpoint.pt').read_bytes(),b'unchanged model and Adam');self.assertFalse(recover_checkpoint(root))
   (root/'checkpoint.pt').unlink();checkpoint.write_bytes(b'corrupted')
   with self.assertRaises(ValueError):recover_checkpoint(root)
if __name__=='__main__':unittest.main()
