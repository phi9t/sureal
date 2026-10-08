import hashlib,json,tarfile,tempfile,unittest
from pathlib import Path
from evidence.source_snapshot import file_sha256
from resources.resource_archive import create_archive,verify_archive

class ArchiveContract(unittest.TestCase):
 def test_roundtrip_manifest_and_deterministic_bytes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'source';root.mkdir();(root/'checkpoint.pt').write_bytes(bytes(range(256))*64);(root/'check.json').write_text('{"steps":750}')
   a,b=Path(d)/'a.tar.gz',Path(d)/'b.tar.gz'
   one=create_archive(root,['checkpoint.pt','check.json'],a);two=create_archive(root,['check.json','checkpoint.pt'],b)
   self.assertEqual(a.read_bytes(),b.read_bytes());self.assertEqual(one,two);self.assertTrue(verify_archive(a,one)['exact_members_and_hashes'])
   self.assertEqual([x['path'] for x in one['members']],['check.json','checkpoint.pt'])
 def test_traversal_and_symlinks_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'source';root.mkdir();(Path(d)/'secret').write_text('must stay outside');(root/'link').symlink_to(Path(d)/'secret')
   for paths in [['../secret'],['/secret'],['link'],['a/../secret'],['missing'],['a','a']]:
    with self.assertRaises(ValueError):create_archive(root,paths,Path(d)/'bad.tar.gz')
 def test_tampered_manifest_and_payload_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'source';root.mkdir();(root/'checkpoint.pt').write_bytes(b'original');archive=Path(d)/'a.tar.gz';manifest=create_archive(root,['checkpoint.pt'],archive)
   bad=json.loads(json.dumps(manifest));bad['members'][0]['sha256']='0'*64
   with self.assertRaises(ValueError):verify_archive(archive,bad)
   archive.write_bytes(archive.read_bytes()[:-3]+b'bad')
   with self.assertRaises(ValueError):verify_archive(archive,manifest)
 def test_duplicate_or_link_tar_members_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/'bad.tar'
   with tarfile.open(a,'w') as tar:
    m=tarfile.TarInfo('checkpoint.pt');m.type=tarfile.SYMTYPE;m.linkname='/etc/passwd';tar.addfile(m)
   manifest={'archive_sha256':file_sha256(a),'archive_bytes':a.stat().st_size,'members':[{'path':'checkpoint.pt','bytes':0,'sha256':hashlib.sha256(b'').hexdigest()}]}
   with self.assertRaises(ValueError):verify_archive(a,manifest)
 def test_admission_bounds_are_enforced(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'source';root.mkdir();(root/'checkpoint.pt').write_bytes(b'x'*20)
   with self.assertRaises(ValueError):create_archive(root,['checkpoint.pt'],Path(d)/'a.tar.gz',max_bytes=10)

if __name__ == "__main__":
 unittest.main()
