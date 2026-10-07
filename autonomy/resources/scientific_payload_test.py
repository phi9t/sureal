import os,tempfile,unittest
from pathlib import Path
from resources.scientific_payload import unique_payload_bytes,deduplicate
class StorageTests(unittest.TestCase):
 def test_hardlinks_count_once(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'a').write_bytes(b'abc');os.link(p/'a',p/'b');self.assertEqual(unique_payload_bytes(p),3)
 def test_dedup_preserves_paths_and_bytes(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'a').write_bytes(b'abc');(p/'b').write_bytes(b'abc');deduplicate([p/'a',p/'b']);self.assertEqual((p/'a').read_bytes(),(p/'b').read_bytes());self.assertEqual(unique_payload_bytes(p),3)
 def test_different_payloads_refused(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'a').write_bytes(b'abc');(p/'b').write_bytes(b'xyz')
   with self.assertRaises(ValueError):deduplicate([p/'a',p/'b'])
   self.assertEqual((p/'b').read_bytes(),b'xyz')
