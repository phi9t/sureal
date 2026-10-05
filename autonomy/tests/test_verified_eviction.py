import hashlib,json,tempfile,unittest
from pathlib import Path
from pipeline.verified_eviction import evict_points

class VerifiedEvictionTests(unittest.TestCase):
    def fixture(self,root):
        processing=root/'processing';points=processing/'points';points.mkdir(parents=True);publication=root/'publication';(publication/'packed').mkdir(parents=True);replay=root/'replay';replay.mkdir()
        payload=points/'scene-10-1-1.npz';payload.write_bytes(b'payload');archive=publication/'packed/scene.tar';archive.write_bytes(b'archive')
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        report=points/'report.json';report.write_text(json.dumps({'scene':'scene','rows':[{'artifact':payload.name,'sha256':sha(payload),'return_present':True}]}))
        pub={'scene':'scene','archive_hdfs_uri':'hdfs://host/scene.tar','archive':{'sha256':sha(archive),'report_sha256':sha(report)},'checks':[{'exit_code':0}]};pp=publication/'receipt.json';pp.write_text(json.dumps(pub))
        rr={'scene':'scene','publication_receipt_sha256':sha(pp),'checks':[{'exit_code':0},{'exit_code':0}],'validation':{'records':1}};rp=replay/'receipt.json';rp.write_text(json.dumps(rr))
        return processing,publication,replay,sha(pp),sha(rp),payload,archive

    def test_verified_payloads_evicted_and_recovery_manifest_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,u,r,ph,rh,payload,archive=self.fixture(Path(tmp));result=evict_points(p,u,r,expected_publication_sha256=ph,expected_replay_sha256=rh)
            self.assertFalse(payload.exists());self.assertFalse(archive.exists());self.assertTrue((p/'points/report.json').exists());self.assertEqual(result['bytes_evicted'],14);self.assertEqual(result['archive_hdfs_uri'],'hdfs://host/scene.tar');self.assertTrue((p/'point-eviction.json').exists())

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
