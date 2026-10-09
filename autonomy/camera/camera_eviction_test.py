import json,sys,tempfile,unittest
from pathlib import Path
from blob_store.core import WaystoneBlobAdapter
from camera.camera_eviction import evict_camera
from evidence.source_snapshot import file_sha256
class CameraEvictionTests(unittest.TestCase):
 def fixture(self,root,*,legacy=False):
  processing=root/'processing';source=processing/'sidecars/camera_image';source.mkdir(parents=True);payload=source/'row.bin';payload.write_bytes(b'jpeg');publication=root/'publication';(publication/'packed').mkdir(parents=True);(publication/'input').mkdir();archive=publication/'packed/camera.tar';archive.write_bytes(b'archive');replay=root/'replay';replay.mkdir()
  sha=lambda p:file_sha256(p)
  trusted={'files':{'camera_image/row.bin':sha(payload)},'provenance':{'scene':'scene'}};t=publication/'input/trusted.json';t.write_text(json.dumps(trusted))
  old_checks=['pack-live','hdfs-put','hdfs-download','independent-bundle-live','manifest-put-last','manifest-download']
  blob={'key':'runs/scientific-camera/scene/archive/camera.tar','sha256':sha(archive),'bytes':len(b'archive'),'verified_by_readback':True}
  blob_fields={'blob_key':blob['key'],'sha256':blob['sha256'],'bytes':blob['bytes'],'verified_by_readback':True}
  checks=[{'stage':s,'exit_code':0} for s in old_checks] if legacy else [
   {'stage':'pack-live','exit_code':0},
   dict({'stage':'archive-blob-put'},**blob_fields),
   dict({'stage':'archive-blob-download'},**blob_fields),
   {'stage':'independent-bundle-live','exit_code':0},
   dict({'stage':'manifest-blob-put-last'},**blob_fields),
   dict({'stage':'manifest-blob-download'},**blob_fields),
  ]
  pub={'scene':'scene','checks':checks,'archive':{'sha256':sha(archive)},'artifacts':{'input/trusted.json':sha(t)},'validation':{'files':1,'provenance':trusted['provenance']}}
  if legacy:
   pub['archive_hdfs_uri']='hdfs://fixture/root/sureal/runs/scientific-camera/scene/archive/camera.tar'
   pub['store_descriptor']={'kind':'waystone','project':'sureal'}
  else:
   pub['archive_blob']=blob
   pub['store_descriptor']={'kind':'waystone','project':'sureal'}
  p=publication/'receipt.json';p.write_text(json.dumps(pub))
  rr={'scene':'scene','publication_receipt_sha256':sha(p),'checks':[{'exit_code':0},{'exit_code':0}]};r=replay/'receipt.json';r.write_text(json.dumps(rr));return processing,publication,replay,sha(p),sha(r),payload,archive
 def test_recovery_first_eviction_and_receipt_preservation(self):
  with tempfile.TemporaryDirectory() as tmp:
   p,u,r,ph,rh,f,a=self.fixture(Path(tmp));out=evict_camera(p,u,r,expected_publication_sha256=ph,expected_replay_sha256=rh);self.assertFalse(f.exists());self.assertFalse(a.exists());self.assertEqual(out['bytes_evicted'],11);self.assertEqual(out['archive_blob_key'],'runs/scientific-camera/scene/archive/camera.tar');self.assertTrue((p/'camera-eviction.json').exists());self.assertTrue((r/'receipt.json').exists())
 def test_legacy_publication_uri_resolves_to_blob_key(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p,u,r,ph,rh,f,a=self.fixture(root,legacy=True)
   tool=root/'waystone';tool.write_text('not executed')
   resolver=WaystoneBlobAdapter(project='sureal',command_prefix=[str(tool)],
                                tool_pins={str(tool):file_sha256(tool)})
   resolver._layout={'project':'sureal','storage_root':'hdfs://fixture/root',
                     'project_root':'hdfs://fixture/root/sureal'}
   out=evict_camera(p,u,r,expected_publication_sha256=ph,expected_replay_sha256=rh,
                    blob_adapter=resolver)
   self.assertEqual(out['archive_blob_key'],'runs/scientific-camera/scene/archive/camera.tar')
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
