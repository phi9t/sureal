import json,tempfile,unittest
from pathlib import Path
from dataset.sidecar_eviction import evict_sidecars
from evidence.source_snapshot import file_sha256 as sha

class SidecarEvictionTests(unittest.TestCase):
 def fixture(self,root):
  p=root/'processing';s=p/'sidecars/lidar_pose';s.mkdir(parents=True);f=s/'row.npz';f.write_bytes(b'payload')
  u=root/'publication';(u/'packed').mkdir(parents=True);(u/'input').mkdir();a=u/'packed/sidecars.tar';a.write_bytes(b'archive')
  trusted={'files':{'lidar_pose/row.npz':sha(f)},'provenance':{'scene':'scene','scene_receipt_sha256':'abc','source_receipt_hashes':{}}}
  t=u/'input/trusted.json';t.write_text(json.dumps(trusted));m=u/'packed/publication.json';m.write_text('{}')
  r={'scene':'scene','archive_hdfs_uri':'hdfs://host/archive.tar','archive':{'sha256':sha(a)},'scene_receipt_sha256':'abc','component_receipt_hashes':{},'publication_manifest_sha256':sha(m),'validation':{'files':1,'provenance':trusted['provenance']},'checks':[{'stage':x,'exit_code':0} for x in ['pack-live','hdfs-put','hdfs-download','independent-bundle-live','manifest-put-last','manifest-download']],'artifacts':{'input/trusted.json':sha(t),'packed/publication.json':sha(m)}}
  receipt=u/'receipt.json';receipt.write_text(json.dumps(r));return p,u,f,a,sha(receipt)
 def blob_fixture(self,root):
  p,u,f,a,h=self.fixture(root);receipt=u/'receipt.json';r=json.loads(receipt.read_text())
  r.pop('archive_hdfs_uri');r['archive_blob']={'key':'datasets/component-bundles-v1/scene/scientific/archive.tar','sha256':sha(a),'bytes':a.stat().st_size,'verified_by_readback':True};r['store_descriptor']={'kind':'waystone','project':'sureal'}
  stages=['pack-live','archive-blob-put','archive-blob-fetch','independent-bundle-live','manifest-blob-put-last','manifest-blob-fetch'];r['checks']=[{'stage':x,'exit_code':0} for x in stages]
  receipt.write_text(json.dumps(r));return p,u,f,a,sha(receipt)
 def test_verified_eviction_preserves_recovery(self):
  with tempfile.TemporaryDirectory() as d:
   p,u,f,a,h=self.fixture(Path(d));r=evict_sidecars(p,u,expected_publication_sha256=h)
   self.assertFalse(f.exists());self.assertFalse(a.exists());self.assertEqual(r['bytes_evicted'],14);self.assertTrue((p/'sidecar-eviction.json').exists());self.assertTrue((u/'receipt.json').exists())
 def test_blob_publication_receipt_preserves_blob_recovery(self):
  with tempfile.TemporaryDirectory() as d:
   p,u,f,a,h=self.blob_fixture(Path(d));r=evict_sidecars(p,u,expected_publication_sha256=h)
   self.assertEqual(r['archive_blob']['key'],'datasets/component-bundles-v1/scene/scientific/archive.tar')
   self.assertNotIn('archive_hdfs_uri',r)
 def test_mutations_refuse_before_any_deletion(self):
  for kind in ['payload','archive','receipt','extra','symlink']:
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
    p,u,f,a,h=self.fixture(Path(d))
    if kind=='payload':f.write_bytes(b'bad')
    elif kind=='archive':a.write_bytes(b'bad')
    elif kind=='receipt':(u/'receipt.json').write_text('{}')
    elif kind=='extra':(f.parent/'extra').write_bytes(b'extra')
    else:f.unlink();f.symlink_to(a)
    with self.assertRaises(ValueError):evict_sidecars(p,u,expected_publication_sha256=h)
    self.assertTrue(f.exists());self.assertTrue(a.exists());self.assertFalse((p/'sidecar-eviction.json').exists())
if __name__=='__main__':unittest.main()
