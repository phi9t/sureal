import json,tempfile,unittest
from pathlib import Path
from evidence.artifact_lifecycle import load_release_records
class ResumeReleaseTests(unittest.TestCase):
 def test_resume_keeps_previously_admitted_release_records(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger.json';record={'path':'/cache/checkpoint-0100/heads.npz','sha256':'a'*64}
   self.assertEqual(load_release_records(p),[])
   p.write_text(json.dumps({'released_only_after_exact_replay_and_all_native_and_literal_audits':True,'released':[record]}))
   self.assertEqual(load_release_records(p),[record])
 def test_incomplete_release_evidence_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger.json';p.write_text(json.dumps({'released_only_after_exact_replay_and_all_native_and_literal_audits':False,'released':[]}))
   with self.assertRaises(ValueError):load_release_records(p)
if __name__=='__main__':unittest.main()
