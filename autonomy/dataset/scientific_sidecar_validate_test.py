import json
from pathlib import Path
import tempfile,unittest
import numpy as np
from dataset.scientific_sidecars_test import ScientificSidecarTests
from dataset.scientific_sidecars import materialize_component
from dataset.scientific_sidecar_validate import validate_component
from evidence.source_snapshot import file_sha256

class ScientificSidecarValidationTests(unittest.TestCase):
    def test_all_rows_reconciled_and_semantic_mutations_rejected(self):
        for mutation in ('none','field','array','key'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);fixture=ScientificSidecarTests();source=fixture.source(root);out=root/'decoded'
                report=materialize_component(source,'lidar_pose','scene',out,100000)
                first=report['rows'][0]
                if mutation in ('field','key'):
                    p=out/first['metadata'];m=json.loads(p.read_text());m['fields']['key.frame_timestamp_micros' if mutation=='key' else 'optional.scalar']=99;p.write_text(json.dumps(m));first['metadata_sha256']=file_sha256(p)
                elif mutation=='array':
                    p=out/first['arrays'];np.savez(p,a0=np.zeros((1,2,3),dtype=np.float32));first['arrays_sha256']=file_sha256(p)
                if mutation!='none':
                    (out/'manifest.json').write_text(json.dumps(report))
                    # Give corrupted data a consistent byte declaration, so content checks must reject it.
                    for _ in range(5):
                        report['output_bytes']=sum(p.stat().st_size for p in out.iterdir());(out/'manifest.json').write_text(json.dumps(report))
                    with self.assertRaises(ValueError):validate_component(source,out)
                else:self.assertEqual(validate_component(source,out)['rows'],2)

if __name__=='__main__':unittest.main()
