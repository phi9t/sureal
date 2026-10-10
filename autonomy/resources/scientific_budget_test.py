import contextlib,io,tempfile,unittest
from pathlib import Path
from resources import scientific_budget
from resources.scientific_budget import check_working,reserve_write,fit_interval
class AdmissionTests(unittest.TestCase):
 def test_scientific_working_cap_is_still_20_gib(self):
  cap=20*1024**3
  self.assertEqual(getattr(scientific_budget,'SCIENTIFIC_WORKING_CAP_BYTES',None),cap)

 def test_check_working_records_under_cap_without_alert(self):
  stderr=io.StringIO()
  with contextlib.redirect_stderr(stderr):
   record=check_working(80,19,where='unit.under',limit=100)
  self.assertEqual(stderr.getvalue(),'')
  self.assertEqual(record['where'],'unit.under')
  self.assertEqual(record['used_bytes'],80)
  self.assertEqual(record['new_bytes'],19)
  self.assertEqual(record['limit_bytes'],100)
  self.assertEqual(record['over_by_bytes'],0)
  self.assertFalse(record['exceeded'])
  self.assertTrue(record['timestamp_utc'].endswith('+00:00'))

 def test_check_working_warns_and_records_over_cap(self):
  stderr=io.StringIO()
  with contextlib.redirect_stderr(stderr):
   record=check_working(90,11,where='unit.over',limit=100)
  warning=stderr.getvalue()
  self.assertIn('WARNING: scientific working cap exceeded',warning)
  self.assertIn('where=unit.over',warning)
  self.assertIn('used_bytes=90',warning)
  self.assertIn('new_bytes=11',warning)
  self.assertIn('limit_bytes=100',warning)
  self.assertEqual(record['where'],'unit.over')
  self.assertEqual(record['used_bytes'],90)
  self.assertEqual(record['new_bytes'],11)
  self.assertEqual(record['limit_bytes'],100)
  self.assertEqual(record['over_by_bytes'],1)
  self.assertTrue(record['exceeded'])

 def test_reserve_write_keeps_shape_and_becomes_advisory(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'existing';p.write_bytes(b'x'*90)
   stderr=io.StringIO()
   with contextlib.redirect_stderr(stderr):
    record=reserve_write(d,11,100)
   self.assertIn('WARNING: scientific working cap exceeded',stderr.getvalue())
   self.assertEqual(record['used_bytes_before'],90)
   self.assertEqual(record['maximum_new_bytes'],11)
   self.assertEqual(record['limit'],100)
   self.assertEqual(record['where'],'resources.scientific_budget.reserve_write')
   self.assertEqual(record['used_bytes'],90)
   self.assertEqual(record['new_bytes'],11)
   self.assertEqual(record['limit_bytes'],100)
   self.assertEqual(record['over_by_bytes'],1)
   self.assertTrue(record['exceeded'])
   self.assertEqual(p.read_bytes(),b'x'*90);self.assertEqual(len(list(Path(d).iterdir())),1)
 def test_sustained_fit_after_regression(self):
  curve=[{'step':i,'cumulative_train_seconds':i/2,'all_class_quality_passed':ok} for i,ok in [(0,False),(25,True),(50,False),(100,True),(200,True)]]
  r=fit_interval(curve);self.assertEqual(r['first_stable_fit_update_interval'],[50,100]);self.assertEqual(r['confirmation_update'],200)
 def test_censored(self):
  r=fit_interval([{'step':0,'cumulative_train_seconds':0,'all_class_quality_passed':False},{'step':10000,'cumulative_train_seconds':500,'all_class_quality_passed':False}]);self.assertTrue(r['right_censored']);self.assertEqual(r['observed_updates'],10000)

if __name__ == "__main__":
 unittest.main()
