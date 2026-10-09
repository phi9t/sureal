import json,tempfile,unittest
from pathlib import Path
from dataset.verified_eviction import evict_points
from evidence.source_snapshot import file_sha256

class VerifiedEvictionTests(unittest.TestCase):
    def fixture(self,root):
        processing=root/'processing';points=processing/'points';points.mkdir(parents=True);publication=root/'publication';(publication/'packed').mkdir(parents=True);replay=root/'replay';replay.mkdir()
        payload=points/'scene-10-1-1.npz';payload.write_bytes(b'payload');archive=publication/'packed/scene.tar';archive.write_bytes(b'archive')
        sha=lambda p:file_sha256(p)
        report=points/'report.json';report.write_text(json.dumps({'scene':'scene','rows':[{'artifact':payload.name,'sha256':sha(payload),'return_present':True}]}))
        pub={'scene':'scene','archive_hdfs_uri':'hdfs://host/scene.tar','archive':{'sha256':sha(archive),'report_sha256':sha(report)},'checks':[{'exit_code':0}]};pp=publication/'receipt.json';pp.write_text(json.dumps(pub))
        rr={'scene':'scene','publication_receipt_sha256':sha(pp),'checks':[{'exit_code':0},{'exit_code':0}],'validation':{'records':1}};rp=replay/'receipt.json';rp.write_text(json.dumps(rr))
        return processing,publication,replay,sha(pp),sha(rp),payload,archive

    def blob_fixture(self,root):
        processing,publication,replay,_,_,payload,archive=self.fixture(root)
        pp=publication/'receipt.json';pub=json.loads(pp.read_text())
        pub.pop('archive_hdfs_uri')
        pub['archive_blob']={'key':'datasets/scene-records-v1/scene/scientific/archive.tar','sha256':file_sha256(archive),'bytes':archive.stat().st_size,'verified_by_readback':True}
        pub['store_descriptor']={'kind':'waystone','project':'sureal'}
        pp.write_text(json.dumps(pub))
        rp=replay/'receipt.json';rr=json.loads(rp.read_text());rr['publication_receipt_sha256']=file_sha256(pp);rp.write_text(json.dumps(rr))
        return processing,publication,replay,file_sha256(pp),file_sha256(rp),payload,archive

    def test_verified_payloads_evicted_and_recovery_manifest_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,u,r,ph,rh,payload,archive=self.fixture(Path(tmp));result=evict_points(p,u,r,expected_publication_sha256=ph,expected_replay_sha256=rh)
            self.assertFalse(payload.exists());self.assertFalse(archive.exists());self.assertTrue((p/'points/report.json').exists());self.assertEqual(result['bytes_evicted'],14);self.assertEqual(result['archive_hdfs_uri'],'hdfs://host/scene.tar');self.assertTrue((p/'point-eviction.json').exists())

    def test_blob_publication_receipt_preserves_blob_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,u,r,ph,rh,payload,archive=self.blob_fixture(Path(tmp));result=evict_points(p,u,r,expected_publication_sha256=ph,expected_replay_sha256=rh)
            self.assertEqual(result['archive_blob']['key'],'datasets/scene-records-v1/scene/scientific/archive.tar')
            self.assertNotIn('archive_hdfs_uri',result)

    def test_changed_payload_archive_or_receipt_refused_before_any_deletion(self):
        for mutation in ('payload','archive','receipt'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                p,u,r,ph,rh,payload,archive=self.fixture(Path(tmp))
                if mutation=='payload':payload.write_bytes(b'changed')
                elif mutation=='archive':archive.write_bytes(b'changed')
                else:(r/'receipt.json').write_text('{}')
                with self.assertRaises(ValueError):evict_points(p,u,r,expected_publication_sha256=ph,expected_replay_sha256=rh)
                self.assertTrue(payload.exists());self.assertTrue(archive.exists());self.assertFalse((p/'point-eviction.json').exists())

if __name__=='__main__':unittest.main()
