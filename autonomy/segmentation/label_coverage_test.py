import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import pyarrow as pa
import pyarrow.parquet as pq

class LabelCoverageTests(unittest.TestCase):
    def run_coverage(self, source, component, output):
        env = dict(os.environ)
        package_root = str(Path(__file__).resolve().parents[1])
        env['PYTHONPATH'] = package_root + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
        return subprocess.run(
            [sys.executable, '-m', 'segmentation.label_coverage', str(source), component, str(output)],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_instance_ids_do_not_become_semantic_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'labels.parquet';out=Path(tmp)/'coverage.json'
            prefix='[LiDARSegmentationLabelComponent].range_image_return'
            fields={'key.frame_timestamp_micros':[10]}
            for ret in [1,2]:fields.update({prefix+str(ret)+'.values':[[99,2,10,0]],prefix+str(ret)+'.shape':[[1,2,2]]})
            pq.write_table(pa.table(fields),p)
            result=self.run_coverage(p,'lidar_segmentation',out)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(out.read_text())['semantic_counts'],{'0':2,'2':2})
            for ret in [1,2]:fields[prefix+str(ret)+'.values']=[[99,-1,10,0]]
            pq.write_table(pa.table(fields),p)
            result=self.run_coverage(p,'lidar_segmentation',out)
            self.assertNotEqual(result.returncode,0)

if __name__ == '__main__':
    unittest.main()
