import hashlib,json,tempfile,unittest
from pathlib import Path
from geometry.native_range_shape_test_fixtures import native_range_shape_fixture
from geometry.native_range_shape_worker import run_shape_worker
class WorkerTests(unittest.TestCase):
 def test_pinned_job_and_native_output(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'source';source,inventory=native_range_shape_fixture(p);job={'scene':'scene','membership':{'official_split':'training','research_splits':['train']},'source':source,'inventory':inventory};j=root/'job.json';j.write_text(json.dumps(job));h=hashlib.sha256(j.read_bytes()).hexdigest();out=root/'shapes.json';run_shape_worker(p,j,expected_job_sha256=h,output=out);r=json.loads(out.read_text());self.assertEqual(r['job_sha256'],h);self.assertEqual(r['membership'],job['membership']);self.assertEqual(r['independent']['records_verified'],2);self.assertEqual(r['shapes']['null_shape_records'],1);self.assertGreater(r['worker_resources']['peak_rss_kib'],0)
 def test_changed_job_and_existing_output_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);j=root/'job.json';j.write_text('{}');out=root/'shapes.json'
   with self.assertRaises(ValueError):run_shape_worker(root/'missing',j,expected_job_sha256='0'*64,output=out)
   self.assertFalse(out.exists());out.write_text('preserve')
   with self.assertRaises(ValueError):run_shape_worker(root/'missing',j,expected_job_sha256=hashlib.sha256(j.read_bytes()).hexdigest(),output=out)
   self.assertEqual(out.read_text(),'preserve')
if __name__=='__main__':unittest.main()
