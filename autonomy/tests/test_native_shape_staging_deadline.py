import base64,hashlib,json,sys,tempfile,time,unittest
from pathlib import Path
from pipeline.staged_source import staged_source
from insula.staging_lease import staging_lease
class StagingDeadlineTests(unittest.TestCase):
 def record(self,data):
  h=hashlib.sha256(data).hexdigest();return {'hdfs_uri':'hdfs://fixture/native-source','sha256':h,'hdfs_roundtrip_sha256':h,'source_metadata':{'size':len(data),'md5_hash':base64.b64encode(hashlib.md5(data).digest()).decode()}}
 def prefix(self,program,deadline):
  wrapper='import sys; from geometry.native_shape_transfer import bounded_transfer; r=bounded_transfer([sys.executable,"-c",'+repr(program)+',*sys.argv[1:]],timeout_seconds='+repr(deadline)+'); raise SystemExit(r["exit_code"])'
  return [sys.executable,'-c',wrapper]
 def test_timeout_partial_stage_cleanup_and_lease_reuse(self):
  with tempfile.TemporaryDirectory() as tmp:
   cache=Path(tmp);(cache/'scientific-processing').mkdir();program='import sys,time; from pathlib import Path; Path(sys.argv[-1]).write_bytes(b"partial"); time.sleep(20)';start=time.monotonic()
   with staging_lease(cache/'scientific-processing/cohort-queue.lock'):
    with self.assertRaisesRegex(ValueError,'transfer failed'):
     with staged_source(self.record(b'x'*64),cache,retained_bytes=0,limit_bytes=1024,transfer_command=self.prefix(program,.25)):self.fail('timed-out source yielded')
    self.assertEqual(list((cache/'scientific-processing-staging').glob('stage-*')),[])
    with staging_lease(cache/'raw-staging.lock'):pass
   with staging_lease(cache/'scientific-processing/cohort-queue.lock'):pass
   self.assertLess(time.monotonic()-start,4)
 def test_success_admits_exact_bytes_and_cleans_stage(self):
  data=b'native-source-transfer-fixture'
  with tempfile.TemporaryDirectory() as tmp:
   cache=Path(tmp);program='import sys; from pathlib import Path; Path(sys.argv[-1]).write_bytes('+repr(data)+')'
   with staged_source(self.record(data),cache,retained_bytes=100,limit_bytes=1024,transfer_command=self.prefix(program,2)) as (p,e):
    self.assertEqual(p.read_bytes(),data);self.assertEqual(e['raw_peak_bytes_including_retained'],100+len(data));stage=p
   self.assertFalse(stage.exists())
if __name__=='__main__':unittest.main()
