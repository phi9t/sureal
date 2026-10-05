import json,tempfile,unittest
from pathlib import Path
from evidence.journal import append_entry,read_entries
class JournalTests(unittest.TestCase):
 def test_evidence_hashes_and_history_are_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);evidence=root/'proof.json';evidence.write_text('{"passed":true}');journal=root/'journal.jsonl'
   one=append_entry(journal,'observation',['tier1/baseline'],'Native overfit verified',[evidence]);two=append_entry(journal,'hypothesis',['tier1/baseline'],'Background imbalance may slow fitting',[])
   self.assertEqual(two['previous_hash'],one['sha256']);self.assertEqual(len(read_entries(journal)),2);self.assertEqual(one['evidence'][0]['path'],str(evidence.resolve()));self.assertEqual(len(one['evidence'][0]['sha256']),64)
 def test_tampering_and_missing_evidence_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   journal=Path(d)/'journal.jsonl'
   with self.assertRaises(ValueError):append_entry(journal,'observation',['a'],'Unproven',[Path(d)/'missing'])
   proof=Path(d)/'proof.json';proof.write_text('{"passed":true}')
   link=Path(d)/'proof-link.json';link.symlink_to(proof)
   with self.assertRaisesRegex(ValueError,'regular non-symlinked file required'):
    append_entry(journal,'observation',['a'],'Symlink proof',[link])
   append_entry(journal,'decision',['a'],'Keep all ground truth',[]);journal.write_text(journal.read_text().replace('Keep all ground truth','Drop ground truth'))
   with self.assertRaises(ValueError):read_entries(journal)
 def test_evidence_survives_source_replacement(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);proof=root/'proof.json';proof.write_bytes(b'original evidence');journal=root/'journal.jsonl';entry=append_entry(journal,'observation',['a'],'Original claim',[proof]);snapshot=root/'journal-evidence'/entry['evidence'][0]['sha256'];proof.write_bytes(b'later evidence')
   self.assertEqual(snapshot.read_bytes(),b'original evidence');self.assertEqual(read_entries(journal)[0],entry)
 def test_corrupt_existing_snapshot_refuses_append(self):
  with tempfile.TemporaryDirectory() as d:
   import hashlib
   root=Path(d);proof=root/'proof.json';proof.write_bytes(b'evidence');journal=root/'journal.jsonl';snapshots=root/'journal-evidence';snapshots.mkdir();(snapshots/hashlib.sha256(proof.read_bytes()).hexdigest()).write_bytes(b'corrupted')
   with self.assertRaises(ValueError):append_entry(journal,'observation',['a'],'Must not cite corrupted snapshot',[proof])
   self.assertFalse(journal.exists())
 def test_unknown_entry_category_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):append_entry(Path(d)/'journal.jsonl','conclusion',['a'],'x',[])
if __name__=='__main__':unittest.main()
