import json
from pathlib import Path
import tempfile,unittest
import numpy as np
from dataset import scientific_sidecars_test as fixture
from dataset.scientific_sidecars import materialize_component
from dataset.scientific_sidecar_reader import iter_sidecar_rows
from evidence.source_snapshot import file_sha256

class ScientificSidecarReaderTests(unittest.TestCase):
    def setup_sidecar(self, root):
        source=fixture.ScientificSidecarTests().source(root);out=root/'decoded'
        manifest=materialize_component(source,'lidar_pose','scene',out,100000)
        return out,manifest,file_sha256(out/'manifest.json')

    def test_native_rows_arrays_nulls_and_repeat_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            out,manifest,digest=self.setup_sidecar(Path(tmp))
            for _ in range(2):
                rows=list(iter_sidecar_rows(out,expected_manifest_sha256=digest))
                self.assertEqual([r['key.frame_timestamp_micros'] for r in rows],[10,20])
                prefix=fixture.ScientificSidecarTests.prefix
                np.testing.assert_array_equal(rows[0][prefix+'.values'],np.arange(1,7,dtype=np.float32))
                self.assertEqual(rows[0][prefix+'.values'].dtype,np.float32)
                self.assertEqual(rows[0][prefix+'.shape'],[1,2,3])
                self.assertIsNone(rows[1][prefix+'.values']);self.assertIsNone(rows[1][prefix+'.shape'])

    def test_changed_artifact_or_manifest_rejected(self):
        for member in ('arrays','metadata','manifest'):
            with self.subTest(member=member),tempfile.TemporaryDirectory() as tmp:
                out,m,digest=self.setup_sidecar(Path(tmp));p=out/('manifest.json' if member=='manifest' else m['rows'][0][member]);p.write_bytes(p.read_bytes()+b'corrupt')
                with self.assertRaises(ValueError):list(iter_sidecar_rows(out,expected_manifest_sha256=digest))

    def test_unsafe_path_and_native_key_conflict_rejected(self):
        for mutation in ('path','key'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                out,m,digest=self.setup_sidecar(Path(tmp))
                if mutation=='path':m['rows'][0]['metadata']='../outside.json'
                else:
                    p=out/m['rows'][0]['metadata'];data=json.loads(p.read_text());data['fields']['key.frame_timestamp_micros']=99;p.write_text(json.dumps(data));m['rows'][0]['metadata_sha256']=file_sha256(p)
                (out/'manifest.json').write_text(json.dumps(m));digest=file_sha256(out/'manifest.json')
                with self.assertRaises(ValueError):list(iter_sidecar_rows(out,expected_manifest_sha256=digest))

if __name__=='__main__':unittest.main()
