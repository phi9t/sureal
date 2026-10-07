import json,tempfile,unittest
from pathlib import Path
from camera.camera_eviction import evict_camera
from evidence.source_snapshot import file_sha256
class CameraEvictionTests(unittest.TestCase):
 def fixture(self,root):
  processing=root/'processing';source=processing/'sidecars/camera_image';source.mkdir(parents=True);payload=source/'row.bin';payload.write_bytes(b'jpeg');publication=root/'publication';(publication/'packed').mkdir(parents=True);(publication/'input').mkdir();archive=publication/'packed/camera.tar';archive.write_bytes(b'archive');replay=root/'replay';replay.mkdir()
  sha=lambda p:file_sha256(p)
  trusted={'files':{'camera_image/row.bin':sha(payload)},'provenance':{'scene':'scene'}};t=publication/'input/trusted.json';t.write_text(json.dumps(trusted))
  pub={'scene':'scene','checks':[{'stage':s,'exit_code':0} for s in ['pack-live','hdfs-put','hdfs-download','independent-bundle-live','manifest-put-last','manifest-download']],'archive_hdfs_uri':'hdfs://host/camera.tar','archive':{'sha256':sha(archive)},'artifacts':{'input/trusted.json':sha(t)},'validation':{'files':1,'provenance':trusted['provenance']}};p=publication/'receipt.json';p.write_text(json.dumps(pub))
  rr={'scene':'scene','publication_receipt_sha256':sha(p),'checks':[{'exit_code':0},{'exit_code':0}]};r=replay/'receipt.json';r.write_text(json.dumps(rr));return processing,publication,replay,sha(p),sha(r),payload,archive
 def test_recovery_first_eviction_and_receipt_preservation(self):
  with tempfile.TemporaryDirectory() as tmp:
   p,u,r,ph,rh,f,a=self.fixture(Path(tmp));out=evict_camera(p,u,r,expected_publication_sha256=ph,expected_replay_sha256=rh);self.assertFalse(f.exists());self.assertFalse(a.exists());self.assertEqual(out['bytes_evicted'],11);self.assertTrue((p/'camera-eviction.json').exists());self.assertTrue((r/'receipt.json').exists())
 def test_replay_payload_archive_extra_and_symlink_refuse_before_deletion(self):
  for kind in ['replay','payload','archive','extra','symlink']:
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
    p,u,r,ph,rh,f,a=self.fixture(Path(tmp))
    if kind=='replay':(r/'receipt.json').write_text('{}')
    elif kind=='payload':f.write_bytes(b'bad')
    elif kind=='archive':a.write_bytes(b'bad')
    elif kind=='extra':(f.parent/'extra').write_bytes(b'bad')
    else:f.unlink();f.symlink_to(a)
    with self.assertRaises(ValueError):evict_camera(p,u,r,expected_publication_sha256=ph,expected_replay_sha256=rh)
    self.assertTrue(f.exists());self.assertTrue(a.exists());self.assertFalse((p/'camera-eviction.json').exists())
if __name__=='__main__':unittest.main()
