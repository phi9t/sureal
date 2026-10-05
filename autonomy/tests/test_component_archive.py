import hashlib,json,tempfile,unittest
from pathlib import Path
from pipeline.component_archive import create_component_archive
from pipeline.component_archive_validate import validate_component_archive

class ComponentArchiveTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'sidecars';(source/'lidar_pose').mkdir(parents=True)
        (source/'lidar_pose/manifest.json').write_text('{}');(source/'lidar_pose/000000.npz').write_bytes(b'decoded-array')
        expected={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
        return source,expected

    def test_exact_members_provenance_and_deterministic_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,expected=self.fixture(root);a=root/'a.tar';b=root/'b.tar';provenance={'scene':'scene','source_receipt_hashes':{'lidar_pose':'a'*64}}
            meta=create_component_archive(source,a,expected_files=expected,provenance=provenance,other_bytes=100,budget_bytes=10**6)
            create_component_archive(source,b,expected_files=expected,provenance=provenance,other_bytes=100,budget_bytes=10**6)
            self.assertEqual(a.read_bytes(),b.read_bytes())
            checked=validate_component_archive(a,expected_archive_sha256=meta['sha256'],expected_manifest_sha256=meta['manifest_sha256'])
            self.assertEqual(checked['files'],2);self.assertEqual(checked['provenance'],provenance)

    def test_changed_source_undeclared_member_and_capacity_refused(self):
        for change in ('source','extra','budget','path'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);source,expected=self.fixture(root);a=root/'a.tar'
                if change=='source':(source/'lidar_pose/000000.npz').write_bytes(b'changed')
                elif change=='extra':(source/'orphan').write_bytes(b'x')
                elif change=='path':expected['../escape']='a'*64
                with self.assertRaises(ValueError):create_component_archive(source,a,expected_files=expected,provenance={},other_bytes=0,budget_bytes=1 if change=='budget' else 10**6)
                self.assertFalse(a.exists())

    def test_corrupt_archive_or_manifest_identity_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,expected=self.fixture(root);a=root/'a.tar';m=create_component_archive(source,a,expected_files=expected,provenance={},other_bytes=0,budget_bytes=10**6)
            with self.assertRaises(ValueError):validate_component_archive(a,expected_archive_sha256=m['sha256'],expected_manifest_sha256='0'*64)
            a.write_bytes(a.read_bytes()[:-100])
            with self.assertRaises(ValueError):validate_component_archive(a,expected_archive_sha256=m['sha256'],expected_manifest_sha256=m['manifest_sha256'])

if __name__=='__main__':unittest.main()
