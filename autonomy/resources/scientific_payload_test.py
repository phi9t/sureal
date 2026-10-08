import os,tempfile,unittest
from pathlib import Path
from resources.scientific_payload import unique_payload_bytes,deduplicate
class StorageTests(unittest.TestCase):
 def test_hardlinks_count_once(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'a').write_bytes(b'abc');os.link(p/'a',p/'b');self.assertEqual(unique_payload_bytes(p),3)
 def test_symlink_root_is_refused(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);root=p/'root';root.mkdir();(root/'a').write_bytes(b'abc');link=p/'link';link.symlink_to(root,target_is_directory=True)
   with self.assertRaisesRegex(ValueError,'symlink'):unique_payload_bytes(link)
 def test_symlink_payload_file_is_refused(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);target=p/'target';target.write_bytes(b'abc');(p/'link').symlink_to(target)
   with self.assertRaisesRegex(ValueError,'symlink'):unique_payload_bytes(p)
 def test_dedup_preserves_paths_and_bytes(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'a').write_bytes(b'abc');(p/'b').write_bytes(b'abc');deduplicate([p/'a',p/'b']);self.assertEqual((p/'a').read_bytes(),(p/'b').read_bytes());self.assertEqual(unique_payload_bytes(p),3)
 def test_different_payloads_refused(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'a').write_bytes(b'abc');(p/'b').write_bytes(b'xyz')
   with self.assertRaises(ValueError):deduplicate([p/'a',p/'b'])
   self.assertEqual((p/'b').read_bytes(),b'xyz')
if __name__=='__main__':unittest.main()
