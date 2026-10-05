import hashlib,json,tempfile,unittest
from pathlib import Path
from dataset.scientific_preparation import verified_sidecar_hashes

class ScientificPreparationTests(unittest.TestCase):
    def fixture(self,root):
        sidecar=root/'sidecars/lidar_pose';sidecar.mkdir(parents=True);evidence=root/'evidence/lidar_pose';(evidence/'checked').mkdir(parents=True)
        manifest=sidecar/'manifest.json';manifest.write_text(json.dumps({'component':'lidar_pose','scene':'scene','source_sha256':'a'*64}))
        check=evidence/'checked/check.json';check.write_text(json.dumps({'source_sha256':'a'*64,'status':'all native identities, scalars and shaped arrays reconciled'}))
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        r={'scene':'scene','component':'lidar_pose','source_sha256':'a'*64,'candidate_hashes':{'worker':'b'*64},'checks':[{'stage':'decode','exit_code':0},{'stage':'independent-check','exit_code':0}],'validation':json.loads(check.read_text()),'artifacts':{str(p.relative_to(root)):sha(p) for p in [manifest,check]}}
        receipt=evidence/'receipt.json';receipt.write_text(json.dumps(r));return manifest,check,receipt

    def test_hashes_anchored_to_successful_independent_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest,_,_=self.fixture(root)
            self.assertEqual(verified_sidecar_hashes(root,['lidar_pose'],'scene',{'worker':'b'*64}),{'lidar_pose':hashlib.sha256(manifest.read_bytes()).hexdigest()})

    def test_changed_missing_or_failed_evidence_refused(self):
        for mutation in ('manifest','checker','failure','candidate','scene','source','missing'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);manifest,check,receipt=self.fixture(root);r=json.loads(receipt.read_text())
                if mutation=='manifest':manifest.write_text('{}')
                elif mutation=='checker':check.write_text('{}')
                elif mutation=='failure':r['checks'][1]['exit_code']=1
                elif mutation=='candidate':r['candidate_hashes']={}
                elif mutation=='scene':r['scene']='different'
                elif mutation=='source':r['source_sha256']='c'*64
                elif mutation=='missing':r['artifacts'].pop(str(check.relative_to(root)))
                receipt.write_text(json.dumps(r))
                with self.assertRaises(ValueError):verified_sidecar_hashes(root,['lidar_pose'],'scene',{'worker':'b'*64})

if __name__=='__main__':unittest.main()
