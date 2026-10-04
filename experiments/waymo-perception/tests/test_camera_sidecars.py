import tempfile,unittest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from pipeline.camera_sidecars import materialize_camera_component
from pipeline.camera_sidecar_validate import validate_camera_component
class CameraSidecarTests(unittest.TestCase):
 def fixture(self,root):
  source=root/'source.parquet';pq.write_table(pa.table({'key.segment_context_name':['scene','scene'],'key.frame_timestamp_micros':pa.array([10,20],type=pa.int64()),'key.camera_name':pa.array([1,1],type=pa.int8()),'[CameraImageComponent].image':pa.array([b'jpeg-bytes',b'second'],type=pa.binary()),'optional':pa.array([None,[]],type=pa.list_(pa.int32()))}),source);return source
 def test_exact_bytes_keys_nulls_and_budget_reconciled(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=self.fixture(root);out=root/'decoded';r=materialize_camera_component(source,'camera_image','scene',out,100000);checked=validate_camera_component(source,out);self.assertEqual(checked['rows'],2);self.assertEqual(checked['binary_fields'],2);self.assertEqual(checked['output_bytes'],r['output_bytes']);self.assertEqual(sum(p.stat().st_size for p in out.iterdir()),r['output_bytes'])
 def test_capacity_wrong_scene_and_duplicate_keys_rejected(self):
  for kind in ['capacity','scene','duplicate']:
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);source=self.fixture(root)
    if kind=='duplicate':table=pq.read_table(source);pq.write_table(pa.concat_tables([table,table]),source)
    with self.assertRaises(ValueError):materialize_camera_component(source,'camera_image','other' if kind=='scene' else 'scene',root/'decoded',1 if kind=='capacity' else 100000)
 def test_binary_mutation_and_extra_artifacts_rejected(self):
  for kind in ['binary','extra']:
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);source=self.fixture(root);out=root/'decoded';materialize_camera_component(source,'camera_image','scene',out,100000)
    if kind=='binary':next(out.glob('*.bin')).write_bytes(b'changed')
    else:(out/'extra').write_bytes(b'extra')
    with self.assertRaises(ValueError):validate_camera_component(source,out)
if __name__=='__main__':unittest.main()
