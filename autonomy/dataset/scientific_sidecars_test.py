import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from dataset.scientific_sidecars import materialize_component


class ScientificSidecarTests(unittest.TestCase):
    prefix = '[LiDARPoseComponent].range_image_return1'

    def source(self, root, *, contexts=None, duplicate=False, malformed=False, empty=False):
        contexts = contexts or ['scene', 'scene']
        rows = 0 if empty else 2
        data = {'key.segment_context_name': pa.array(contexts[:rows], type=pa.string()),
                'key.frame_timestamp_micros': pa.array(([10,10] if duplicate else [10,20])[:rows],type=pa.int64()),
                'key.laser_name': pa.array([1,1][:rows],type=pa.int8()),
                self.prefix+'.values': pa.array([[1.,2.,3.,4.,5.,6.],None][:rows],type=pa.list_(pa.float32())),
                self.prefix+'.shape': pa.array([[1,2,4 if malformed else 3],None][:rows],type=pa.list_(pa.int32())),
                'optional.scalar': pa.array([None,3.][:rows],type=pa.float64())}
        path = root/'source.parquet'; pq.write_table(pa.table(data),path); return path

    def test_native_identity_array_shape_dtype_and_null_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=self.source(root); out=root/'decoded'
            result=materialize_component(source,'lidar_pose','scene',out,100000)
            self.assertEqual(result['component'],'lidar_pose'); self.assertEqual(len(result['rows']),2)
            self.assertEqual(result['output_bytes'],sum(p.stat().st_size for p in out.iterdir()))
            row=json.loads((out/result['rows'][0]['metadata']).read_text())
            self.assertEqual(row['fields']['key.frame_timestamp_micros'],10)
            self.assertIsNone(row['fields']['optional.scalar'])
            with np.load(out/result['rows'][0]['arrays'],allow_pickle=False) as arrays:
                actual=arrays[row['array_fields'][self.prefix]]
                np.testing.assert_array_equal(actual,np.arange(1,7,dtype=np.float32).reshape(1,2,3))
                self.assertEqual(actual.dtype,np.float32)
            null=json.loads((out/result['rows'][1]['metadata']).read_text())
            self.assertIsNone(null['array_fields'][self.prefix])

    def test_present_empty_component_has_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'decoded';r=materialize_component(self.source(root,empty=True),'lidar_pose','scene',out,100000)
            self.assertEqual(r['rows'],[]);self.assertTrue((out/'manifest.json').is_file())

    def test_wrong_context_duplicate_malformed_and_budget_rejected(self):
        for kwargs in ({'contexts':['other','scene']},{'duplicate':True},{'malformed':True},{}):
            with self.subTest(kwargs=kwargs),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);out=root/'decoded'
                with self.assertRaises(ValueError):
                    materialize_component(self.source(root,**kwargs),'lidar_pose','scene',out,1 if not kwargs else 100000)
                self.assertFalse((out/'manifest.json').exists())

    def test_existing_output_and_unsupported_component_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=self.source(root);out=root/'decoded';out.mkdir();(out/'keep').write_text('retained')
            for component in ('lidar_pose','camera_image'):
                with self.assertRaises(ValueError):materialize_component(source,component,'scene',out,100000)
            self.assertEqual((out/'keep').read_text(),'retained')


if __name__=='__main__':unittest.main()
