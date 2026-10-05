import json,subprocess,sys,tempfile,unittest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

class ShardInventoryTests(unittest.TestCase):
    def run_case(self,rows):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input.parquet';out=Path(tmp)/'result.json'
            table=pa.table({'key.segment_context_name':[r[0] for r in rows],'key.frame_timestamp_micros':[r[1] for r in rows],'key.laser_name':[r[2] for r in rows]})
            pq.write_table(table,p)
            run=subprocess.run([sys.executable,'-m','pipeline.shard_inventory',str(p),'scene',str(out)],capture_output=True,text=True)
            return run.returncode,json.loads(out.read_text()) if out.exists() else None

    def test_native_rows_and_frame_membership_preserved(self):
        code,result=self.run_case([('scene',10,1),('scene',10,2),('scene',20,1)])
        self.assertEqual(code,0);self.assertIsNotNone(result)
        self.assertEqual(result['rows'],3);self.assertEqual(result['frame_timestamps'],[10,20])

    def test_duplicate_and_wrong_segment_are_rejected(self):
        for rows in [[('scene',10,1),('scene',10,1)],[('other',10,1)]]:
            with self.subTest(rows=rows):self.assertNotEqual(self.run_case(rows)[0],0)

if __name__=='__main__':unittest.main()
