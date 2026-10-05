import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import pyarrow as pa
import pyarrow.parquet as pq

class LabelCoverageTests(unittest.TestCase):
    def test_instance_ids_do_not_become_semantic_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'labels.parquet';out=Path(tmp)/'coverage.json'
            prefix='[LiDARSegmentationLabelComponent].range_image_return'
            fields={'key.frame_timestamp_micros':[10]}
            for ret in [1,2]:fields.update({prefix+str(ret)+'.values':[[99,2,10,0]],prefix+str(ret)+'.shape':[[1,2,2]]})
            pq.write_table(pa.table(fields),p)
            result=subprocess.run(['python','-m','pipeline.label_coverage',str(p),'lidar_segmentation',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(out.read_text())['semantic_counts'],{'0':2,'2':2})
            for ret in [1,2]:fields[prefix+str(ret)+'.values']=[[99,-1,10,0]]
            pq.write_table(pa.table(fields),p)
            result=subprocess.run(['python','-m','pipeline.label_coverage',str(p),'lidar_segmentation',str(out)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
